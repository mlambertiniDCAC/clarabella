# vacunar-repos — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar al plugin clarabella la skill `vacunar-repos`, que escanea vulnerabilidades en los repos Node del workspace, aplica solo el fix seguro, lo valida, y deja el diff listo para que el usuario apruebe el envío.

**Architecture:** Un script Python de stdlib (`scripts/vacunas.py`) hace la parte determinística y sin tokens: detecta repos, lee la versión de node del Dockerfile, arma y corre los comandos de `npm audit` y trivy en contenedores efímeros, y normaliza la salida a un JSON chico por repo. Un agente nuevo (`veterinario`, sonnet · medio, uno por repo) lee ese JSON, aplica `npm audit fix --package-lock-only`, valida con los tests del repo y devuelve un contrato con lo arreglado, lo pendiente y las dudas. La skill (`skills/vacunar-repos/SKILL.md`) orquesta: worktrees, tandas de 3, consolidación en el chat, `mostrar-diff` y `enviar-review` gateado.

**Tech Stack:** Python 3 stdlib (`unittest`, `json`, `re`, `pathlib`, `subprocess`, `argparse`), Docker (`node:<tag>`, `aquasec/trivy`), markdown de skills y agentes de Claude Code.

**Spec:** `docs/specs/2026-10-15-vacunar-repos-design.md`

## Global Constraints

- **Nada de commits.** Marcos maneja git él mismo: ninguna tarea de este plan commitea, ni crea branches en el repo del plugin. Los pasos terminan con la suite verde, no con un commit.
- **Sin comentarios en el código.** El código que se escribe no lleva comentarios explicativos; el único comentario admitido es el que ya existe en `tests/test_agentes.py`.
- **Python stdlib solamente**, como el resto de `scripts/`. Sin dependencias nuevas.
- **Texto en español**, igual que todo el plugin (nombres de funciones, claves de JSON, mensajes).
- **La suite completa** es `python3 -m unittest discover -s tests -v`, corrida desde `/home/marcos/projects/clarabella`. Tiene que quedar verde al final de cada tarea.
- **Ningún test requiere Docker ni red.** Los comandos se arman como listas y se comparan; la ejecución se inyecta.
- **Imagen de trivy fijada por constante**: `aquasec/trivy:0.58.1`, sobreescribible con `--trivy-image`. Nunca `latest`.
- **Prohibiciones que el código debe garantizar**: el comando de fix nunca lleva `--force`, siempre lleva `--package-lock-only` y `--user <uid>:<gid>`; el normalizador de secretos nunca propaga el valor del secreto.
- **Versión objetivo del plugin**: 0.7.0 en `.claude-plugin/plugin.json`.

## Review Focus

- **`FROM node@sha256:...` sin tag** — un Dockerfile pineado por digest no da una versión usable; `tag_node` tiene que devolver `(None, None)` y no un tag inventado. Test en Task 1.
- **`npm audit` que devuelve un error en vez de un reporte** (repo sin lockfile, registry caído): el JSON trae `{"error": {...}}` y ninguna clave `metadata`; `normalizar_npm` tiene que devolver conteos en cero y el error en `"error"`, no explotar. Test en Task 2.
- **Trivy con `"Vulnerabilities": null`** — trivy emite `null`, no `[]`, cuando un target no tiene hallazgos; iterar sobre `null` rompe. Test en Task 2.
- **Rutas con espacios** (`.worktrees/vacuna-2026-10-15/ms psp`): los comandos se arman como listas argv, nunca interpolando en un string de shell. Test en Task 3.
- **El valor del secreto repetido en otro campo de trivy** (`Match`, `Code.Lines`, `Title`): el normalizador arma el hallazgo con lista blanca de campos, así que agregar un campo nuevo en trivy no filtra el valor. Test en Task 2.

---

### Task 1: Detección de repos Node y versión de node

**Files:**
- Create: `scripts/vacunas.py`
- Test: `tests/test_vacunas.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `DOCKERFILES: tuple[str, ...]` = `('Dockerfile.test', 'Dockerfile.dev', 'Dockerfile', 'Dockerfile.prod')`
  - `tag_node(repo: Path) -> tuple[str | None, str | None]` — `(tag, archivo)` del primer `FROM node:<tag>`, buscando en el orden de `DOCKERFILES`. Sin coincidencia: `(None, None)`.
  - `detectar_repos(raiz: Path) -> list[str]` — nombres de carpeta, ordenados, que tienen `package.json` y algún `FROM node:` en sus Dockerfiles.
  - `notas_version(repo: Path, tag: str) -> list[str]` — una nota por conflicto entre el tag y `engines.node` del `package.json` o `.nvmrc`. Sin conflictos: `[]`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_vacunas.py`:

```python
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'scripts'))

import vacunas


def repo(tmp, nombre, dockerfiles, package=None, nvmrc=None):
    d = Path(tmp) / nombre
    d.mkdir(parents=True)
    for archivo, contenido in dockerfiles.items():
        (d / archivo).write_text(contenido, encoding='utf-8')
    if package is not None:
        (d / 'package.json').write_text(json.dumps(package), encoding='utf-8')
    if nvmrc is not None:
        (d / '.nvmrc').write_text(nvmrc, encoding='utf-8')
    return d


class TagNode(unittest.TestCase):
    def test_multistage_toma_el_primer_from(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine AS build\nRUN npm ci\nFROM node:22-alpine\n'})
            self.assertEqual(vacunas.tag_node(d), ('22-alpine', 'Dockerfile.test'))

    def test_test_tiene_prioridad_sobre_prod(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-permisos', {
                'Dockerfile.prod': 'FROM node:18-alpine AS build\n',
                'Dockerfile.test': 'FROM node:20 AS build\n',
            })
            self.assertEqual(vacunas.tag_node(d), ('20', 'Dockerfile.test'))

    def test_front_solo_con_dockerfile_prod(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'onboarding-psp', {'Dockerfile.prod': 'FROM node:20 AS builder\nFROM nginx:alpine AS production\n'})
            self.assertEqual(vacunas.tag_node(d), ('20', 'Dockerfile.prod'))

    def test_sin_from_node(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'api-testing-end2end', {'Dockerfile': 'FROM cypress/base:16\n'})
            self.assertEqual(vacunas.tag_node(d), (None, None))

    def test_pineado_por_digest_no_da_tag(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-x', {'Dockerfile': 'FROM node@sha256:abc123 AS build\n'})
            self.assertEqual(vacunas.tag_node(d), (None, None))


class DetectarRepos(unittest.TestCase):
    def test_detecta_solo_los_node_con_package_json(self):
        with TemporaryDirectory() as tmp:
            repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={'name': 'ms-psp'})
            repo(tmp, 'ms-faena', {'Dockerfile': 'FROM php:8.1-fpm\n'}, package=None)
            repo(tmp, 'web-cliente-react', {'Dockerfile.prod': 'FROM node:20 AS build\n'}, package={'name': 'web'})
            repo(tmp, 'sin-package', {'Dockerfile': 'FROM node:20\n'}, package=None)
            self.assertEqual(vacunas.detectar_repos(Path(tmp)), ['ms-psp', 'web-cliente-react'])


class NotasVersion(unittest.TestCase):
    def test_engines_coincide_no_genera_nota(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'},
                     package={'engines': {'node': '>= 22 <23'}})
            self.assertEqual(vacunas.notas_version(d, '22-alpine'), [])

    def test_engines_en_conflicto_genera_nota(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-x', {'Dockerfile': 'FROM node:20-alpine\n'},
                     package={'engines': {'node': '>= 22 <23'}})
            notas = vacunas.notas_version(d, '20-alpine')
            self.assertEqual(len(notas), 1)
            self.assertIn('engines.node', notas[0])
            self.assertIn('20-alpine', notas[0])

    def test_nvmrc_en_conflicto_genera_nota(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-x', {'Dockerfile': 'FROM node:22-alpine\n'}, package={}, nvmrc='18.19.1\n')
            notas = vacunas.notas_version(d, '22-alpine')
            self.assertEqual(len(notas), 1)
            self.assertIn('.nvmrc', notas[0])

    def test_package_json_ilegible_no_explota(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp) / 'ms-roto'
            d.mkdir()
            (d / 'Dockerfile').write_text('FROM node:22-alpine\n', encoding='utf-8')
            (d / 'package.json').write_text('{roto', encoding='utf-8')
            self.assertEqual(vacunas.notas_version(d, '22-alpine'), [])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest tests.test_vacunas -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vacunas'`

- [ ] **Step 3: Implementar la detección**

Crear `scripts/vacunas.py`:

```python
import json
import re
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


def detectar_repos(raiz):
    raiz = Path(raiz)
    nombres = []
    for d in sorted(p for p in raiz.iterdir() if p.is_dir()):
        if (d / 'package.json').is_file() and tag_node(d)[0]:
            nombres.append(d.name)
    return nombres


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
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest tests.test_vacunas -v`
Expected: PASS, 10 tests.

---

### Task 2: Normalizadores de npm audit y trivy

**Files:**
- Modify: `scripts/vacunas.py`
- Test: `tests/test_vacunas.py`

**Interfaces:**
- Consumes: nada de Task 1.
- Produces:
  - `normalizar_npm(data: dict) -> dict` → `{"critical": int, "high": int, "moderate": int, "low": int, "hallazgos": [...]}`, y `"error": str` si el reporte vino con error. Cada hallazgo: `{"paquete", "severidad", "advisory", "via", "fix_disponible", "fix_breaking"}`.
  - `normalizar_trivy_vuln(data: dict) -> dict` → `{"critical": int, "high": int, "medium": int, "low": int, "hallazgos": [...]}`, con hallazgos solo de severidad CRITICAL y HIGH. Cada hallazgo: `{"id", "paquete", "instalada", "fixada", "severidad"}`.
  - `normalizar_secretos(data: dict) -> list[dict]` → `[{"archivo", "linea", "tipo"}]`, nada más.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_vacunas.py`, antes del `if __name__`:

```python
AUDIT_OK = {
    'auditReportVersion': 2,
    'vulnerabilities': {
        'braces': {
            'name': 'braces', 'severity': 'high', 'isDirect': False,
            'via': [{'source': 1098094, 'name': 'braces',
                     'url': 'https://github.com/advisories/GHSA-grv7-fg5c-xmjg',
                     'severity': 'high', 'range': '<3.0.3'}],
            'effects': ['tsc-alias'], 'range': '<3.0.3',
            'fixAvailable': {'name': 'tsc-alias', 'version': '1.8.10', 'isSemVerMajor': False},
        },
        'tsc-alias': {
            'name': 'tsc-alias', 'severity': 'high', 'isDirect': True,
            'via': ['braces'], 'effects': [], 'range': '<=1.8.9',
            'fixAvailable': {'name': 'tsc-alias', 'version': '2.0.0', 'isSemVerMajor': True},
        },
        'js-yaml': {
            'name': 'js-yaml', 'severity': 'moderate', 'isDirect': False,
            'via': [{'source': 1, 'name': 'js-yaml',
                     'url': 'https://github.com/advisories/GHSA-8j8c-7jfh-h6hx',
                     'severity': 'moderate', 'range': '<3.13.1'}],
            'effects': [], 'range': '<3.13.1', 'fixAvailable': False,
        },
    },
    'metadata': {'vulnerabilities': {'info': 0, 'low': 1, 'moderate': 1, 'high': 2,
                                     'critical': 0, 'total': 4}},
}

TRIVY_VULN = {
    'Results': [
        {'Target': 'package-lock.json', 'Vulnerabilities': [
            {'VulnerabilityID': 'CVE-2024-4068', 'PkgName': 'braces', 'Severity': 'HIGH',
             'InstalledVersion': '3.0.2', 'FixedVersion': '3.0.3'},
            {'VulnerabilityID': 'CVE-2024-0001', 'PkgName': 'lodash', 'Severity': 'LOW',
             'InstalledVersion': '4.17.20', 'FixedVersion': '4.17.21'},
        ]},
        {'Target': 'otro', 'Vulnerabilities': None},
    ]
}

TRIVY_SECRET = {
    'Results': [
        {'Target': 'src/config.ts', 'Class': 'secret', 'Secrets': [
            {'RuleID': 'generic-api-key', 'Category': 'general', 'Severity': 'HIGH',
             'Title': 'Generic API Key AKIAIOSFODNN7EXAMPLE', 'StartLine': 14, 'EndLine': 14,
             'Match': 'const key = "AKIAIOSFODNN7EXAMPLE"',
             'Code': {'Lines': [{'Number': 14, 'Content': 'AKIAIOSFODNN7EXAMPLE'}]}},
        ]},
        {'Target': 'src/otro.ts', 'Class': 'secret', 'Secrets': None},
    ]
}


class NormalizarNpm(unittest.TestCase):
    def test_conteos_y_hallazgos(self):
        r = vacunas.normalizar_npm(AUDIT_OK)
        self.assertEqual((r['critical'], r['high'], r['moderate'], r['low']), (0, 2, 1, 1))
        self.assertEqual([h['paquete'] for h in r['hallazgos']], ['braces', 'tsc-alias', 'js-yaml'])
        self.assertNotIn('error', r)

    def test_campos_del_hallazgo(self):
        h = vacunas.normalizar_npm(AUDIT_OK)['hallazgos'][0]
        self.assertEqual(h, {'paquete': 'braces', 'severidad': 'high',
                             'advisory': 'GHSA-grv7-fg5c-xmjg', 'via': ['tsc-alias'],
                             'fix_disponible': True, 'fix_breaking': False})

    def test_fix_breaking_y_sin_fix(self):
        hallazgos = {h['paquete']: h for h in vacunas.normalizar_npm(AUDIT_OK)['hallazgos']}
        self.assertTrue(hallazgos['tsc-alias']['fix_breaking'])
        self.assertFalse(hallazgos['js-yaml']['fix_disponible'])
        self.assertIsNone(hallazgos['tsc-alias']['advisory'])

    def test_reporte_con_error_no_explota(self):
        r = vacunas.normalizar_npm({'error': {'code': 'ENOLOCK', 'summary': 'no lockfile'}})
        self.assertEqual((r['critical'], r['high'], r['moderate'], r['low']), (0, 0, 0, 0))
        self.assertEqual(r['hallazgos'], [])
        self.assertIn('ENOLOCK', r['error'])

    def test_json_vacio_no_explota(self):
        r = vacunas.normalizar_npm({})
        self.assertEqual(r['hallazgos'], [])
        self.assertEqual(r['high'], 0)


class NormalizarTrivy(unittest.TestCase):
    def test_conteos_y_solo_altos_en_hallazgos(self):
        r = vacunas.normalizar_trivy_vuln(TRIVY_VULN)
        self.assertEqual((r['critical'], r['high'], r['medium'], r['low']), (0, 1, 0, 1))
        self.assertEqual([h['id'] for h in r['hallazgos']], ['CVE-2024-4068'])

    def test_vulnerabilities_null_no_explota(self):
        self.assertEqual(vacunas.normalizar_trivy_vuln({'Results': [{'Target': 'x', 'Vulnerabilities': None}]}),
                         {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'hallazgos': []})

    def test_sin_results_no_explota(self):
        self.assertEqual(vacunas.normalizar_trivy_vuln({})['hallazgos'], [])

    def test_campos_del_hallazgo(self):
        h = vacunas.normalizar_trivy_vuln(TRIVY_VULN)['hallazgos'][0]
        self.assertEqual(h, {'id': 'CVE-2024-4068', 'paquete': 'braces', 'instalada': '3.0.2',
                             'fixada': '3.0.3', 'severidad': 'HIGH'})


class NormalizarSecretos(unittest.TestCase):
    def test_archivo_linea_y_tipo(self):
        self.assertEqual(vacunas.normalizar_secretos(TRIVY_SECRET),
                         [{'archivo': 'src/config.ts', 'linea': 14, 'tipo': 'generic-api-key'}])

    def test_el_valor_del_secreto_no_sale_en_ningun_campo(self):
        salida = json.dumps(vacunas.normalizar_secretos(TRIVY_SECRET))
        self.assertNotIn('AKIAIOSFODNN7EXAMPLE', salida)
        self.assertNotIn('Match', salida)

    def test_secrets_null_no_explota(self):
        self.assertEqual(vacunas.normalizar_secretos({'Results': [{'Target': 'x', 'Secrets': None}]}), [])
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest tests.test_vacunas -v`
Expected: FAIL — `AttributeError: module 'vacunas' has no attribute 'normalizar_npm'`

- [ ] **Step 3: Implementar los normalizadores**

Agregar a `scripts/vacunas.py`:

```python
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
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest tests.test_vacunas -v`
Expected: PASS, 22 tests.

---

### Task 3: Armado de los comandos de contenedor

**Files:**
- Modify: `scripts/vacunas.py`
- Test: `tests/test_vacunas.py`

**Interfaces:**
- Consumes: nada.
- Produces (todas devuelven `list[str]` argv, nunca un string de shell):
  - `TRIVY: str` = `'aquasec/trivy:0.58.1'`
  - `CACHE_TRIVY: str` = `'clarabella-trivy-cache'`
  - `cmd_audit(worktree: str, tag: str) -> list[str]`
  - `cmd_trivy_fs(worktree: str, trivy: str = TRIVY) -> list[str]`
  - `cmd_trivy_image(tag: str, trivy: str = TRIVY) -> list[str]`
  - `cmd_trivy_secret(worktree: str, trivy: str = TRIVY) -> list[str]`
  - `cmd_audit_fix(worktree: str, tag: str, uid: int, gid: int) -> list[str]`
  - `cmd_validar(worktree: str, tag: str) -> list[str]`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_vacunas.py`:

```python
class Comandos(unittest.TestCase):
    def test_audit_monta_read_only_y_usa_el_tag(self):
        cmd = vacunas.cmd_audit('/w/ms-psp', '22-alpine')
        self.assertEqual(cmd, ['docker', 'run', '--rm', '-v', '/w/ms-psp:/app:ro', '-w', '/app',
                               '-e', 'HOME=/tmp', '-e', 'npm_config_cache=/tmp/.npm',
                               'node:22-alpine', 'npm', 'audit', '--json'])

    def test_trivy_fs_usa_el_cache_y_salta_node_modules(self):
        cmd = vacunas.cmd_trivy_fs('/w/ms-psp')
        self.assertIn('-v', cmd)
        self.assertIn(f'{vacunas.CACHE_TRIVY}:/root/.cache/trivy', cmd)
        self.assertIn('/w/ms-psp:/src:ro', cmd)
        self.assertIn(vacunas.TRIVY, cmd)
        self.assertEqual(cmd[-8:], ['fs', '--scanners', 'vuln', '--skip-dirs', 'node_modules',
                                    '--format', 'json', '/src'])

    def test_trivy_image_no_monta_el_repo(self):
        cmd = vacunas.cmd_trivy_image('22-alpine')
        self.assertNotIn('/src:ro', ' '.join(cmd))
        self.assertEqual(cmd[-4:], ['image', '--format', 'json', 'node:22-alpine'])

    def test_trivy_secret_pide_el_scanner_secret(self):
        cmd = vacunas.cmd_trivy_secret('/w/ms-psp')
        self.assertIn('secret', cmd)
        self.assertEqual(cmd[-1], '/src')

    def test_fix_sin_force_con_package_lock_only_y_user(self):
        cmd = vacunas.cmd_audit_fix('/w/ms-psp', '22-alpine', 1000, 1000)
        self.assertNotIn('--force', cmd)
        self.assertIn('--package-lock-only', cmd)
        self.assertIn('--user', cmd)
        self.assertIn('1000:1000', cmd)
        self.assertIn('/w/ms-psp:/app', cmd)
        self.assertNotIn('/w/ms-psp:/app:ro', cmd)

    def test_validar_copia_adentro_y_usa_el_comando_del_prediff(self):
        cmd = vacunas.cmd_validar('/w/ms-psp', '22-alpine')
        self.assertIn('/w/ms-psp:/src:ro', cmd)
        guion = cmd[-1]
        self.assertIn('cp -a /src/. .', guion)
        self.assertIn('npm ci', guion)
        self.assertIn('npm run build', guion)
        self.assertIn('--maxWorkers=2', guion)
        self.assertIn('--workerIdleMemoryLimit=512MB', guion)

    def test_rutas_con_espacios_no_se_parten(self):
        cmd = vacunas.cmd_audit('/w/ms psp', '20')
        self.assertIn('/w/ms psp:/app:ro', cmd)
        self.assertEqual(len([a for a in cmd if 'ms psp' in a]), 1)

    def test_imagen_de_trivy_sobreescribible_y_nunca_latest(self):
        self.assertNotIn('latest', vacunas.TRIVY)
        self.assertIn('aquasec/trivy:9.9.9', vacunas.cmd_trivy_fs('/w/x', 'aquasec/trivy:9.9.9'))
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest tests.test_vacunas.Comandos -v`
Expected: FAIL — `AttributeError: module 'vacunas' has no attribute 'cmd_audit'`

- [ ] **Step 3: Implementar el armado de comandos**

Agregar a `scripts/vacunas.py`:

```python
TRIVY = 'aquasec/trivy:0.58.1'
CACHE_TRIVY = 'clarabella-trivy-cache'
TESTS_PREDIFF = 'npm run test -- --maxWorkers=2 --workerIdleMemoryLimit=512MB'


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


def cmd_validar(worktree, tag):
    guion = ('mkdir -p /work && cd /work && cp -a /src/. . && npm ci && '
             f'npm run build && {TESTS_PREDIFF}')
    return ['docker', 'run', '--rm', '-v', f'{worktree}:/src:ro', '-w', '/tmp',
            '-e', 'HOME=/tmp', '-e', 'npm_config_cache=/tmp/.npm',
            f'node:{tag}', 'sh', '-c', guion]
```

- [ ] **Step 4: Correr toda la suite**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest discover -s tests -v`
Expected: PASS, todo verde (30 tests de `test_vacunas` más los que ya había).

---

### Task 4: CLI del scan, con la ejecución inyectada

**Files:**
- Modify: `scripts/vacunas.py`
- Test: `tests/test_vacunas.py`

**Interfaces:**
- Consumes: todo lo de Tasks 1-3.
- Produces:
  - `escanear(worktree: str, repo_nombre: str, base: str, ejecutar, trivy: str = TRIVY) -> dict` — el JSON por repo de la spec. `ejecutar(cmd: list[str]) -> tuple[int, str]` devuelve `(returncode, stdout)`.
  - `comandos_fix(worktree: str, tag: str, uid: int, gid: int) -> list[str]` — las dos líneas de shell (fix y validación) ya armadas, para imprimir.
  - `main(argv: list[str]) -> int`
  - CLI: `--detectar [--raiz <dir>]` · `--worktree <path> --repo <nombre> [--base <rama>] [--out <dir>] [--trivy-image <img>]` · `--comandos --worktree <path>`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_vacunas.py`:

```python
class Escanear(unittest.TestCase):
    def _ejecutar(self, respuestas):
        llamadas = []

        def ejecutar(cmd):
            llamadas.append(cmd)
            for clave in ('audit', 'secret', 'image', 'fs'):
                if clave in cmd:
                    return respuestas.get(clave, (0, '{}'))
            return 0, '{}'

        return ejecutar, llamadas

    def test_arma_el_json_de_la_spec(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'bridge-node', {'Dockerfile.test': 'FROM node:22-alpine\n'},
                     package={'name': 'bridge-node'})
            ejecutar, llamadas = self._ejecutar({
                'audit': (1, json.dumps(AUDIT_OK)),
                'fs': (0, json.dumps(TRIVY_VULN)),
                'image': (0, json.dumps({'Results': []})),
                'secret': (0, json.dumps(TRIVY_SECRET)),
            })
            r = vacunas.escanear(str(d), 'bridge-node', 'master', ejecutar)
            self.assertEqual(r['repo'], 'bridge-node')
            self.assertEqual(r['node_tag'], '22-alpine')
            self.assertEqual(r['node_tag_origen'], 'Dockerfile.test')
            self.assertEqual(r['base'], 'master')
            self.assertEqual(r['npm']['high'], 2)
            self.assertEqual(r['imagen_base']['tag'], 'node:22-alpine')
            self.assertEqual(r['secretos'][0]['tipo'], 'generic-api-key')
            self.assertEqual(r['notas'], [])
            self.assertEqual(len(llamadas), 4)

    def test_sin_tag_de_node_no_corre_nada(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'api-testing-end2end', {'Dockerfile': 'FROM cypress/base:16\n'},
                     package={'name': 'e2e'})
            ejecutar, llamadas = self._ejecutar({})
            r = vacunas.escanear(str(d), 'api-testing-end2end', 'master', ejecutar)
            self.assertIsNone(r['node_tag'])
            self.assertIn('FROM node:', r['error'])
            self.assertEqual(llamadas, [])

    def test_trivy_que_falla_queda_como_error_no_como_vacio(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            ejecutar, _ = self._ejecutar({
                'audit': (0, json.dumps(AUDIT_OK)),
                'fs': (1, 'FATAL failed to download vulnerability DB'),
                'image': (1, 'FATAL failed to download vulnerability DB'),
                'secret': (1, 'FATAL failed to download vulnerability DB'),
            })
            r = vacunas.escanear(str(d), 'ms-psp', 'master', ejecutar)
            self.assertIn('error', r['trivy_lock'])
            self.assertIn('error', r['imagen_base'])
            self.assertIn('DB', r['trivy_lock']['error'])

    def test_salida_no_parseable_queda_como_error(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            ejecutar, _ = self._ejecutar({'audit': (1, 'npm ERR! code ENOLOCK')})
            r = vacunas.escanear(str(d), 'ms-psp', 'master', ejecutar)
            self.assertIn('error', r['npm'])
            self.assertIn('ENOLOCK', r['npm']['error'])


class ComandosFix(unittest.TestCase):
    def test_imprime_fix_y_validacion(self):
        lineas = vacunas.comandos_fix('/w/ms-psp', '22-alpine', 1000, 1000)
        self.assertEqual(len(lineas), 2)
        self.assertIn('--package-lock-only', lineas[0])
        self.assertNotIn('--force', lineas[0])
        self.assertIn('npm ci', lineas[1])


class Cli(unittest.TestCase):
    def test_detectar_imprime_los_repos(self):
        with TemporaryDirectory() as tmp:
            repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            repo(tmp, 'ms-faena', {'Dockerfile': 'FROM php:8.1\n'}, package={})
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = vacunas.main(['--detectar', '--raiz', tmp])
            self.assertEqual(rc, 0)
            self.assertEqual(buf.getvalue().split(), ['ms-psp'])

    def test_escanear_escribe_el_json_en_out(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            out = Path(tmp) / 'salida'
            out.mkdir()
            rc = vacunas.main(['--worktree', str(d), '--repo', 'ms-psp', '--out', str(out),
                               '--base', 'migracion-psp', '--dry-run'])
            self.assertEqual(rc, 0)
            datos = json.loads((out / 'ms-psp.json').read_text(encoding='utf-8'))
            self.assertEqual(datos['base'], 'migracion-psp')
            self.assertEqual(datos['node_tag'], '22-alpine')
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest tests.test_vacunas.Escanear -v`
Expected: FAIL — `AttributeError: module 'vacunas' has no attribute 'escanear'`

- [ ] **Step 3: Implementar `escanear`, `comandos_fix` y la CLI**

Agregar a `scripts/vacunas.py`:

```python
import argparse
import os
import shlex
import subprocess
import sys


def _ejecutar_real(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def _ejecutar_falso(cmd):
    return 0, '{}'


def _seccion(ejecutar, cmd, normalizar):
    rc, salida = ejecutar(cmd)
    try:
        return normalizar(json.loads(salida))
    except ValueError:
        return {'error': salida.strip()[-500:] or f'exit {rc} sin salida'}


def escanear(worktree, repo_nombre, base, ejecutar, trivy=TRIVY):
    tag, origen = tag_node(worktree)
    datos = {'repo': repo_nombre, 'node_tag': tag, 'node_tag_origen': origen, 'base': base}
    if not tag:
        datos['error'] = 'ningún Dockerfile declara FROM node:<tag>: fuera de alcance automático'
        datos['notas'] = []
        return datos
    npm = _seccion(ejecutar, cmd_audit(worktree, tag), normalizar_npm)
    lock = _seccion(ejecutar, cmd_trivy_fs(worktree, trivy), normalizar_trivy_vuln)
    base_img = _seccion(ejecutar, cmd_trivy_image(tag, trivy), normalizar_trivy_vuln)
    base_img['tag'] = f'node:{tag}'
    secretos = _seccion(ejecutar, cmd_trivy_secret(worktree, trivy), normalizar_secretos)
    datos['npm'] = npm
    datos['trivy_lock'] = lock
    datos['imagen_base'] = base_img
    datos['secretos'] = secretos if isinstance(secretos, list) else []
    if isinstance(secretos, dict):
        datos['secretos_error'] = secretos['error']
    datos['notas'] = notas_version(worktree, tag)
    return datos


def comandos_fix(worktree, tag, uid, gid):
    return [shlex.join(cmd_audit_fix(worktree, tag, uid, gid)),
            shlex.join(cmd_validar(worktree, tag))]


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
        for nombre in detectar_repos(a.raiz):
            print(nombre)
        return 0

    if not a.worktree:
        p.error('se necesita --worktree (o --detectar)')

    if a.comandos:
        tag, _ = tag_node(a.worktree)
        if not tag:
            print('sin FROM node:<tag>: fuera de alcance', file=sys.stderr)
            return 1
        for linea in comandos_fix(a.worktree, tag, os.getuid(), os.getgid()):
            print(linea)
        return 0

    ejecutar = _ejecutar_falso if a.dry_run else _ejecutar_real
    datos = escanear(a.worktree, a.repo or Path(a.worktree).name, a.base, ejecutar, a.trivy_image)
    texto = json.dumps(datos, ensure_ascii=False, indent=2)
    if a.out:
        destino = Path(a.out) / f"{datos['repo']}.json"
        destino.write_text(texto + '\n', encoding='utf-8')
        print(destino)
    else:
        print(texto)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

Mover los `import` nuevos arriba, con los que ya estaban.

- [ ] **Step 4: Correr toda la suite**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest discover -s tests -v`
Expected: PASS, todo verde.

- [ ] **Step 5: Probar la CLI a mano contra un repo real (sin Docker)**

Run: `cd /home/marcos/projects/dcac-ia-context && python3 /home/marcos/projects/clarabella/scripts/vacunas.py --detectar --raiz microservicios`
Expected: lista con `apigateway-psp`, `bridge-node`, `dcp-frontend`, `gestor-cuentas-mfe`, `ms-compliance`, `ms-multimedia-psp`, `ms-permisos`, `ms-psp`, `onboarding-psp`, `web-cliente-react` (y sin `api-testing-end2end`, que es cypress).

Run: `python3 /home/marcos/projects/clarabella/scripts/vacunas.py --comandos --worktree microservicios/ms-psp`
Expected: dos líneas; la primera con `--package-lock-only` y sin `--force`.

---

### Task 5: El agente Veterinario

**Files:**
- Create: `agents/veterinario.md`
- Modify: `tests/test_agentes.py:18` (dict `ROLES`)

**Interfaces:**
- Consumes: `scripts/vacunas.py --comandos` (Task 4).
- Produces: el tipo de agente `clarabella:veterinario`, que la skill de Task 6 despacha.

- [ ] **Step 1: Agregar el rol al test y verificar que falla**

En `tests/test_agentes.py`, agregar al dict `ROLES`, después de `'revisor'`:

```python
    'veterinario': ('sonnet', 'medium'),
```

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest tests.test_agentes -v`
Expected: FAIL — `test_estan_todos_los_roles` y `test_modelo_y_esfuerzo_del_spec` (no existe `agents/veterinario.md`).

- [ ] **Step 2: Escribir el agente**

Crear `agents/veterinario.md`:

```markdown
---
name: veterinario
description: Veterinario de vacunar-repos — vacuna un repo Node: aplica el fix seguro de npm audit en su worktree, lo valida con los tests del repo, y reporta lo que queda.
model: sonnet
effort: medium
disallowedTools: Agent
---

Sos el Veterinario de **un** repo Node. Trabajás en el worktree que te pasaron, nunca en
`microservicios/<repo>`.

Lo que recibís: el nombre del repo, el path del worktree, la rama base, y el path del JSON
de scan que armó `vacunas.py`. Leé ese JSON: **no vuelvas a correr el scan**.

## Lo que hacés

1. Pedí los comandos exactos con
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vacunas.py --comandos --worktree <worktree>`.
   Son dos: el fix y la validación. Usá esos, no los reescribas.
2. Corré el fix. Toca `package-lock.json` (y `package.json` si hace falta), nada más.
3. Volvé a auditar (`vacunas.py --worktree <worktree> --repo <repo> --out <dir>` sobre el
   mismo directorio de salida, con otro nombre) y compará conteos: eso es lo que bajó.
4. Corré la validación. Si no hay script `build` o `test` en el `package.json`, decilo y
   seguí.
5. Si los tests quedan rojos, corré la validación otra vez con el lock original
   (`git -C <worktree> stash` y después `git -C <worktree> stash pop`):
   - ya estaba rojo → el fix queda, y la validación se reporta como no concluyente;
   - lo rompió el fix → `git -C <worktree> checkout -- package-lock.json package.json` y el
     hallazgo pasa a PENDIENTES con el motivo.
6. Si `npm ci` falla en las dos corridas, revertí el lock: sin validación no se entrega un
   lock nuevo.

## Lo que no hacés nunca

- `npm audit fix --force`, ni ningún bump breaking.
- Cambiar la versión de node, el `FROM`, o la imagen base.
- Agregar `overrides` o `resolutions` en `package.json`.
- `.trivyignore`, `npm audit --omit=dev`, o cualquier forma de silenciar un hallazgo.
- Tocar código de producción, cambiar tests, o commitear.
- Imprimir el valor de un secreto: archivo, línea y tipo, nada más.

Todo lo de esta lista que parezca necesario es una **duda**, no una decisión tuya.

## Lo que devolvés

```
ARTEFACTO: <repo> → <n> vulns resueltas (C:<n> H:<n> M:<n> L:<n>), lock actualizado | sin cambios
VALIDACIÓN: npm ci <OK|falla> · build <OK|falla|sin script> · tests <n passed|RED|no concluyente|sin script>
PENDIENTES:
  - [P1] <paquete> <advisory> <severidad> · vía <cadena> · <por qué no se arregló>
  - [P2] imagen base node:<tag> · <n> HIGH · bumpear el FROM está fuera de alcance
  - [P3] secreto en <archivo>:<línea> · <tipo>
DUDAS:
  - [D1] <decisión que requiere al usuario> · bloqueante | no bloqueante
ESTADO: completo | sin-cambios | frenado-por-duda | frenado-por-tests
```
```

- [ ] **Step 3: Correr los tests de agentes y referencias**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest tests.test_agentes tests.test_referencias -v`
Expected: PASS.

---

### Task 6: La skill `vacunar-repos`

**Files:**
- Create: `skills/vacunar-repos/SKILL.md`

**Interfaces:**
- Consumes: `scripts/vacunas.py` (Tasks 1-4), `agents/veterinario.md` (Task 5), y las skills existentes `clarabella:mostrar-diff` y `clarabella:enviar-review`.
- Produces: la skill `clarabella:vacunar-repos`, referenciada por la tabla de Task 7.

- [ ] **Step 1: Escribir la skill**

Crear `skills/vacunar-repos/SKILL.md`:

```markdown
---
name: vacunar-repos
description: Usar cuando hay que buscar y arreglar vulnerabilidades de dependencias en los repos Node del workspace dcac-ia-context — scan con npm audit y trivy en la versión de node que declara cada Dockerfile, fix seguro, validación con los tests del repo y diff por repo. Triggers — "vacuná los repos", "buscá vulnerabilidades en los repos node", "el prediff está rojo por npm audit", "pasá trivy por los microservicios". NO usar para repos PHP, ni para vulnerabilidades de código propio (SAST).
---

# Vacunar repos

Escanea vulnerabilidades en los repos **Node** del workspace, aplica **solo el fix seguro**,
lo valida con los tests del repo, y deja el diff listo para que el usuario decida el envío.

El objetivo concreto: que el prediff de Jenkins (`isolated-npm-unittest`, que corta con
`npm audit` HIGH o CRITICAL incluyendo devDependencies) no sea el lugar donde se descubre una
vulnerabilidad.

## Lo que esta skill NO hace

Nada de esto se decide acá: son **dudas** para el usuario.

- `npm audit fix --force` o cualquier bump breaking.
- Cambiar la versión de node, el `FROM`, o la imagen base.
- `overrides` / `resolutions` en `package.json`.
- `.trivyignore`, `npm audit --omit=dev`, o silenciar un hallazgo de cualquier forma.
- Tocar código de producción.

Tampoco entra misconfig de Dockerfile (`trivy config`), SAST, ni repos PHP.

## Antes de arrancar

- **Docker tiene que estar corriendo.** Si no, hard stop: todo (node y trivy) va en
  contenedores efímeros, no hay nada instalado en el host.
- La primera corrida baja la DB de trivy al volumen `clarabella-trivy-cache`. Tarda; después
  se reusa.

## Paso 0 — alcance

Si el usuario nombró repos, son esos. Si dijo "todos":

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vacunas.py --detectar --raiz microservicios
```

Informá los que quedan afuera, no los adivines: sin `FROM node:` en ningún Dockerfile (ej.
`api-testing-end2end`, que corre sobre `cypress/base:16`), o sin `package-lock.json`.

## Paso 1 — preparar (por repo, en paralelo)

1. `git -C microservicios/<repo> status --porcelain`. Con cambios sin commitear → **frená
   ese repo** y avisá cuál. No hagas stash ni descartes: ese trabajo es del usuario.
2. Rama base al día en el canónico: `master`, salvo excepción conocida (`ms-psp` →
   `migracion-psp`). Si la base no está clara, preguntá; no asumas `main`.
3. Worktree del ticket-menos-ticket:
   `git -C microservicios/<repo> worktree add ../../.worktrees/vacuna-AAAA-MM-DD/<repo> -b vacuna-AAAA-MM-DD <base>`.
   Si ya existe, reusalo.

El canónico se queda en su rama base, solo lectura. Que el worktree sea limpio es a
propósito: el scan de secretos ve solo contenido versionado, así que los `.env` locales no
pueden terminar en el informe.

## Paso 2 — scan (sin tokens)

Un repo por invocación, hasta **3 en paralelo** (la VM de Docker tiene ~3,6 GiB):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vacunas.py \
  --worktree .worktrees/vacuna-AAAA-MM-DD/<repo> --repo <repo> --base <base> \
  --out <scratchpad>/vacuna-AAAA-MM-DD
```

Escribe un JSON chico por repo. **No lo leas entero**: es el input del Veterinario.

Si el JSON de un repo trae `"error"` en `trivy_lock` o `imagen_base` (típico: la DB no se
pudo bajar), no lo trates como "sin vulnerabilidades" — es un scan incompleto y se reporta
como tal.

## Paso 3 — un Veterinario por repo

Despachá `clarabella:veterinario` en tandas de 3, uno por repo. A cada uno pasale: nombre
del repo, path del worktree, rama base, y el path de su JSON de scan. Devuelven el contrato
de su agente (ARTEFACTO / VALIDACIÓN / PENDIENTES / DUDAS / ESTADO).

## Paso 4 — consolidar en el chat

Una tabla, una fila por repo: resueltas por severidad, pendientes, imagen base, secretos,
estado de la validación. **Sin archivo de informe.**

Juntá las dudas de **todos** los repos y preguntá en **una sola ronda** con
`AskUserQuestion`. Un secreto se nombra por archivo, línea y tipo — el valor no se imprime
nunca.

## Paso 5 — diff

Por cada repo con cambios:

```bash
python3 -u ${CLAUDE_PLUGIN_ROOT}/skills/mostrar-diff/serve.py \
  --repo .worktrees/vacuna-AAAA-MM-DD/<repo> --base <base> --ticket vacuna-AAAA-MM-DD \
  > /tmp/diff-vacuna-<repo>.log 2>&1 &
disown
```

Pasale las URLs al usuario. Los repos sin cambios se nombran y listo.

## Paso 6 — envío (gateado)

**Solo con el OK explícito del usuario en el chat.** No lo infieras de que el diff esté
lindo.

Con el OK, invocá `clarabella:enviar-review` por repo, en paralelo. Particularidades de esta
corrida:

- La branch es `vacuna-AAAA-MM-DD`, no `T#####`.
- `Maniphest Tasks: T#####` solo si el usuario te pasa el ticket en ese momento; si no, el
  campo se omite entero.
- Reviewers los decide el usuario; no se inventan.
- Un error de `arc`, un conflicto o un prompt interactivo **frena ese repo** y queda para el
  usuario. Los demás siguen.

## Paso 7 — limpieza

Worktrees sin cambios: `git -C microservicios/<repo> worktree remove <path>` y borrar la
branch. Los que ya tienen diff enviado se dejan: el land es del usuario.

## Errores comunes

- **Tratar un scan con error de trivy como "sin vulnerabilidades"** → es incompleto, decilo.
- **Leer el JSON de scan completo en la sesión principal** → para eso está el Veterinario;
  acá solo se consolida su contrato.
- **Correr el fix en `microservicios/<repo>`** → va en el worktree; el canónico es lectura.
- **Asumir `master` en `ms-psp`** → su base es `migracion-psp`.
- **Dar por aprobado el envío porque los tests pasaron** → el gate es la palabra del usuario.
- **Despachar los 10 repos a la vez** → tandas de 3; la VM de Docker se queda sin memoria y
  se lleva puesta la DB compartida.
```

- [ ] **Step 2: Correr los tests de referencias**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest tests.test_referencias -v`
Expected: PASS (las referencias `clarabella:veterinario`, `clarabella:mostrar-diff` y `clarabella:enviar-review` existen todas).

---

### Task 7: Integración en el plugin

**Files:**
- Modify: `skills/clarabella/SKILL.md` (tabla "A qué skill va cada pedido")
- Modify: `README.md` (tabla de skills, tabla de scripts, tabla de roles)
- Modify: `.claude-plugin/plugin.json` (versión)

**Interfaces:**
- Consumes: Tasks 4, 5 y 6.
- Produces: nada que consuma otra tarea.

- [ ] **Step 1: Agregar la fila a la tabla de la skill de entrada**

En `skills/clarabella/SKILL.md`, en la tabla "A qué skill va cada pedido", después de la fila de `leer-db`:

```markdown
| Buscar / arreglar vulnerabilidades en los repos Node, "vacuná los repos", "el prediff está rojo por npm audit" | `clarabella:vacunar-repos` |
```

- [ ] **Step 2: Agregar las filas al README**

En la tabla `## Skills`, después de la fila de `leer-db`:

```markdown
| `vacunar-repos` | Scan de vulnerabilidades de los repos Node (npm audit + trivy), fix seguro validado y diff por repo |
```

En la tabla de `### Scripts`, al final:

```markdown
| `vacunas.py --worktree … --repo … --out …` | Scan de un repo Node en contenedores efímeros (npm audit + trivy fs/image/secret) normalizado a JSON chico; `--detectar` lista los repos Node, `--comandos` imprime el fix y la validación |
```

En la tabla `## Roles de resolver-proyecto`, nada: el Veterinario no es un rol de ese flujo. Agregarlo en su lugar al final de la sección `## Skills`, como nota de una línea:

```markdown
`vacunar-repos` despacha un **Veterinario** (sonnet · medio) por repo.
```

En la tabla de requisitos (`## Requisitos`), agregar Docker ya está; sumar trivy a la línea de herramientas:

```markdown
Herramientas que usan las skills: `git`, Docker (también para `trivy`, que no se instala en
el host), `python3` (para `mostrar-diff`), Arcanist
```

- [ ] **Step 3: Subir la versión del plugin**

En `.claude-plugin/plugin.json`, `"version": "0.6.0"` → `"version": "0.7.0"`.

- [ ] **Step 4: Correr toda la suite**

Run: `cd /home/marcos/projects/clarabella && python3 -m unittest discover -s tests -v`
Expected: PASS, todo verde.

- [ ] **Step 5: Verificación final a mano**

Run: `cd /home/marcos/projects/clarabella && ls skills/vacunar-repos/SKILL.md agents/veterinario.md scripts/vacunas.py tests/test_vacunas.py && python3 -c "import json;print(json.load(open('.claude-plugin/plugin.json'))['version'])"`
Expected: los cuatro archivos y `0.7.0`.

Avisarle al usuario que falta commitear y, si quiere distribuirlo, `/plugin marketplace update clarabella` después del push. Git lo maneja él.
