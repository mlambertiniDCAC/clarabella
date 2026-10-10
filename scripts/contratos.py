#!/usr/bin/env python3
"""Contratos entre los tickets de un lote: quién expone y quién consume qué.

Uso:
  contratos.py <carpeta de ticket>...
  contratos.py --deriva <carpeta de ticket>... --worktree T#####=<ruta> [...] [--base master]

Cada plan.md lleva:
  ## Contrato
  ### Expone
  - `POST /internal/permisos/usuarios` — …
  ### Consume
  - `GET /compliance/:id/permisos-psp` — de T23821
  - `POST /internal/cuentas/:id/usuarios/sync-compliance` — existente

Cruza cada Consume con un Expone del lote (por verbo y ruta; los parámetros :x y {x} se
comparan como iguales), reporta consumos sin dueño, rutas expuestas dos veces y ciclos, y
termina con la línea "ORDEN: …" (orden topológico del lote). --deriva verifica que cada
Expone tenga rastro en el diff de los worktrees de su ticket.

Salida: 0 sin problemas, 1 con problemas, 2 error de formato.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

from reglas import lineas_agregadas, snapshot

ENDPOINT = re.compile(r'^\s*-\s*`([A-Z]+)\s+(\S+?)`(.*)$')
TICKET = re.compile(r'\bT\d{4,6}\b')
PARAM = re.compile(r':\w+|\{\w+\}')
DECLARA_RUTA = re.compile(
    r"@(Get|Post|Put|Patch|Delete|Controller)\(|Router::|addRoute|->(get|post|put|patch|delete)\(|"
    r"\.(get|post|put|patch|delete)\(\s*['\"]", re.I)


def normalizar(ruta):
    return PARAM.sub(':p', ruta.rstrip('/')) or '/'


def ticket_de(carpeta):
    m = re.match(r'(T\d+)', Path(carpeta).resolve().name)
    if not m:
        raise ValueError(f'la carpeta {carpeta} no empieza con T#####')
    return m.group(1)


def seccion(texto, titulo, nivel):
    """Cuerpo de '<#…#> titulo' hasta el próximo encabezado de nivel igual o mayor."""
    marca = '#' * nivel
    m = re.search(rf'^{marca} {re.escape(titulo)}[ \t]*\n(.*?)(?=^#{{1,{nivel}}} |\Z)', texto, re.M | re.S)
    return m.group(1) if m else None


def contrato(carpeta):
    plan = Path(carpeta, 'plan.md')
    if not plan.is_file():
        raise ValueError(f'falta plan.md en {carpeta}')
    sec = seccion(plan.read_text(encoding='utf-8'), 'Contrato', 2)
    if sec is None:
        raise ValueError(f'{plan} no tiene "## Contrato"')
    expone_txt, consume_txt = seccion(sec, 'Expone', 3), seccion(sec, 'Consume', 3)
    if expone_txt is None or consume_txt is None:
        raise ValueError(f'{plan}: "## Contrato" tiene que tener "### Expone" y "### Consume"')
    expone = [(m.group(1), m.group(2)) for m in map(ENDPOINT.match, expone_txt.splitlines()) if m]
    consume = []
    for linea in consume_txt.splitlines():
        m = ENDPOINT.match(linea)
        if not m:
            continue
        resto = m.group(3)
        t = TICKET.search(resto)
        origen = 'existente' if 'existente' in resto.lower() else (t.group(0) if t else None)
        consume.append((m.group(1), m.group(2), origen))
    return {'ticket': ticket_de(carpeta), 'expone': expone, 'consume': consume}


def orden_topologico(deps):
    """deps: {ticket: {tickets de los que depende}} → (orden, tickets en ciclo)."""
    pendientes = {t: set(d) for t, d in deps.items()}
    orden = []
    while True:
        listos = sorted(t for t, d in pendientes.items() if not d)
        if not listos:
            break
        for t in listos:
            orden.append(t)
            del pendientes[t]
        for d in pendientes.values():
            d.difference_update(listos)
    return orden, sorted(pendientes)


def cruzar(contratos):
    problemas, deps, duenos = [], {c['ticket']: set() for c in contratos}, {}
    for c in contratos:
        for verbo, ruta in c['expone']:
            clave = (verbo, normalizar(ruta))
            if clave in duenos and duenos[clave] != c['ticket']:
                problemas.append(f'expuesto dos veces: {verbo} {ruta} ({duenos[clave]} y {c["ticket"]})')
            duenos.setdefault(clave, c['ticket'])
    for c in contratos:
        for verbo, ruta, origen in c['consume']:
            if origen == 'existente':
                continue
            dueno = duenos.get((verbo, normalizar(ruta)))
            if origen and origen != dueno:
                if origen not in deps:
                    problemas.append(f'{c["ticket"]} consume {verbo} {ruta} de {origen}, que no está en el lote')
                else:
                    problemas.append(f'{c["ticket"]} consume {verbo} {ruta} de {origen}, pero {origen} no lo expone')
                continue
            if not dueno:
                problemas.append(f'{c["ticket"]} consume {verbo} {ruta} y nadie del lote lo expone '
                                 f'(si ya existe, marcalo "existente")')
                continue
            if dueno != c['ticket']:
                deps[c['ticket']].add(dueno)
    orden, ciclo = orden_topologico(deps)
    if ciclo:
        problemas.append(f'ciclo de dependencias entre: {", ".join(ciclo)}')
    return problemas, orden


def ultimo_segmento(ruta):
    segmentos = [s for s in ruta.strip('/').split('/') if s and not PARAM.fullmatch(s)]
    return segmentos[-1] if segmentos else ''


def deriva(contratos, worktrees, base):
    por_ticket = {}
    for w in worktrees:
        t, _, ruta = w.partition('=')
        por_ticket.setdefault(t, []).append(ruta)
    problemas = []
    for c in contratos:
        if not c['expone']:
            continue
        wts = por_ticket.get(c['ticket'])
        if not wts:
            problemas.append(f'{c["ticket"]}: sin --worktree, no se puede verificar')
            continue
        declaraciones = [texto for wt in wts for _, _, texto in lineas_agregadas(wt, base, snapshot(wt))
                         if DECLARA_RUTA.search(texto)]
        for verbo, ruta in c['expone']:
            seg = ultimo_segmento(ruta)
            if not any(seg and seg in linea for linea in declaraciones):
                problemas.append(f'{c["ticket"]}: {verbo} {ruta} no tiene rastro en el diff '
                                 f'(se buscó "{seg}" en las declaraciones de rutas)')
    return problemas


def main():
    p = argparse.ArgumentParser(description='Contratos entre los tickets de un lote.')
    p.add_argument('tickets', nargs='+')
    p.add_argument('--deriva', action='store_true')
    p.add_argument('--worktree', action='append', default=[], help='T#####=<ruta>')
    p.add_argument('--base', default='master')
    a = p.parse_args()
    contratos = [contrato(t) for t in a.tickets]
    if a.deriva:
        problemas = deriva(contratos, a.worktree, a.base)
        for x in problemas:
            print(x)
        if not problemas:
            print(f'OK: cada Expone tiene rastro en su diff ({len(contratos)} tickets)')
        return 1 if problemas else 0
    problemas, orden = cruzar(contratos)
    for x in problemas:
        print(x)
    if not problemas:
        print(f'OK: {len(contratos)} tickets, contratos cruzados')
    print('ORDEN: ' + ' '.join(orden))
    return 1 if problemas else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ValueError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(2)
    except subprocess.CalledProcessError as e:
        print(f'ERROR: git {" ".join(e.cmd[3:])}: {e.stderr.strip()}', file=sys.stderr)
        sys.exit(2)
