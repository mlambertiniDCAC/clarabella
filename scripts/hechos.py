#!/usr/bin/env python3
"""Hechos de un ticket para el Cronista: los datos duros, sacados de los archivos.

Uso: hechos.py <carpeta del ticket> [--worktree <ruta>]... [--base master]

No interpreta ni clasifica: cuenta y copia. Lo que falta sale como "sin registro".
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

from reglas import git, snapshot

SIN_REGISTRO = 'sin registro'


def celdas(fila):
    return [c.strip() for c in fila.strip().strip('|').split('|')]


def numero(texto):
    return float(texto.replace(',', '.'))


def cantidad(m):
    factor = {'k': 1_000, 'm': 1_000_000}.get((m.group(2) or '').lower(), 1)
    return round(numero(m.group(1)) * factor)


def costo(texto):
    """(segundos, tokens, contexto retomado), cada uno None si no está.

    '248 s · 102k tokens' es un subagente nuevo; '35 s · 265k acumulados' es uno retomado,
    y el número es el contexto que arrastra, no tokens nuevos: se cuenta aparte.
    """
    segundos = None
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*min\b', texto)
    if m:
        segundos = round(numero(m.group(1)) * 60)
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*s\b', texto)
    if m:
        segundos = (segundos or 0) + round(numero(m.group(1)))
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*tokens(?!\s+acumulados)', texto)
    tokens = cantidad(m) if m else None
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*(?:tokens\s+)?acumulados', texto)
    retomado = cantidad(m) if m else None
    return segundos, tokens, retomado


def economia(ticket):
    ruta = ticket / 'registro.md'
    if not ruta.is_file():
        return [SIN_REGISTRO]
    filas = [l for l in ruta.read_text(encoding='utf-8').splitlines() if l.strip().startswith('|')]
    if not filas:
        return [SIN_REGISTRO]
    encabezado = celdas(filas[0])
    i_rol, i_modelo = encabezado.index('Rol'), encabezado.index('Modelo')
    i_costo = next((i for i, c in enumerate(encabezado) if 'Duraci' in c or 'oken' in c), len(encabezado) - 1)
    grupos = {}
    for fila in filas[2:]:
        c = celdas(fila)
        if len(c) <= max(i_rol, i_modelo):
            continue
        segundos, tokens, retomado = costo(' '.join(c[i_costo:]))
        g = grupos.setdefault((c[i_rol], c[i_modelo]), [0, 0, 0, 0, 0])
        g[0] += 1
        if segundos is None or (tokens is None and retomado is None):
            g[4] += 1
        else:
            g[1] += segundos
            g[2] += tokens or 0
            g[3] += retomado or 0
    salida = ['| Rol | Modelo | Subagentes | Duración (s) | Tokens | Contexto retomado | Sin registro |',
              '|-----|--------|------------|--------------|--------|-------------------|--------------|']
    total = [0, 0, 0, 0, 0]
    for (rol, modelo), g in grupos.items():
        salida.append(f'| {rol} | {modelo} | {g[0]} | {g[1]} | {g[2]} | {g[3]} | {g[4]} |')
        total = [a + b for a, b in zip(total, g)]
    salida.append('')
    salida.append(f'**Total:** {total[0]} subagentes · {total[1]} s · {total[2]} tokens · '
                  f'{total[3]} de contexto retomado · {total[4]} sin registro')
    return salida


def resultado(ruta):
    m = re.search(r'^RESULTADO:.*$', ruta.read_text(encoding='utf-8'), re.M)
    return m.group(0) if m else SIN_REGISTRO


def verificacion(ticket):
    testeo = ticket / 'revision' / 'testeo'
    red = testeo / 'red.md'
    salida = [f'- RED: {resultado(red) if red.is_file() else SIN_REGISTRO}']
    greens = sorted(testeo.glob('green-*.md'), key=lambda p: int(re.sub(r'\D', '', p.stem) or 0))
    for g in greens:
        salida.append(f'- GREEN {re.sub(r"[^0-9]", "", g.stem)}: {resultado(g)}')
    salida.append(f'\nCorridas de GREEN: {len(greens)}')
    return salida


def repos(worktrees, base):
    if not worktrees:
        return [SIN_REGISTRO]
    salida = []
    for wt in worktrees:
        stat = git(wt, 'diff', '--stat', base, snapshot(wt)).strip().splitlines()
        salida.append(f'- {Path(wt).resolve().name}: {stat[-1].strip() if stat else "sin cambios"}')
    return salida


def revisiones(ticket):
    archivos = sorted((ticket / 'revision').glob('revision-*.md'))
    if not archivos:
        return [SIN_REGISTRO]
    salida = []
    for a in archivos:
        texto = a.read_text(encoding='utf-8')
        hallazgos = len(re.findall(r'^### H\d+', texto, re.M))
        bloqueantes = len(re.findall(r'^### H\d+ · bloqueante', texto, re.M))
        salida.append(f'- {a.name}: {hallazgos} hallazgos ({bloqueantes} bloqueantes)')
    return salida


def decisiones(ticket):
    salida = ['### spec.md § Decisiones de contrato']
    spec = ticket / 'spec.md'
    m = None
    if spec.is_file():
        m = re.search(r'^## Decisiones de contrato[ \t]*\n(.*?)(?=^## |\Z)',
                      spec.read_text(encoding='utf-8'), re.M | re.S)
    salida.append(m.group(1).strip() if m and m.group(1).strip() else SIN_REGISTRO)
    salida.append('')
    salida.append('### revision/provisorias.md')
    provisorias = ticket / 'revision' / 'provisorias.md'
    salida.append(provisorias.read_text(encoding='utf-8').strip() if provisorias.is_file() else SIN_REGISTRO)
    return salida


def main():
    p = argparse.ArgumentParser(description='Hechos de un ticket para el Cronista.')
    p.add_argument('ticket')
    p.add_argument('--worktree', action='append', default=[])
    p.add_argument('--base', default='master')
    a = p.parse_args()
    ticket = Path(a.ticket)
    if not ticket.is_dir():
        print(f'ERROR: no existe {ticket}', file=sys.stderr)
        return 2
    secciones = [
        (f'# Hechos — {ticket.name}', []),
        ('## Economía', economia(ticket)),
        ('## Verificación', verificacion(ticket)),
        ('## Repos', repos(a.worktree, a.base)),
        ('## Revisiones', revisiones(ticket)),
        ('## Decisiones registradas (textuales, sin clasificar)', decisiones(ticket)),
    ]
    for titulo, cuerpo in secciones:
        print(titulo)
        print('\n'.join(cuerpo))
        print()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        print(f'ERROR: git {" ".join(e.cmd[3:])}: {e.stderr.strip()}', file=sys.stderr)
        sys.exit(2)
