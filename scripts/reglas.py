#!/usr/bin/env python3
"""Alertas de reglas críticas del workspace sobre los cambios de un worktree.

Uso:
  reglas.py --worktree <ruta> --ownership <database-ownership.md> [--ms <nombre>] [--base <commit|tree>]
  reglas.py --snapshot --worktree <ruta>

Compara la base (master por defecto) con el estado actual del worktree, incluidos los
archivos nuevos sin trackear, sin tocar el index del repo. Las alertas son heurísticas: la
revisión las confirma o las descarta.

Reglas:
  tabla-ajena       una tabla que database-ownership.md asigna a otro servicio
  llamada-entre-ms  un ms que apunta a otro ms (los apigateway* sí pueden)
  estado-en-clase   PHP: una propiedad que se asigna fuera del constructor (salvo modelos y tests)

No mira tests, líneas de comentario ni hosts de infraestructura (Graylog, Redis, DB, colas…).

Salida: 0 sin alertas, 1 con alertas, 2 error.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REF_TABLA = [
    re.compile(r'\b(?:FROM|JOIN|INTO|UPDATE)\s+`?(?:\w+\.)?(\w+)', re.I),
    re.compile(r"Db::table\(\s*['\"](?:\w+\.)?(\w+)"),
    re.compile(r"\$table\s*=\s*['\"](?:\w+\.)?(\w+)"),
    re.compile(r"@Entity\(\s*\{[^}]*name:\s*['\"](\w+)"),
    re.compile(r"->from\(\s*['\"](?:\w+\.)?(\w+)"),
]
LLAMADA_MS = re.compile(r'\b([A-Z][A-Z0-9_]*)_SERVICE_HOST\b|https?://ms-[\w-]+|\bms-[\w-]+:\d{2,5}\b')
INFRA = re.compile(r'GRAYLOG|REDIS|MYSQL|MARIADB|DB|MONGO|RABBITMQ|RABBIT|KAFKA|ELASTIC|ELASTICSEARCH|SMTP|MAIL|KEYCLOAK')
COMENTARIO = re.compile(r'^\s*(//|#|\*|/\*|--)')
ASIGNACION = re.compile(r'(?:\$this->|self::\$|static::\$)(\w+)\s*(?:\[[^\]]*\]\s*)*'
                        r'(?:=(?![=>])|\.=|\+=|-=|\*=|\?\?=|\+\+|--)')
FUNCION = re.compile(r'\bfunction\s+&?(\w+)\s*\(')
MODELO = re.compile(r'\bextends\s+\w*Model\b')
CARPETA_MODELOS = re.compile(r'(^|/)Models?/')
ES_TEST = re.compile(r'(^|/)(tests?|__tests__)/|Test\.php$|\.spec\.ts$')


def git(worktree, *args, env=None):
    return subprocess.run(['git', '-C', str(worktree), *args], check=True,
                          capture_output=True, text=True, env=env).stdout


def snapshot(worktree):
    """Tree con el estado actual del worktree (incluye sin trackear), sin tocar su index."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, 'GIT_INDEX_FILE': os.path.join(tmp, 'index')}
        git(worktree, 'read-tree', 'HEAD', env=env)
        git(worktree, 'add', '-A', env=env)
        return git(worktree, 'write-tree', env=env).strip()


def lineas_agregadas(worktree, base, tree):
    """[(archivo, número de línea, texto)] de las líneas agregadas entre base y tree."""
    salida = git(worktree, 'diff', '-U0', '--no-color', '--no-ext-diff',
                 '--src-prefix=a/', '--dst-prefix=b/', base, tree)
    agregadas, archivo, nro = [], None, 0
    for linea in salida.splitlines():
        if linea.startswith('+++ '):
            archivo = None if linea[4:] == '/dev/null' else linea[6:]
        elif linea.startswith('@@'):
            nro = int(re.search(r'\+(\d+)', linea).group(1))
        elif linea.startswith('+') and archivo:
            agregadas.append((archivo, nro, linea[1:]))
            nro += 1
    return agregadas


def duenos_de_tablas(ownership):
    """{tabla sin esquema: {servicios dueños}} desde database-ownership.md."""
    duenos, ms = {}, None
    for linea in Path(ownership).read_text(encoding='utf-8').splitlines():
        if linea.startswith('### '):
            ms = linea[4:].split()[0]
        elif linea.startswith('# ') or linea.startswith('## '):
            ms = None
        elif ms:
            m = re.match(r'\s*-\s*`(?:\w+\.)?(\w+)`', linea)
            if m:
                duenos.setdefault(m.group(1), set()).add(ms)
    return duenos


def funcion_que_contiene(lineas, nro):
    for linea in reversed(lineas[:nro]):
        m = FUNCION.search(linea)
        if m:
            return m.group(1)
    return None


def llama_a_otro_ms(texto):
    for m in LLAMADA_MS.finditer(texto):
        if not (m.group(1) and INFRA.fullmatch(m.group(1))):
            return True
    return False


def alertas(worktree, ms, base, duenos):
    tree = snapshot(worktree)
    encontradas, vistas, contenidos = [], set(), {}
    es_gateway = ms.startswith('apigateway')

    def alertar(archivo, nro, regla, detalle):
        if (archivo, nro, regla, detalle) not in vistas:
            vistas.add((archivo, nro, regla, detalle))
            encontradas.append((archivo, nro, regla, detalle))

    for archivo, nro, texto in lineas_agregadas(worktree, base, tree):
        fragmento = texto.strip()[:100]
        if COMENTARIO.match(texto) or ES_TEST.search(archivo):
            continue
        for patron in REF_TABLA:
            for tabla in patron.findall(texto):
                dueños = duenos.get(tabla)
                if dueños and ms not in dueños:
                    alertar(archivo, nro, 'tabla-ajena',
                            f'{tabla} es de {", ".join(sorted(dueños))} · {fragmento}')
        if not es_gateway and llama_a_otro_ms(texto):
            alertar(archivo, nro, 'llamada-entre-ms', fragmento)
        if archivo.endswith('.php') and not CARPETA_MODELOS.search(archivo) and ASIGNACION.search(texto):
            if archivo not in contenidos:
                contenidos[archivo] = git(worktree, 'show', f'{tree}:{archivo}').splitlines()
            lineas = contenidos[archivo]
            if not MODELO.search('\n'.join(lineas)) and funcion_que_contiene(lineas, nro) != '__construct':
                alertar(archivo, nro, 'estado-en-clase', fragmento)
    return encontradas


def main():
    p = argparse.ArgumentParser(description='Alertas de reglas críticas sobre el diff de un worktree.')
    p.add_argument('--worktree', required=True)
    p.add_argument('--ownership', help='dcac-context/back/database-ownership.md')
    p.add_argument('--ms', help='nombre del servicio (default: nombre del directorio del worktree)')
    p.add_argument('--base', default='master', help='commit o tree contra el que comparar')
    p.add_argument('--snapshot', action='store_true', help='imprimir el tree del estado actual y salir')
    a = p.parse_args()
    if a.snapshot:
        print(snapshot(a.worktree))
        return 0
    if not a.ownership:
        p.error('falta --ownership')
    ms = a.ms or Path(a.worktree).resolve().name
    encontradas = alertas(a.worktree, ms, a.base, duenos_de_tablas(a.ownership))
    for archivo, nro, regla, detalle in encontradas:
        print(f'{archivo}:{nro} · {regla} · {detalle}')
    if not encontradas:
        print(f'OK: sin alertas en {ms} (base {a.base})')
    return 1 if encontradas else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        print(f'ERROR: git {" ".join(e.cmd[3:])}: {e.stderr.strip()}', file=sys.stderr)
        sys.exit(2)
