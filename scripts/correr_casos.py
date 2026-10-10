#!/usr/bin/env python3
"""Corre los casos de un ticket (casos/<ms>/T##.sh) y resume el resultado. 0 tokens.

Uso: correr_casos.py <carpeta del ticket> [--red] [--solo T01,T05] [--timeout 300]

Cada caso es un script de bash: exit 0 pasa, cualquier otro código falla. Corre con el
entorno heredado. --red compara con la última columna de la tabla de casos de tests.md
("Esperado en RED"): lo nuevo tiene que fallar y la regresión pasar.

Un caso de tests.md sin script cuenta como problema ("sin script").
Salida: 0 si todo dio lo esperado, 1 si no, 2 error.
"""
import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

from trazabilidad import casos_de_tests, seccion

LINEAS_DE_SALIDA = 40


def esperados_en_red(tests):
    filas = [l.strip() for l in seccion(tests, 'Tabla de casos de prueba').splitlines()
             if l.strip().startswith('|')]
    encabezado = [c.strip() for c in filas[0].strip('|').split('|')] if filas else []
    if not encabezado or encabezado[-1] != 'Esperado en RED':
        raise ValueError('la tabla de casos de tests.md tiene que terminar con la columna "Esperado en RED"')
    esperados = {}
    for fila in filas[1:]:
        celdas = [c.strip() for c in fila.strip('|').split('|')]
        if celdas and not set(celdas[0]) <= set(':-'):
            esperados[celdas[0]] = celdas[-1].lower()
    return esperados


def correr(caso, timeout):
    """(pasó, salida). Corre en su propio grupo de procesos: al vencer el timeout se mata el
    grupo entero, así un curl colgado no deja la corrida esperando."""
    proceso = subprocess.Popen(['bash', str(caso)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, start_new_session=True)
    try:
        salida, _ = proceso.communicate(timeout=timeout)
        return proceso.returncode == 0, salida.strip()
    except subprocess.TimeoutExpired:
        os.killpg(proceso.pid, signal.SIGKILL)
        proceso.communicate()
        return False, f'TIMEOUT tras {timeout} s'


def main():
    p = argparse.ArgumentParser(description='Corre los casos de un ticket.')
    p.add_argument('ticket')
    p.add_argument('--red', action='store_true')
    p.add_argument('--solo', default='')
    p.add_argument('--timeout', type=int, default=300)
    a = p.parse_args()
    ticket = Path(a.ticket)
    scripts = sorted(ticket.glob('casos/*/T*.sh'))
    if not scripts:
        raise ValueError(f'no hay casos en {ticket}/casos/<ms>/T##.sh')
    solo = {s.strip() for s in a.solo.split(',') if s.strip()}
    tests_md = ticket / 'tests.md'
    tests = tests_md.read_text(encoding='utf-8') if tests_md.is_file() else ''
    ids_tests = [caso for caso, _ in casos_de_tests(tests)] if tests else []
    esperados = esperados_en_red(tests) if a.red else {}

    pasan = fallan = ok = no = 0
    con_script = set()
    for script in scripts:
        caso, ms = script.stem, script.parent.name
        if solo and caso not in solo:
            continue
        con_script.add(caso)
        paso, salida = correr(script, a.timeout)
        resultado = 'PASA' if paso else 'FALLA'
        pasan += paso
        fallan += not paso
        linea = f'{caso} · {ms} · {resultado}'
        if a.red:
            esperado = esperados.get(caso, '?')
            coincide = (esperado == 'pasa') == paso
            ok += coincide
            no += not coincide
            linea += f' · esperado {esperado} · {"OK" if coincide else "NO"}'
        print(linea)
        if not paso or (a.red and not coincide):
            for l in salida.splitlines()[-LINEAS_DE_SALIDA:]:
                print(f'    {l}')
    sin_script = [c for c in ids_tests if c not in con_script and (not solo or c in solo)]
    for caso in sin_script:
        print(f'{caso} · sin script')
    extra = f' / {len(sin_script)} sin script' if sin_script else ''
    if a.red:
        print(f'RESULTADO RED: {ok} dieron lo esperado / {no} no{extra}')
        return 1 if no or sin_script else 0
    print(f'RESULTADO: {pasan} pasan / {fallan} fallan{extra}')
    return 1 if fallan or sin_script else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ValueError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(2)
