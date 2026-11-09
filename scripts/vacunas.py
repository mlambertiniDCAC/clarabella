import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

DOCKERFILES = ('Dockerfile.test', 'Dockerfile.dev', 'Dockerfile', 'Dockerfile.prod')
FROM_NODE = re.compile(r'^FROM\s+node:(\S+)', re.MULTILINE)


def tag_node(repo):
    repo = Path(repo)
    for archivo in DOCKERFILES:
        ruta = repo / archivo
        if not ruta.is_file():
            continue
        m = FROM_NODE.search(ruta.read_text(encoding='utf-8', errors='replace'))
        if m:
            return m.group(1), archivo
    return None, None


def clasificar_repos(raiz):
    salida = []
    for d in sorted(p for p in Path(raiz).iterdir() if p.is_dir()):
        if not (d / 'package.json').is_file():
            continue
        if not tag_node(d)[0]:
            salida.append((d.name, 'fuera', 'sin-FROM-node'))
        elif not (d / 'package-lock.json').is_file():
            salida.append((d.name, 'fuera', 'sin-package-lock'))
        else:
            salida.append((d.name, 'dentro', ''))
    return salida


def detectar_repos(raiz):
    return [nombre for nombre, veredicto, _ in clasificar_repos(raiz) if veredicto == 'dentro']


def _major(tag):
    m = re.match(r'(\d+)', tag or '')
    return m.group(1) if m else None


def notas_version(repo, tag):
    repo = Path(repo)
    notas = []
    major = _major(tag)
    if not major:
        return notas
    pkg = repo / 'package.json'
    if pkg.is_file():
        try:
            engines = json.loads(pkg.read_text(encoding='utf-8')).get('engines', {}).get('node')
        except (ValueError, AttributeError):
            engines = None
        if engines and major not in engines:
            notas.append(f'engines.node dice "{engines}" y el Dockerfile usa {tag}: revisar cuál manda')
    nvmrc = repo / '.nvmrc'
    if nvmrc.is_file():
        declarado = nvmrc.read_text(encoding='utf-8').strip().lstrip('v')
        if _major(declarado) != major:
            notas.append(f'.nvmrc dice {declarado} y el Dockerfile usa {tag}: revisar cuál manda')
    return notas


SEVERIDADES_NPM = ('critical', 'high', 'moderate', 'low')
ORDEN_NPM = {s: i for i, s in enumerate(SEVERIDADES_NPM)}


def _advisory(via):
    for v in via or []:
        if isinstance(v, dict) and v.get('url'):
            return v['url'].rstrip('/').rsplit('/', 1)[-1]
    return None


def normalizar_npm(data):
    data = data or {}
    conteos = (data.get('metadata') or {}).get('vulnerabilities') or {}
    salida = {s: int(conteos.get(s, 0)) for s in SEVERIDADES_NPM}
    hallazgos = []
    for nombre, v in sorted((data.get('vulnerabilities') or {}).items()):
        fix = v.get('fixAvailable')
        hallazgos.append({
            'paquete': v.get('name', nombre),
            'severidad': v.get('severity'),
            'advisory': _advisory(v.get('via')),
            'via': list(v.get('effects') or []),
            'fix_disponible': bool(fix),
            'fix_breaking': bool(fix.get('isSemVerMajor')) if isinstance(fix, dict) else False,
        })
    hallazgos.sort(key=lambda h: (ORDEN_NPM.get(h['severidad'], 9), h['paquete']))
    salida['hallazgos'] = hallazgos
    if data.get('error'):
        error = data['error']
        salida['error'] = json.dumps(error) if isinstance(error, dict) else str(error)
    return salida


def normalizar_trivy_vuln(data):
    salida = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    hallazgos = []
    for resultado in (data or {}).get('Results') or []:
        for v in resultado.get('Vulnerabilities') or []:
            severidad = (v.get('Severity') or '').upper()
            clave = severidad.lower()
            if clave in salida:
                salida[clave] += 1
            if severidad in ('CRITICAL', 'HIGH'):
                hallazgos.append({
                    'id': v.get('VulnerabilityID'),
                    'paquete': v.get('PkgName'),
                    'instalada': v.get('InstalledVersion'),
                    'fixada': v.get('FixedVersion'),
                    'severidad': severidad,
                })
    salida['hallazgos'] = hallazgos
    return salida


def normalizar_secretos(data):
    salida = []
    for resultado in (data or {}).get('Results') or []:
        for s in resultado.get('Secrets') or []:
            salida.append({
                'archivo': resultado.get('Target'),
                'linea': s.get('StartLine'),
                'tipo': s.get('RuleID'),
            })
    return salida


TRIVY = 'aquasec/trivy:0.58.1'
CACHE_TRIVY = 'clarabella-trivy-cache'
FLAGS_JEST = '--maxWorkers=2 --workerIdleMemoryLimit=512MB'


def _scripts(repo):
    pkg = Path(repo) / 'package.json'
    if not pkg.is_file():
        return {}
    try:
        datos = json.loads(pkg.read_text(encoding='utf-8'))
    except ValueError:
        return {}
    scripts = datos.get('scripts') if isinstance(datos, dict) else None
    return scripts if isinstance(scripts, dict) else {}


def plan_validacion(repo):
    scripts = _scripts(repo)
    correr, salteados = [], []
    for nombre in ('build', 'test'):
        (correr if scripts.get(nombre) else salteados).append(nombre)
    test = scripts.get('test', '')
    flags = FLAGS_JEST if 'jest' in test and '--runInBand' not in test else ''
    return correr, salteados, flags


def cmd_audit(worktree, tag):
    return ['docker', 'run', '--rm', '-v', f'{worktree}:/app:ro', '-w', '/app',
            '-e', 'HOME=/tmp', '-e', 'npm_config_cache=/tmp/.npm',
            f'node:{tag}', 'npm', 'audit', '--json']


def _trivy_base(trivy, montaje=None):
    cmd = ['docker', 'run', '--rm', '-v', f'{CACHE_TRIVY}:/root/.cache/trivy']
    if montaje:
        cmd += ['-v', montaje]
    return cmd + [trivy]


def cmd_trivy_fs(worktree, trivy=TRIVY):
    return _trivy_base(trivy, f'{worktree}:/src:ro') + [
        'fs', '--scanners', 'vuln', '--skip-dirs', 'node_modules', '--format', 'json', '/src']


def cmd_trivy_image(tag, trivy=TRIVY):
    return _trivy_base(trivy) + ['image', '--format', 'json', f'node:{tag}']


def cmd_trivy_secret(worktree, trivy=TRIVY):
    return _trivy_base(trivy, f'{worktree}:/src:ro') + [
        'fs', '--scanners', 'secret', '--skip-dirs', 'node_modules', '--format', 'json', '/src']


def cmd_audit_fix(worktree, tag, uid, gid):
    return ['docker', 'run', '--rm', '-v', f'{worktree}:/app', '-w', '/app',
            '-e', 'HOME=/tmp', '-e', 'npm_config_cache=/tmp/.npm',
            '--user', f'{uid}:{gid}', f'node:{tag}',
            'npm', 'audit', 'fix', '--package-lock-only']


def cmd_validar(worktree, tag, correr=('build', 'test'), flags=FLAGS_JEST):
    pasos = ['mkdir -p /work', 'cd /work', 'cp -a /src/. .', 'rm -rf .git',
             'npm pkg delete scripts.prepare', 'npm ci']
    for nombre in correr:
        if nombre == 'test' and flags:
            pasos.append(f'npm run test -- {flags}')
        else:
            pasos.append(f'npm run {nombre}')
    guion = ' && '.join(pasos)
    return ['docker', 'run', '--rm', '-v', f'{worktree}:/src:ro', '-w', '/tmp',
            '-e', 'HOME=/tmp', '-e', 'npm_config_cache=/tmp/.npm',
            f'node:{tag}', 'sh', '-c', guion]


def _ejecutar_real(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout or '', p.stderr or ''


def _ejecutar_falso(cmd):
    return 0, '{}', ''


def _seccion(ejecutar, cmd, normalizar, secreto=False):
    rc, salida, err = ejecutar(cmd)
    try:
        datos = json.loads(salida)
    except ValueError:
        datos = None
    if not isinstance(datos, dict):
        if secreto:
            return {'error': f'el scan de secretos no devolvió JSON (exit {rc})'}
        ultima = (err.strip().splitlines() or [''])[-1][:200]
        return {'error': f'exit {rc}: {ultima}' if ultima else f'exit {rc} sin salida'}
    return normalizar(datos)


def escanear(worktree, repo_nombre, base, ejecutar, trivy=TRIVY):
    tag, origen = tag_node(worktree)
    datos = {'repo': repo_nombre, 'node_tag': tag, 'node_tag_origen': origen, 'base': base}
    if not tag:
        datos['error'] = 'ningún Dockerfile declara FROM node:<tag>: fuera de alcance automático'
        datos['notas'] = []
        datos['scan_incompleto'] = ['npm', 'trivy_lock', 'imagen_base', 'secretos']
        return datos
    ruta = Path(worktree)
    sin_lock = not (ruta / 'package-lock.json').is_file()
    worktree = str(ruta.resolve())
    datos['sin_lock'] = sin_lock
    if sin_lock:
        datos['npm'] = {'error': 'sin package-lock.json: npm audit no tiene qué leer, '
                                 'y no se aplica ningún fix'}
    else:
        datos['npm'] = _seccion(ejecutar, cmd_audit(worktree, tag), normalizar_npm)
    datos['trivy_lock'] = _seccion(ejecutar, cmd_trivy_fs(worktree, trivy), normalizar_trivy_vuln)
    base_img = _seccion(ejecutar, cmd_trivy_image(tag, trivy), normalizar_trivy_vuln)
    base_img['tag'] = f'node:{tag}'
    datos['imagen_base'] = base_img
    secretos = _seccion(ejecutar, cmd_trivy_secret(worktree, trivy), normalizar_secretos,
                        secreto=True)
    datos['secretos'] = secretos if isinstance(secretos, list) else []
    if isinstance(secretos, dict):
        datos['secretos_error'] = secretos['error']
    incompleto = [clave for clave in ('npm', 'trivy_lock', 'imagen_base')
                  if 'error' in datos[clave]]
    if 'secretos_error' in datos:
        incompleto.append('secretos')
    datos['scan_incompleto'] = incompleto
    notas = notas_version(worktree, tag)
    for clave in incompleto:
        motivo = datos['secretos_error'] if clave == 'secretos' else datos[clave]['error']
        notas.append(f'scan incompleto en {clave}: {motivo}')
    datos['notas'] = notas
    return datos


def comandos_fix(worktree, tag, uid, gid):
    correr, _, flags = plan_validacion(worktree)
    ruta = str(Path(worktree).resolve())
    return [shlex.join(cmd_audit_fix(ruta, tag, uid, gid)),
            shlex.join(cmd_validar(ruta, tag, correr, flags))]


def main(argv=None):
    p = argparse.ArgumentParser(description='Scan de vulnerabilidades de un repo Node')
    p.add_argument('--detectar', action='store_true')
    p.add_argument('--raiz', default='microservicios')
    p.add_argument('--worktree')
    p.add_argument('--repo')
    p.add_argument('--base', default='master')
    p.add_argument('--out')
    p.add_argument('--trivy-image', default=TRIVY)
    p.add_argument('--comandos', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args(argv)

    if a.detectar:
        for nombre, veredicto, motivo in clasificar_repos(a.raiz):
            print(f'{nombre} {veredicto} {motivo}'.rstrip())
        return 0

    if not a.worktree:
        p.error('se necesita --worktree (o --detectar)')

    if a.comandos:
        tag, _ = tag_node(a.worktree)
        if not tag:
            print('sin FROM node:<tag>: fuera de alcance', file=sys.stderr)
            return 1
        if not (Path(a.worktree) / 'package-lock.json').is_file():
            print('sin package-lock.json: no se aplica ningún fix', file=sys.stderr)
            return 1
        for linea in comandos_fix(a.worktree, tag, os.getuid(), os.getgid()):
            print(linea)
        salteados = plan_validacion(a.worktree)[1]
        if salteados:
            print('SALTEADOS: ' + ' '.join(salteados))
        return 0

    ejecutar = _ejecutar_falso if a.dry_run else _ejecutar_real
    datos = escanear(a.worktree, a.repo or Path(a.worktree).name, a.base, ejecutar, a.trivy_image)
    texto = json.dumps(datos, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).mkdir(parents=True, exist_ok=True)
        destino = Path(a.out) / f"{datos['repo']}.json"
        destino.write_text(texto + '\n', encoding='utf-8')
        print(destino)
    else:
        print(texto)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
