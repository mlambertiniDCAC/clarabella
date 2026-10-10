#!/usr/bin/env python3
"""Ficha de un ticket para el juicio de valor: qué pide, qué toca, qué se decidió sin el
usuario y cuánto costó hasta acá. Cuenta y copia; no opina.

Uso: fichas.py <carpeta del ticket>
"""
import re
import sys
from pathlib import Path

from contratos import contrato, seccion
from hechos import SIN_REGISTRO, economia

DECIDIDO_SIN_USUARIO = re.compile(r'PROVISORIA|provisoria|DECISIÓN MENOR|\bP\d+\b')
MIGRACION = re.compile(r'migraci[oó]n|migration|crear-migracion', re.I)


def leer(ruta):
    return ruta.read_text(encoding='utf-8') if ruta.is_file() else ''


def main(carpeta):
    t = Path(carpeta)
    if not t.is_dir():
        print(f'ERROR: no existe {t}', file=sys.stderr)
        return 2
    spec, plan = leer(t / 'spec.md'), leer(t / 'plan.md')
    titulo = next((l[2:].strip() for l in spec.splitlines() if l.startswith('# ')), t.name)
    objetivo = (seccion(spec, 'Objetivo', 2) or '').strip() or SIN_REGISTRO
    repos = re.findall(r'^## Parte \d+\s*[—-]\s*(\S+)', plan, re.M)
    migraciones = [l.strip() for l in plan.splitlines() if MIGRACION.search(l)][:5]
    try:
        c = contrato(t)
        lineas_contrato = [f'- Expone: {v} {r}' for v, r in c['expone']]
        lineas_contrato += [f'- Consume: {v} {r}' + (f' (de {o})' if o and o != 'existente' else
                                                       ' (existente)' if o else '')
                            for v, r, o in c['consume']]
    except ValueError:
        lineas_contrato = []
    decisiones = seccion(spec, 'Decisiones de contrato', 2) or ''
    sin_usuario = [l.strip() for l in decisiones.splitlines()
                   if l.strip().startswith('-') and DECIDIDO_SIN_USUARIO.search(l)]

    secciones = [
        (f'# Ficha — {titulo}', []),
        ('## Qué pide', [objetivo]),
        ('## Repos', [f'- {r}' for r in repos] or [SIN_REGISTRO]),
        ('## Migraciones (menciones en el plan)', migraciones or ['ninguna']),
        ('## Contrato', lineas_contrato or [SIN_REGISTRO]),
        ('## Decidido sin el usuario (provisorias y menores)', sin_usuario or ['ninguna']),
        ('## Costo hasta acá', economia(t)),
    ]
    for titulo_sec, cuerpo in secciones:
        print(titulo_sec)
        if cuerpo:
            print('\n'.join(cuerpo))
        print()
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
