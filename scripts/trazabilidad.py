#!/usr/bin/env python3
"""Trazabilidad de un ticket: cruza los criterios CA# de spec.md con plan.md y tests.md.

Uso: trazabilidad.py <carpeta del ticket>

- spec.md: criterios en "## Criterios de aceptación" (- [ ] **CA1** — ...).
- plan.md: cada "## Parte N — <repo>" con una línea "Cubre: CA1, CA3".
- tests.md: "## Tabla de casos de prueba" que empieza con "| ID | Criterio |". Criterio: CA#, una
  decisión de la spec (E#, P#, C#) o "regresión".

Salida: 0 si todo cierra, 1 si hay huecos, 2 si falta un archivo o el formato no es el esperado.
"""
import re
import sys
from pathlib import Path

CA = re.compile(r'\bCA(\d+)\b')
DECISION = re.compile(r'\b([EPC]\d+)\b')
SEPARADOR = re.compile(r'^:?-+:?$')


def seccion(texto, titulo):
    """Cuerpo de '## <titulo>' hasta el próximo encabezado de nivel 2."""
    m = re.search(rf'^## {re.escape(titulo)}[ \t]*\n(.*?)(?=^## |\Z)', texto, re.M | re.S)
    return m.group(1) if m else ''


def ids(texto):
    return {f'CA{n}' for n in CA.findall(texto)}


def orden(ca):
    return int(ca[2:])


def partes_del_plan(plan):
    """[(nombre de la Parte, {CA#}, tiene línea Cubre:)]"""
    partes = []
    for m in re.finditer(r'^## (Parte \d+.*?)[ \t]*\n(.*?)(?=^## |\Z)', plan, re.M | re.S):
        cubre = re.findall(r'^Cubre:(.*)$', m.group(2), re.M)
        partes.append((m.group(1), ids(' '.join(cubre)), bool(cubre)))
    return partes


def casos_de_tests(tests):
    """[(ID del caso, texto de la columna Criterio)] de la tabla de casos."""
    filas = [l.strip() for l in seccion(tests, 'Tabla de casos de prueba').splitlines()
             if l.strip().startswith('|')]
    if not filas:
        raise ValueError('tests.md no tiene "## Tabla de casos de prueba" con filas')
    encabezado = [c.strip() for c in filas[0].strip('|').split('|')]
    if encabezado[:2] != ['ID', 'Criterio']:
        raise ValueError('la tabla de casos de tests.md tiene que empezar con "| ID | Criterio |"')
    casos = []
    for fila in filas[1:]:
        celdas = fila[1:].split('|')
        if len(celdas) < 2 or SEPARADOR.match(celdas[0].strip()):
            continue
        casos.append((celdas[0].strip(), celdas[1].strip()))
    return casos


def leer(carpeta):
    textos = {}
    for nombre in ('spec.md', 'plan.md', 'tests.md'):
        ruta = Path(carpeta, nombre)
        if not ruta.is_file():
            raise ValueError(f'falta {nombre} en {carpeta}')
        textos[nombre] = ruta.read_text(encoding='utf-8')
    return textos


def main(carpeta):
    textos = leer(carpeta)
    criterios = ids(seccion(textos['spec.md'], 'Criterios de aceptación'))
    if not criterios:
        raise ValueError('spec.md no tiene criterios numerados (CA1, CA2…) en "## Criterios de aceptación"')
    decisiones = set(DECISION.findall(textos['spec.md']))
    partes = partes_del_plan(textos['plan.md'])
    casos = casos_de_tests(textos['tests.md'])

    cubiertos_plan, cubiertos_tests = set(), set()
    sin_cubre, sin_criterio, inexistentes, decisiones_inexistentes = [], [], [], []
    for parte, cas, tiene_cubre in partes:
        if not tiene_cubre:
            sin_cubre.append(parte)
        cubiertos_plan |= cas & criterios
        inexistentes += [f'{ca} (plan.md · {parte})' for ca in sorted(cas - criterios, key=orden)]
    for caso, criterio in casos:
        cas, decs = ids(criterio), set(DECISION.findall(criterio))
        if not cas and not decs and criterio.lower() not in ('regresión', 'regresion'):
            sin_criterio.append(caso)
        decisiones_inexistentes += [f'{d} (tests.md · {caso})' for d in sorted(decs - decisiones)]
        cubiertos_tests |= cas & criterios
        inexistentes += [f'{ca} (tests.md · {caso})' for ca in sorted(cas - criterios, key=orden)]

    problemas = [
        ('CA sin Parte en plan.md', sorted(criterios - cubiertos_plan, key=orden)),
        ('Partes sin línea Cubre: en plan.md', sin_cubre),
        ('CA sin caso en tests.md', sorted(criterios - cubiertos_tests, key=orden)),
        ('Casos sin criterio en tests.md', sin_criterio),
        ('CA citados que no existen en spec.md', inexistentes),
        ('Decisiones citadas que no existen en spec.md', decisiones_inexistentes),
    ]
    hay = [(titulo, lista) for titulo, lista in problemas if lista]
    for titulo, lista in hay:
        print(f'{titulo}: {", ".join(lista)}')
    if not hay:
        print(f'OK: {len(criterios)} criterios, {len(partes)} Partes, {len(casos)} casos')
    return 1 if hay else 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(main(sys.argv[1]))
    except ValueError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(2)
