# Revisión en vez de juicio — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar `juicio-ticket` por chequeos determinísticos (trazabilidad, reglas críticas, hechos) y una revisión sonnet de una pasada (`revisar-ticket`), y llevar Clarabella a 0.5.0.

**Architecture:** Tres scripts Python stdlib en `scripts/` (0 tokens) que producen archivos de texto en `revision/` de la carpeta del ticket; una skill nueva que los corre y despacha un revisor con entrada cerrada; las skills del flujo (`resolver-ticket`, `ciclo-ticket`, generativas, `baqueano`, `cronista`) se ajustan para usar `revision/` y los IDs `CA#`.

**Tech Stack:** Python 3.12 (stdlib: `re`, `argparse`, `subprocess`, `tempfile`, `unittest`), git, Markdown (skills de Claude Code).

**Spec:** `docs/specs/2026-10-07-revision-en-vez-de-juicio.md`

## Global Constraints

- Repo: `/home/marcos/projects/clarabella`. Todos los paths del plan son relativos a esa raíz.
- Versión objetivo: `0.5.0` en `.claude-plugin/plugin.json`.
- Scripts sin dependencias fuera de la stdlib de Python; se invocan como `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py`.
- Tests: `python3 -m unittest discover -s tests -v` desde la raíz del repo.
- Revisor: subagente **nuevo**, `model: "sonnet"`, **una pasada**, **hasta 10 hallazgos**, cada uno con cita a una fuente; lo que no tiene fuente no se reporta.
- Ningún paso de calidad retoma al agente del plan.
- Criterios: `CA1…CAn` en `spec.md` § `## Criterios de aceptación`, con el formato `- [ ] **CA1** — <texto>`.
- Plan: cada `## Parte N — <repo>` lleva una línea que empieza exactamente con `Cubre: ` seguida de los `CA#` separados por coma.
- Tests: la tabla de `## Tabla de casos de prueba` empieza con las columnas `| ID | Criterio |`; los casos de regresión llevan `regresión` en `Criterio`.
- Cronista: sigue en `sonnet`.
- Carpeta del ticket: `juicio/` pasa a `revision/`.
- Textos de las skills en español rioplatense, mismo tono y densidad que las skills vecinas.
- Commits: terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Spec con criterios sin numerar** (`- [ ] texto` como hoy): `trazabilidad.py` tiene que salir con 2 y decir qué falta, nunca "OK". → test en Task 1.
2. **Celda de la tabla de casos con `|` dentro de un curl** (`` `curl … | jq` ``): no tiene que correr las columnas ID/Criterio. → test en Task 1.
3. **Archivos nuevos sin trackear en el worktree** (la implementación crea archivos y no commitea): `reglas.py` y `hechos.py` los tienen que ver, y el index del repo no se toca. → tests en Task 2 y Task 3.
4. **Tabla compartida por dos servicios** (`dcac.negocios`, de ms-faena y ms-invernada) y **tabla citada sin esquema** (`$table = 'compra_inmediata_faena'`): la primera no alerta, la segunda sí. → tests en Task 2.
5. **`registro.md` con filas sin duración/tokens** (subagente en curso, dato no informado): se cuentan como "sin registro", nunca como 0. → test en Task 3.

---

## File Structure

| Archivo | Responsabilidad |
|---------|-----------------|
| `scripts/trazabilidad.py` | Cruza `CA#` de spec con `Cubre:` del plan y columna `Criterio` de tests |
| `scripts/reglas.py` | Alertas de reglas críticas sobre el diff de un worktree (incluye sin trackear); `--snapshot` devuelve el tree del estado actual |
| `scripts/hechos.py` | Arma `revision/hechos.md` para el Cronista: economía, verificación, repos, revisiones, decisiones textuales |
| `tests/test_trazabilidad.py`, `tests/test_reglas.py`, `tests/test_hechos.py` | Tests `unittest` de cada script |
| `skills/revisar-ticket/SKILL.md` | Skill nueva: chequeos + revisor + corrección |
| `skills/juicio-ticket/`, `skills/ensayar-juicio/` | Se eliminan |
| Resto de `skills/*/SKILL.md`, `README.md`, `.claude-plugin/plugin.json` | Ajustes según el spec |

---

### Task 0: Línea de base 0.4.0

La 0.4.0 está sin commitear. Commitearla primero hace que el diff de la 0.5.0 sea revisable.
**Requiere el OK explícito de Marcos antes de commitear.**

- [ ] **Step 1: Ver el estado**

Run: `git -C /home/marcos/projects/clarabella status --short`
Expected: los 13 modificados/borrados y 7 directorios sin trackear de la 0.4.0, más `docs/`.

- [ ] **Step 2: Commitear la 0.4.0 (sin `docs/`)**

```bash
cd /home/marcos/projects/clarabella
git add .claude-plugin README.md skills
git commit -m "Clarabella 0.4.0: juicio, escribano, baqueano, ciclo, cronista y bajar-entorno

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 3: Commitear spec y plan**

```bash
git add docs
git commit -m "Spec y plan: revisión en vez de juicio (0.5.0)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 1: `scripts/trazabilidad.py`

**Files:**
- Create: `scripts/trazabilidad.py`
- Test: `tests/test_trazabilidad.py`

**Interfaces:**
- Produces: CLI `python3 scripts/trazabilidad.py <carpeta del ticket>`. Stdout: una línea por tipo de problema (`<título>: a, b`) o `OK: N criterios, P Partes, C casos`. Exit 0 limpio, 1 con huecos, 2 error de entrada (mensaje `ERROR: …` en stderr).

- [ ] **Step 1: Escribir los tests**

`tests/test_trazabilidad.py`:

```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'trazabilidad.py'

SPEC = """# T1 — Alta de recurso

## Criterios de aceptación

- [ ] **CA1** — Crea el recurso.
- [ ] **CA2** — Rechaza duplicados.

## Decisiones de contrato

- CA9 se menciona acá pero no es un criterio.
"""

PLAN = """# Plan

## Parte 1 — ms-a
Cubre: CA1, CA2

Cambios.

## Verificación
"""

TESTS = """# Tests

## Tabla de casos de prueba

| ID | Criterio | Precondición | Acción | Esperado | Código | Esperado en RED |
|---|---|---|---|---|---|---|
| T01 | CA1 | nada | `curl -s x | jq .id` | 201 | 201 | falla |
| T02 | CA2 | T01 | repetir | 409 | 409 | falla |
| T03 | regresión | nada | listar | 200 | 200 | pasa |

## Preparación de datos de prueba
"""


def correr(spec=SPEC, plan=PLAN, tests=TESTS):
    with tempfile.TemporaryDirectory() as carpeta:
        for nombre, texto in (('spec.md', spec), ('plan.md', plan), ('tests.md', tests)):
            if texto is not None:
                Path(carpeta, nombre).write_text(texto, encoding='utf-8')
        r = subprocess.run([sys.executable, str(SCRIPT), carpeta], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


class Trazabilidad(unittest.TestCase):
    def test_todo_cierra(self):
        rc, out = correr()
        self.assertEqual(rc, 0, out)
        self.assertIn('OK: 2 criterios, 1 Partes, 3 casos', out)

    def test_criterio_sin_parte(self):
        rc, out = correr(plan=PLAN.replace('Cubre: CA1, CA2', 'Cubre: CA1'))
        self.assertEqual(rc, 1)
        self.assertIn('CA sin Parte en plan.md: CA2', out)

    def test_parte_sin_linea_cubre(self):
        rc, out = correr(plan=PLAN.replace('Cubre: CA1, CA2\n', ''))
        self.assertEqual(rc, 1)
        self.assertIn('Partes sin línea Cubre: en plan.md: Parte 1 — ms-a', out)

    def test_criterio_sin_caso(self):
        rc, out = correr(tests=TESTS.replace('| T02 | CA2 |', '| T02 | CA1 |'))
        self.assertEqual(rc, 1)
        self.assertIn('CA sin caso en tests.md: CA2', out)

    def test_caso_sin_criterio(self):
        rc, out = correr(tests=TESTS.replace('| T03 | regresión |', '| T03 |  |'))
        self.assertEqual(rc, 1)
        self.assertIn('Casos sin criterio en tests.md: T03', out)

    def test_ca_citado_que_no_existe(self):
        rc, out = correr(plan=PLAN.replace('Cubre: CA1, CA2', 'Cubre: CA1, CA2, CA7'))
        self.assertEqual(rc, 1)
        self.assertIn('CA citados que no existen en spec.md: CA7 (plan.md · Parte 1 — ms-a)', out)

    def test_ca10_no_cuenta_como_ca1(self):
        spec = SPEC.replace('- [ ] **CA2** — Rechaza duplicados.',
                            '- [ ] **CA2** — Rechaza duplicados.\n- [ ] **CA10** — Lista.')
        plan = PLAN.replace('Cubre: CA1, CA2', 'Cubre: CA2, CA10')
        tests = TESTS.replace('| T03 | regresión |', '| T03 | CA10 |')
        rc, out = correr(spec=spec, plan=plan, tests=tests)
        self.assertEqual(rc, 1)
        self.assertIn('CA sin Parte en plan.md: CA1\n', out)

    def test_pipe_dentro_de_un_curl_no_corre_columnas(self):
        rc, out = correr()
        self.assertNotIn('Casos sin criterio', out)
        self.assertEqual(rc, 0, out)

    def test_spec_sin_numerar_es_error(self):
        spec = SPEC.replace('**CA1** — ', '').replace('**CA2** — ', '')
        rc, out = correr(spec=spec)
        self.assertEqual(rc, 2)
        self.assertIn('spec.md no tiene criterios numerados', out)
        self.assertNotIn('OK', out)

    def test_tabla_sin_columna_criterio_es_error(self):
        tests = TESTS.replace('| ID | Criterio |', '| ID | Prioridad |')
        rc, out = correr(tests=tests)
        self.assertEqual(rc, 2)
        self.assertIn('"| ID | Criterio |"', out)

    def test_falta_archivo(self):
        rc, out = correr(plan=None)
        self.assertEqual(rc, 2)
        self.assertIn('falta plan.md', out)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `python3 -m unittest tests.test_trazabilidad -v`
Expected: FAIL/ERROR en todos (el script no existe: rc 2 con "can't open file").

- [ ] **Step 3: Implementar**

`scripts/trazabilidad.py`:

```python
#!/usr/bin/env python3
"""Trazabilidad de un ticket: cruza los criterios CA# de spec.md con plan.md y tests.md.

Uso: trazabilidad.py <carpeta del ticket>

- spec.md: criterios en "## Criterios de aceptación" (- [ ] **CA1** — ...).
- plan.md: cada "## Parte N — <repo>" con una línea "Cubre: CA1, CA3".
- tests.md: "## Tabla de casos de prueba" que empieza con "| ID | Criterio |".

Salida: 0 si todo cierra, 1 si hay huecos, 2 si falta un archivo o el formato no es el esperado.
"""
import re
import sys
from pathlib import Path

CA = re.compile(r'\bCA(\d+)\b')
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
    partes = partes_del_plan(textos['plan.md'])
    casos = casos_de_tests(textos['tests.md'])

    cubiertos_plan, cubiertos_tests = set(), set()
    sin_cubre, sin_criterio, inexistentes = [], [], []
    for parte, cas, tiene_cubre in partes:
        if not tiene_cubre:
            sin_cubre.append(parte)
        cubiertos_plan |= cas & criterios
        inexistentes += [f'{ca} (plan.md · {parte})' for ca in sorted(cas - criterios, key=orden)]
    for caso, criterio in casos:
        cas = ids(criterio)
        if not cas and criterio.lower() not in ('regresión', 'regresion'):
            sin_criterio.append(caso)
        cubiertos_tests |= cas & criterios
        inexistentes += [f'{ca} (tests.md · {caso})' for ca in sorted(cas - criterios, key=orden)]

    problemas = [
        ('CA sin Parte en plan.md', sorted(criterios - cubiertos_plan, key=orden)),
        ('Partes sin línea Cubre: en plan.md', sin_cubre),
        ('CA sin caso en tests.md', sorted(criterios - cubiertos_tests, key=orden)),
        ('Casos sin criterio en tests.md', sin_criterio),
        ('CA citados que no existen en spec.md', inexistentes),
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `python3 -m unittest tests.test_trazabilidad -v`
Expected: 11 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/trazabilidad.py tests/test_trazabilidad.py
git commit -m "trazabilidad.py: cruza criterios CA# con plan y tests

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `scripts/reglas.py`

**Files:**
- Create: `scripts/reglas.py`
- Test: `tests/test_reglas.py`

**Interfaces:**
- Produces:
  - CLI `python3 scripts/reglas.py --worktree <ruta> --ownership <database-ownership.md> [--ms <nombre>] [--base <commit|tree>]`. Stdout: `<archivo>:<línea> · <regla> · <detalle>` por alerta, o `OK: sin alertas en <ms> (base <base>)`. Exit 0 / 1 / 2. Reglas: `tabla-ajena`, `llamada-entre-ms`, `estado-en-clase`. `--ms` default: nombre del directorio del worktree. `--base` default `master`.
  - CLI `python3 scripts/reglas.py --snapshot --worktree <ruta>`: imprime el sha del tree del estado actual (con sin trackear).
  - Función importable `snapshot(worktree) -> str` (la usa `hechos.py`).

- [ ] **Step 1: Escribir los tests**

`tests/test_reglas.py`:

```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'reglas.py'

OWNERSHIP = """# Ownership de tablas

## Tablas por servicio

### ms-faena
- `dcac.negocios` — Tabla central de lotes (compartida con ms-invernada)
- `dcac.cobros_faena` — Cobros, discriminados por el campo `dinamica`

### ms-invernada
- `dcac.negocios` — Compartida con ms-faena
- `dcac.invernadas` — Propia

### ms-compra_inmediata
- `negocios.compra_inmediata_faena` — CI de faena
"""

SERVICIO_CON_ESTADO = """<?php
class Servicio
{
    private array $cache = [];

    public function __construct(private Repo $repo)
    {
        $this->cache = [];
    }

    public function buscar(int $id)
    {
        $this->cache[$id] = $this->repo->find($id);
        return $this->cache[$id];
    }
}
"""

MODELO = """<?php
class Lote extends Model
{
    public function cerrar()
    {
        $this->estado = 'cerrado';
    }
}
"""


class Reglas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ownership = Path(self.tmp.name, 'ownership.md')
        self.ownership.write_text(OWNERSHIP, encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, wt, *args):
        return subprocess.run(['git', '-C', str(wt), *args], check=True,
                              capture_output=True, text=True).stdout

    def repo(self, nombre):
        wt = Path(self.tmp.name, nombre)
        wt.mkdir()
        self.git(wt, 'init', '-q', '-b', 'master')
        self.git(wt, 'config', 'user.email', 't@t')
        self.git(wt, 'config', 'user.name', 't')
        (wt / 'README.md').write_text('base\n')
        self.git(wt, 'add', '-A')
        self.git(wt, 'commit', '-q', '-m', 'base')
        return wt

    def escribir(self, wt, ruta, texto):
        archivo = wt / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding='utf-8')

    def correr(self, wt, *extra):
        r = subprocess.run([sys.executable, str(SCRIPT), '--worktree', str(wt),
                            '--ownership', str(self.ownership), *extra],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_sin_cambios_es_ok(self):
        wt = self.repo('ms-faena')
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)
        self.assertIn('OK: sin alertas en ms-faena (base master)', out)

    def test_tabla_ajena_en_archivo_nuevo_sin_trackear(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Repo.php', "<?php\n$r = Db::table('dcac.invernadas')->get();\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 1, out)
        self.assertIn('app/Repo.php:2 · tabla-ajena · invernadas es de ms-invernada', out)

    def test_no_toca_el_index(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Repo.php', "<?php\n$r = Db::table('dcac.invernadas')->get();\n")
        self.correr(wt)
        self.assertIn('?? app/', self.git(wt, 'status', '--porcelain'))

    def test_tabla_compartida_no_alerta(self):
        wt = self.repo('ms-invernada')
        self.escribir(wt, 'app/Repo.php', "<?php\n$sql = 'SELECT * FROM dcac.negocios WHERE id = ?';\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)

    def test_tabla_sin_esquema_se_detecta(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Model/Ci.php',
                      "<?php\nclass Ci extends Model\n{\n    protected ?string $table = 'compra_inmediata_faena';\n}\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 1, out)
        self.assertIn('tabla-ajena · compra_inmediata_faena es de ms-compra_inmediata', out)

    def test_estado_en_clase_fuera_del_constructor(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Service/Servicio.php', SERVICIO_CON_ESTADO)
        rc, out = self.correr(wt)
        self.assertEqual(rc, 1, out)
        self.assertIn('app/Service/Servicio.php:13 · estado-en-clase', out)
        self.assertNotIn('Servicio.php:8 ', out)

    def test_modelo_no_alerta_estado(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Model/Lote.php', MODELO)
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)

    def test_llamada_entre_ms(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Client.php', "<?php\n$host = env('INVERNADA_SERVICE_HOST');\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 1, out)
        self.assertIn('app/Client.php:2 · llamada-entre-ms', out)

    def test_el_gateway_puede_llamar_a_los_ms(self):
        wt = self.repo('apigateway')
        self.escribir(wt, 'app/Client.php', "<?php\n$host = env('INVERNADA_SERVICE_HOST');\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)

    def test_snapshot_y_base_para_el_delta(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Repo.php', "<?php\n$r = Db::table('dcac.invernadas')->get();\n")
        r = subprocess.run([sys.executable, str(SCRIPT), '--snapshot', '--worktree', str(wt)],
                           capture_output=True, text=True, check=True)
        tree = r.stdout.strip()
        self.assertRegex(tree, r'^[0-9a-f]{40}$')
        rc, out = self.correr(wt, '--base', tree)
        self.assertEqual(rc, 0, out)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `python3 -m unittest tests.test_reglas -v`
Expected: FAIL en todos (el script no existe).

- [ ] **Step 3: Implementar**

`scripts/reglas.py`:

```python
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
LLAMADA_MS = re.compile(r'\b[A-Z][A-Z0-9_]*_SERVICE_HOST\b|https?://ms-[\w-]+|\bms-[\w-]+:\d{2,5}\b')
ASIGNACION = re.compile(r'(?:\$this->|self::\$|static::\$)(\w+)\s*(?:\[[^\]]*\]\s*)*'
                        r'(?:=(?![=>])|\.=|\+=|-=|\*=|\?\?=|\+\+|--)')
FUNCION = re.compile(r'\bfunction\s+&?(\w+)\s*\(')
MODELO = re.compile(r'\bextends\s+\w*Model\b')
ES_TEST = re.compile(r'(^|/)tests?/|Test\.php$')


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
        for patron in REF_TABLA:
            for tabla in patron.findall(texto):
                dueños = duenos.get(tabla)
                if dueños and ms not in dueños:
                    alertar(archivo, nro, 'tabla-ajena',
                            f'{tabla} es de {", ".join(sorted(dueños))} · {fragmento}')
        if not es_gateway and LLAMADA_MS.search(texto):
            alertar(archivo, nro, 'llamada-entre-ms', fragmento)
        if archivo.endswith('.php') and not ES_TEST.search(archivo) and ASIGNACION.search(texto):
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `python3 -m unittest tests.test_reglas -v`
Expected: 10 tests OK.

- [ ] **Step 5: Probar contra el workspace real (solo lectura)**

Run: `python3 scripts/reglas.py --worktree /home/marcos/projects/dcac-ia-context/microservicios/ms-faena --ownership /home/marcos/projects/dcac-ia-context/dcac-context/back/database-ownership.md --base HEAD~5`
Expected: exit 0 o 1 con alertas legibles `archivo:línea · regla · …`; no exit 2. Anotar falsos positivos evidentes; si un patrón dispara sobre código normal del repo, ajustarlo y agregar un test.

- [ ] **Step 6: Commit**

```bash
git add scripts/reglas.py tests/test_reglas.py
git commit -m "reglas.py: alertas de reglas críticas sobre el diff de un worktree

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `scripts/hechos.py`

**Files:**
- Create: `scripts/hechos.py`
- Test: `tests/test_hechos.py`

**Interfaces:**
- Consumes: `snapshot(worktree) -> str` de `scripts/reglas.py`.
- Produces: CLI `python3 scripts/hechos.py <carpeta del ticket> [--worktree <ruta>]… [--base master]`. Stdout: el Markdown de `revision/hechos.md`. Exit 0 (2 si la carpeta no existe).

- [ ] **Step 1: Escribir los tests**

`tests/test_hechos.py`:

```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'hechos.py'

REGISTRO = """# Registro — T1

## Subagentes despachados
| # | Rol | Modelo | Resultado | Duración / tokens |
|---|-----|--------|-----------|-------------------|
| 1 | Escribano | sonnet | 9 puntos | 248 s · 102k tokens · 12 tools |
| 2 | Agente del plan | opus | plan.md | 600 s · 1.5M tokens |
| 3 | GREEN | sonnet | 2/2 | 300 s · 80k tokens |
| 4 | GREEN | sonnet | 2/2 | en curso |
- **Estado:** en curso
"""

SPEC = """# T1

## Criterios de aceptación
- [ ] **CA1** — Algo.

## Decisiones de contrato
- **E1 · P1 · Formato de ids:** string.
- **C1 · DECISIÓN MENOR del Baqueano · Nombres:** sin prefijo I.
"""

REVISION = """# Revisión plan-tests

### H1 · bloqueante
- **Dice el artefacto:** x

### H2 · menor
- **Dice el artefacto:** y
"""


class Hechos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ticket = Path(self.tmp.name, 'T1-algo')
        (self.ticket / 'revision' / 'testeo').mkdir(parents=True)
        (self.ticket / 'spec.md').write_text(SPEC, encoding='utf-8')
        (self.ticket / 'registro.md').write_text(REGISTRO, encoding='utf-8')
        testeo = self.ticket / 'revision' / 'testeo'
        (testeo / 'red.md').write_text('# RED\nRESULTADO: 0 pasan / 2 fallan\nESTADO: completo\n')
        (testeo / 'green-1.md').write_text('# GREEN 1\nRESULTADO: 1 pasan / 1 fallan\n')
        (testeo / 'green-2.md').write_text('# GREEN 2\nRESULTADO: 2 pasan / 0 fallan\n')
        (self.ticket / 'revision' / 'revision-plan-tests.md').write_text(REVISION, encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def repo(self, nombre):
        wt = Path(self.tmp.name, nombre)
        wt.mkdir()
        g = lambda *a: subprocess.run(['git', '-C', str(wt), *a], check=True, capture_output=True)
        g('init', '-q', '-b', 'master')
        g('config', 'user.email', 't@t')
        g('config', 'user.name', 't')
        (wt / 'README.md').write_text('base\n')
        g('add', '-A')
        g('commit', '-q', '-m', 'base')
        return wt

    def correr(self, *extra):
        r = subprocess.run([sys.executable, str(SCRIPT), str(self.ticket), *extra],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_economia_por_rol_y_sin_registro(self):
        rc, out = self.correr()
        self.assertEqual(rc, 0, out)
        self.assertIn('| Escribano | sonnet | 1 | 248 | 102000 | 0 |', out)
        self.assertIn('| Agente del plan | opus | 1 | 600 | 1500000 | 0 |', out)
        self.assertIn('| GREEN | sonnet | 2 | 300 | 80000 | 1 |', out)
        self.assertIn('**Total:** 4 subagentes · 1148 s · 1682000 tokens · 1 sin registro', out)

    def test_sin_registro_md(self):
        (self.ticket / 'registro.md').unlink()
        rc, out = self.correr()
        self.assertEqual(rc, 0, out)
        self.assertIn('## Economía\nsin registro', out)

    def test_verificacion(self):
        _, out = self.correr()
        self.assertIn('- RED: RESULTADO: 0 pasan / 2 fallan', out)
        self.assertIn('- GREEN 1: RESULTADO: 1 pasan / 1 fallan', out)
        self.assertIn('- GREEN 2: RESULTADO: 2 pasan / 0 fallan', out)
        self.assertIn('Corridas de GREEN: 2', out)

    def test_revisiones(self):
        _, out = self.correr()
        self.assertIn('- revision-plan-tests.md: 2 hallazgos (1 bloqueantes)', out)

    def test_decisiones_textuales_y_provisorias_sin_registro(self):
        _, out = self.correr()
        self.assertIn('- **E1 · P1 · Formato de ids:** string.', out)
        self.assertIn('- **C1 · DECISIÓN MENOR del Baqueano · Nombres:** sin prefijo I.', out)
        self.assertIn('### revision/provisorias.md\nsin registro', out)

    def test_repos_incluye_archivos_nuevos(self):
        wt = self.repo('ms-a')
        (wt / 'nuevo.php').write_text('<?php\n')
        rc, out = self.correr('--worktree', str(wt))
        self.assertEqual(rc, 0, out)
        self.assertIn('- ms-a: 1 file changed', out)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `python3 -m unittest tests.test_hechos -v`
Expected: FAIL en todos.

- [ ] **Step 3: Implementar**

`scripts/hechos.py`:

```python
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


def duracion_y_tokens(texto):
    """(segundos | None, tokens | None) desde '248 s · 102k tokens'."""
    segundos = None
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*min\b', texto)
    if m:
        segundos = round(numero(m.group(1)) * 60)
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*s\b', texto)
    if m:
        segundos = (segundos or 0) + round(numero(m.group(1)))
    tokens = None
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*([kKmM])?\s*tokens', texto)
    if m:
        factor = {'k': 1_000, 'm': 1_000_000}.get((m.group(2) or '').lower(), 1)
        tokens = round(numero(m.group(1)) * factor)
    return segundos, tokens


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
        segundos, tokens = duracion_y_tokens(' '.join(c[i_costo:]))
        g = grupos.setdefault((c[i_rol], c[i_modelo]), [0, 0, 0, 0])
        g[0] += 1
        if segundos is None or tokens is None:
            g[3] += 1
        else:
            g[1] += segundos
            g[2] += tokens
    salida = ['| Rol | Modelo | Subagentes | Duración (s) | Tokens | Sin registro |',
              '|-----|--------|------------|--------------|--------|--------------|']
    total = [0, 0, 0, 0]
    for (rol, modelo), g in grupos.items():
        salida.append(f'| {rol} | {modelo} | {g[0]} | {g[1]} | {g[2]} | {g[3]} |')
        total = [a + b for a, b in zip(total, g)]
    salida.append('')
    salida.append(f'**Total:** {total[0]} subagentes · {total[1]} s · {total[2]} tokens · '
                  f'{total[3]} sin registro')
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
```

Nota: `## Economía` con `sin registro` imprime `## Economía\nsin registro`, que es lo que pide el test.

- [ ] **Step 4: Correr y verificar que pasan**

Run: `python3 -m unittest tests.test_hechos -v`
Expected: 6 tests OK.

- [ ] **Step 5: Probar contra un ticket real (solo lectura)**

Run: `python3 scripts/hechos.py /home/marcos/projects/dcac-ia-context/docs/permisos-psp/desarrollo/T23815-tablas-y-repositorios`
Expected: exit 0. La Economía refleja la tabla de `registro.md` de ese ticket; Verificación y Revisiones dicen `sin registro` (ese ticket usa `juicio/`, no `revision/`). Si la tabla del registro real tiene otro encabezado y la Economía sale vacía, ajustar `economia()` y agregar un test con ese encabezado.

- [ ] **Step 6: Suite completa y commit**

Run: `python3 -m unittest discover -s tests -v`
Expected: 27 tests OK.

```bash
git add scripts/hechos.py tests/test_hechos.py
git commit -m "hechos.py: datos duros del ticket para el Cronista

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Skill `revisar-ticket` y baja del juicio

**Files:**
- Create: `skills/revisar-ticket/SKILL.md`
- Delete: `skills/juicio-ticket/`, `skills/ensayar-juicio/`

**Interfaces:**
- Consumes: CLIs de Task 1 y Task 2.
- Produces: skill `clarabella:revisar-ticket` con modos `plan-tests` e `implementacion`; archivos `revision/trazabilidad.txt`, `revision/reglas-<ms>.txt`, `revision/diff-<ms>.patch`, `revision/ultima-revision-<ms>.txt`, `revision/revision-plan-tests.md`, `revision/revision-impl-<ms>.md`; contrato `ARTEFACTO / HALLAZGOS / ALERTAS_DESCARTADAS / ESTADO`.

- [ ] **Step 1: Crear `skills/revisar-ticket/SKILL.md`**

````markdown
---
name: revisar-ticket
description: Usar para revisar el plan y los tests de un ticket del workspace dcac-ia-context antes de implementar, o la implementación de un repo después de GREEN — primero corren los chequeos determinísticos (trazabilidad de los criterios CA#, reglas críticas sobre el diff) y después un revisor sonnet nuevo, de una sola pasada y con checklist fija, devuelve hasta 10 hallazgos con cita a una fuente. Es la fase 2 (Revisión) de resolver-ticket, el paso 3.4 y la revisión de cada vuelta de ciclo-ticket. Triggers — "revisá el plan y los tests de T#####", "revisá la implementación de T#####", "chequeá la trazabilidad de T#####". NO escribe plan ni tests, NO ejecuta tests, NO corrige.
---

# Revisar ticket

Lo que se puede verificar con un script no se le pregunta a un modelo. La revisión tiene
dos capas:

1. **Chequeos** (scripts, 0 tokens): trazabilidad de criterios y reglas críticas.
2. **Un revisor** (sonnet, nuevo, una pasada) para lo que no se puede mecanizar:
   convenciones, desvíos del plan, coherencia entre plan y tests, y confirmar o descartar
   las alertas de los scripts.

No hay rondas. No se retoma a quien escribió el artefacto para que se defienda. La
verificación de una corrección es volver a correr los scripts (y GREEN, si cambió código).

Todo va a `docs/{proyecto}/{tipo}/T#####-{slug}/revision/` (abajo, `{ticket}`).

## Modo plan-tests (fase 2 de `resolver-ticket`)

### 1. Trazabilidad

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/trazabilidad.py {ticket} > {ticket}/revision/trazabilidad.txt
```

- Exit 2 (formato): la spec no tiene `CA#`, falta un archivo, o la tabla de casos no empieza
  con `| ID | Criterio |`. Arreglalo vos (es formato, no contenido) y volvé a correr.
- Exit 1 (huecos): una línea `Cubre:` faltante la agregás vos. Un criterio sin caso o sin
  Parte es contenido: entra como hallazgo `bloqueante` para la corrección, sin pasar por el
  revisor.

### 2. Revisor

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Revisión plan-tests T#####",
      prompt: "Invocá la skill clarabella:revisar-ticket, rol revisor, modo plan-tests, para
               T##### (proyecto {proyecto}, tipo {tipo}, slug {slug}). Leé solo: spec.md,
               plan.md, tests.md, revision/trazabilidad.txt,
               dcac-context/back/conventions.md y el CLAUDE.md de cada repo del plan.
               Escribí revision/revision-plan-tests.md y devolvé el contrato.")
```

**Checklist del revisor (plan-tests):**
- Cada criterio está cubierto con sentido: la Parte que lo cita lo implementa y el caso que
  lo cita lo prueba (no alcanza con citarlo).
- El plan respeta las reglas críticas: los ms no se llaman entre sí, cada ms toca solo sus
  tablas, sin estado en propiedades de clase en Hyperf/apigateway.
- Plan y tests usan el contrato de `spec.md` (rutas, campos, códigos) y describen el mismo
  comportamiento.
- Los esperados de los tests son coherentes con las reglas documentadas, y cada
  verificación consulta una tabla del servicio dueño.
- El "Esperado en RED" es coherente: `falla` para comportamiento nuevo, `pasa` para
  regresión.
- El plan sigue las convenciones del servicio.

## Modo implementación (paso 3.4 de `resolver-ticket`, vueltas de `ciclo-ticket`)

Por cada repo tocado (`<ms>`, worktree `.worktrees/T#####-{slug}/<ms>`):

### 1. Diff y reglas

```bash
wt=.worktrees/T#####-{slug}/<ms>
base=master   # en el ciclo, desde la segunda revisión: base=$(cat {ticket}/revision/ultima-revision-<ms>.txt)
tree=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reglas.py --snapshot --worktree $wt)
git -C $wt diff $base $tree > {ticket}/revision/diff-<ms>.patch
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reglas.py --worktree $wt --base $base \
  --ownership dcac-context/back/database-ownership.md > {ticket}/revision/reglas-<ms>.txt
echo $tree > {ticket}/revision/ultima-revision-<ms>.txt
```

El snapshot incluye los archivos nuevos sin trackear y no toca el index del repo.
`ultima-revision-<ms>.txt` es la base del delta en la próxima revisión del ciclo: el
revisor ve solo lo que cambió desde la última vez.

### 2. Revisor

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Revisión <ms> T#####",
      prompt: "Invocá la skill clarabella:revisar-ticket, rol revisor, modo implementación,
               para T##### (proyecto {proyecto}, tipo {tipo}, slug {slug}), repo <ms>. Leé
               solo: revision/diff-<ms>.patch, plan.md, revision/reglas-<ms>.txt,
               revision/notas-<ms>.md (si existe), dcac-context/back/conventions.md y el
               CLAUDE.md del repo. Podés abrir un archivo del worktree solo para ver el
               contexto de una línea del diff. Escribí revision/revision-impl-<ms>.md y
               devolvé el contrato.")
```

Los repos van en paralelo, un revisor por repo.

**Checklist del revisor (implementación):**
- Cada Parte del plan para este repo está implementada; los tests unitarios que el plan
  pedía existen.
- Lo que no sale del plan está en `notas-<ms>.md`. Un cambio fuera del plan y sin nota es
  hallazgo.
- Cada alerta de `reglas-<ms>.txt` se confirma (hallazgo `bloqueante`) o se descarta con
  una línea de por qué (falso positivo).
- Convenciones: `conventions.md`, el `CLAUDE.md` del repo, el código vecino; sin
  comentarios salvo que el archivo ya los use.

## El oficio del revisor

- **Una pasada.** Leés lo que dice el prompt, escribís el archivo, devolvés el contrato. No
  ejecutás nada: ni tests, ni lint, ni la app.
- **Hasta 10 hallazgos**, los más importantes primero. Si hay más, quedate con los
  bloqueantes.
- **Cada hallazgo, contra una fuente.** Lo que no tiene fuente no se reporta.
- **Severidad:** `bloqueante` (contradice la spec, una regla crítica o una regla de negocio
  documentada, o deja un criterio sin cubrir) o `menor` (se aparta de una convención sin
  cambiar el comportamiento).

```markdown
# Revisión — {plan-tests | impl <ms>} · T#####

### H1 · bloqueante
- **Dice el artefacto:** <cita, con sección, caso o archivo:línea>
- **Dice la fuente:** <cita> — `<ruta>` § <sección>
- **Propuesta:** <qué cambiar>

## Alertas descartadas
- `<archivo:línea · regla>` — <por qué es falso positivo>
```

Contrato:
```
ARTEFACTO: revision/<archivo>
HALLAZGOS: <n> (<b> bloqueantes, <m> menores)
ALERTAS_DESCARTADAS: <n>
ESTADO: completo
```

## La corrección

| Artefacto | Quién corrige |
|-----------|---------------|
| `plan.md` / `tests.md` | Un subagente **nuevo** (`sonnet`) con el artefacto y los hallazgos que le tocan, nada más. Si el cambio es trivial (una línea `Cubre:`, un renombre), el hilo principal |
| Código de un repo | Quien implementó ese repo (el hilo principal o su subagente) |

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Corregir {plan|tests} T#####",
      prompt: "Corregí {plan.md|tests.md} de T##### (carpeta {ticket}) según los hallazgos
               H<n>, H<m> de revision/revision-plan-tests.md. Cambiá solo lo que marcan. Si
               un hallazgo no corresponde, no lo apliques: devolvé DESACUERDO: H<n> — <por
               qué, con fuente>. Devolvé ARTEFACTO/CORREGIDOS/DESACUERDOS/ESTADO.")
```

- **No se retoma al agente del plan** (opus, con toda su exploración): ese era el costo del
  juicio.
- Los `DESACUERDOS` van al usuario en una línea cada uno (en el ciclo, al Baqueano: menor o
  provisoria).
- **No hay segunda revisión.** Después de corregir: `trazabilidad.py` de nuevo
  (plan-tests), o `reglas.py` y un GREEN nuevo si cambió código (implementación).

## Registro

Cada revisor y cada corrector es una fila en `registro.md` (rol, modelo, resultado,
duración, tokens), como cualquier subagente.

## Errores comunes

- **Mandarle al revisor lo que un script ya verificó** → la trazabilidad y las reglas no se
  revisan a mano; el revisor solo confirma o descarta alertas.
- **Retomar al autor para que corrija o se defienda** → corrige un sonnet nuevo con el
  artefacto y los hallazgos.
- **Una segunda pasada del revisor sobre la corrección** → se verifica con scripts y GREEN.
- **Revisar el diff completo en cada vuelta del ciclo** → desde la segunda, solo el delta
  (`ultima-revision-<ms>.txt`).
- **Usar `git diff master` a secas** → no ve los archivos nuevos sin trackear; usá el
  snapshot.
- **Reportar un hallazgo sin fuente** → no se reporta.
````

- [ ] **Step 2: Eliminar el juicio**

```bash
git rm -r -q skills/juicio-ticket skills/ensayar-juicio
```

- [ ] **Step 3: Verificar el frontmatter**

Run: `head -4 skills/revisar-ticket/SKILL.md`
Expected: `---`, `name: revisar-ticket`, `description: …`, `---`.

- [ ] **Step 4: Commit**

```bash
git add skills/revisar-ticket
git commit -m "revisar-ticket reemplaza a juicio-ticket y ensayar-juicio

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Agentes generativos, implementador y Escribano

**Files:**
- Modify: `skills/planear-ticket/SKILL.md` (líneas ~61, ~86, ~106-113, ~132, sección `## Como agente generativo de juicio-ticket` ~194-213)
- Modify: `skills/planear-tests-ticket/SKILL.md` (~131, tabla de casos ~208-209, sección `## Como agente generativo de juicio-ticket` ~275-294)
- Modify: `skills/implementar-ticket/SKILL.md` (`## Bitácora de implementación` ~83-90, ~112-113, ~161-162)
- Modify: `skills/escribano/SKILL.md` (~60, `## Después` ~90)

**Interfaces:**
- Consumes: formatos de Global Constraints (`CA#`, `Cubre:`, `| ID | Criterio |`).
- Produces: `revision/notas-<ms>.md` (implementador); `spec.md` con `CA#` (Escribano).

- [ ] **Step 1: `planear-ticket`**

1. En el bloque de estructura del plan, debajo de `## Parte 1 — <repo>` (y de `## Parte N — <repo>`), agregar como primera línea del cuerpo:

```markdown
Cubre: CA1, CA3
```

y debajo del bloque, el párrafo:

```markdown
**`Cubre:`** es obligatoria en cada Parte: la línea empieza exactamente con `Cubre: ` y
lista los criterios de `spec.md` que esa Parte implementa (`CA1, CA3`). La lee
`trazabilidad.py`; un criterio que ninguna Parte cubre frena la revisión.
```

2. En la línea ~61, `juicio/exploracion-<ms>.md` → `revision/exploracion-<ms>.md`.
3. En "Tamaño del plan" (~86), `(Juez, peritos, implementadores, Cronista)` → `(revisor, implementadores, Cronista)`.
4. En ~132, reemplazar la mención "en el juicio (`juicio-ticket`, donde defendés el plan frente a la documentación)" por "en la revisión (`revisar-ticket`)".
5. Reemplazar la sección `## Como agente generativo de juicio-ticket` entera por:

```markdown
## Como agente generativo de `resolver-ticket` o `ciclo-ticket`

Si el prompt dice que sos el agente generativo del plan:

1. Tu única fuente de lo pedido es `spec.md`. **Nunca leas `tests.md`.**
2. Cada Parte lleva su línea `Cubre:`. Un criterio que no sabés cómo cubrir es una DUDA, no
   una Parte sin `Cubre:`.
3. Las DUDAS van en el contrato; te las contesta el Baqueano o el usuario. Si una decisión
   sale de una respuesta del Baqueano, citá la consulta (`C3`) en el plan, al lado de la
   decisión.
4. Después de entregar, no te van a retomar: la revisión la hace un revisor nuevo y las
   correcciones, otro agente. Lo que dejes escrito es lo que cuenta.
```

- [ ] **Step 2: `planear-tests-ticket`**

1. En "Tamaño" (~131), `lo leen el Juez, los peritos, el RED, cada GREEN y el Cronista` → `lo leen el revisor, el RED, cada GREEN y el Cronista`.
2. En la Fase 2 (~136), `tabla de casos (ID, precondición, …)` → `tabla de casos (ID, criterio, precondición, …)`.
3. En la plantilla, la tabla de casos pasa a:

```markdown
## Tabla de casos de prueba
| ID | Criterio | Precondición | Acción / request | Esperado | Código | Esperado en RED |
```

y debajo, el párrafo:

```markdown
`Criterio` va **segunda**, siempre: uno o más `CA#` de `spec.md` (`CA1, CA2`), o
`regresión` para un caso de comportamiento existente. La lee `trazabilidad.py`; un caso
sin criterio, o un criterio sin caso, frena la revisión.
```

4. Reemplazar la sección `## Como agente generativo de juicio-ticket` entera por:

```markdown
## Como agente generativo de `resolver-ticket` o `ciclo-ticket`

Si el prompt dice que sos el agente generativo de los tests:

1. Tu única fuente de lo pedido es `spec.md`. **Nunca leas `plan.md`.**
2. Cada caso lleva su `Criterio`. Un criterio que no se puede testear va a "Fuera de
   alcance" con el motivo, y es una DUDA.
3. Las DUDAS van en el contrato; te las contesta el Baqueano o el usuario. Si un esperado
   sale de una respuesta del Baqueano, citá la consulta (`C3`) en el caso.
4. Después de entregar, no te van a retomar: la revisión la hace un revisor nuevo y las
   correcciones, otro agente.
```

- [ ] **Step 3: `implementar-ticket`**

1. Renombrar `## Bitácora de implementación` a `## Notas de implementación` y reemplazar su cuerpo por:

```markdown
Mientras implementás, anotá en `revision/notas-<ms>.md` (uno por repo) **solo lo que no
sale literal del plan**: un desvío, una decisión que el plan no tomaba, un archivo que el
plan no nombraba. Una línea por punto, con el por qué. Lo que sigue el plan no se anota.

El revisor de la implementación (`revisar-ticket`) lee estas notas: un cambio fuera del
plan sin nota es un hallazgo.
```

2. En ~112-113, reemplazar las oraciones sobre bitácora, perito, defensa y Juez por:
   `Tus notas las lee el revisor. Lo que la revisión marque como bloqueante lo corregís vos, solo en lo marcado, y después corre un GREEN nuevo.`
3. En Errores comunes (~161-162), reemplazar el ítem por:
   `- **No anotar en las notas una decisión que el plan no tomaba** → el revisor lo marca como cambio fuera del plan.`

- [ ] **Step 4: `escribano`**

1. En ~60, reemplazar "lo justifica en su bitácora, y el Juez lo revisa" por "lo resuelve en su artefacto, y el revisor lo mira".
2. En `## Después`, agregar al final:

```markdown
**Numerar los criterios.** Con la escritura cerrada, los criterios de aceptación de
`spec.md` quedan numerados en su sección `## Criterios de aceptación`, con el formato
`- [ ] **CA1** — <texto tal cual>`. No se reescribe el texto del ticket: solo se agrega el
número. Si la escritura sumó un criterio (un borde que el usuario decidió testear), va al
final con el número siguiente y `(escritura E#)`.
```

3. Cualquier ruta `juicio/` en el archivo → `revision/`.

- [ ] **Step 5: Verificar**

Run: `grep -n -i -E 'juicio|juez|perito|bit[aá]cora|prontuario' skills/planear-ticket/SKILL.md skills/planear-tests-ticket/SKILL.md skills/implementar-ticket/SKILL.md skills/escribano/SKILL.md`
Expected: sin resultados.

- [ ] **Step 6: Commit**

```bash
git add skills/planear-ticket skills/planear-tests-ticket skills/implementar-ticket skills/escribano
git commit -m "Generativos, implementador y escribano: CA#, Cubre:, Criterio y notas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Baqueano

**Files:**
- Modify: `skills/baqueano/SKILL.md` (~30-31, regla 1 ~82, tabla de faltas ~93-101, ~120, ~131-132, ~150, ~162, ~167, ~187, ~194)

- [ ] **Step 1: Editar**

1. ~30-31: `` `juicio/bitacora-*.md`), ni `juicio/peritajes/` `` → `` ni `revision/` ``. La oración queda: "No lee: los artefactos de los agentes generativos (`plan.md`, `tests.md`) ni `revision/`."
2. Regla 1 (~82): reemplazar "Un perito puede abrir cada cita y revisar tu…" por "El usuario y el Cronista pueden abrir cada cita: tiene que existir y decir eso."
3. Tabla de faltas (~93-101): eliminar la fila `fabricacion` y el párrafo "Solo cuenta si un agente generativo **usó** esa respuesta y el error llegó al juicio…", y reemplazar "**Con una falta, el Baqueano corrige** (ver `juicio-ticket` § El Baqueano en el juicio)…" por:

```markdown
**Si una respuesta resulta errónea** (lo marca la revisión, el RED o el GREEN), el
Baqueano se retoma, corrige esa respuesta, y el orquestador le pasa la corrección al agente
que la usó, que actualiza solo lo que dependía de ella.
```

   (Las demás faltas de la tabla, si quedan `respuesta-erronea` y `decidio-por-el-usuario`, se mantienen; si la tabla queda vacía, eliminarla.)
4. Todas las rutas `juicio/consultas-{plan|tests}.md` → `revision/consultas-{plan|tests}.md` (~120, ~150, ~167).
5. ~131-132: reemplazar "El Juez lee estos archivos en el juicio… Un perito puede verificar sus citas…" por "El revisor y el Cronista leen estos archivos: un agente generativo puede citar una respuesta (\"consulta C3\")."
6. ~162: eliminar el punto 4 "Guardá el id de cada Baqueano: en el juicio, un perito lo puede interrogar." (renumerar si hace falta) y reemplazarlo por "4. **Guardá el id de cada Baqueano:** si una respuesta resulta errónea, se lo retoma para corregirla."
7. Errores comunes ~187 y ~194: "el perito y el usuario necesitan poder verificarlo" → "el usuario necesita poder verificarlo"; "es lo primero que verifica el perito" → "el usuario lo va a notar al seguir la cita".

- [ ] **Step 2: Verificar y commit**

Run: `grep -n -i -E 'juicio|juez|perito|prontuario|fabricaci' skills/baqueano/SKILL.md`
Expected: sin resultados.

```bash
git add skills/baqueano
git commit -m "Baqueano sin juicio: correcciones y rutas en revision/

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `resolver-ticket`

**Files:**
- Modify: `skills/resolver-ticket/SKILL.md` (frontmatter, tabla de fases ~12-18, párrafo del orquestador ~27, árbol de carpeta ~47-56, registro ~62-66, 1.3 ~90-133, Fase 2 ~135-156, 3.2 ~176-202, 3.3 ~230-239, 3.4-3.5 ~241-251, Errores comunes ~267-298)

- [ ] **Step 1: Frontmatter**

En `description`, reemplazar `juicio (Juez, defensa y peritos), implementación (RED, código, GREEN, diff)` por `revisión (trazabilidad, reglas y un revisor de una pasada), implementación (RED, código, GREEN, revisión, diff)`.

- [ ] **Step 2: Tabla de fases**

```markdown
| Fase | Qué pasa | Termina cuando |
|------|----------|----------------|
| **1. Preparación** | Repos listos; un agente generativo escribe el plan y otro los tests, sin verse | Los dos entregaron y sus DUDAS están respondidas |
| **2. Revisión** | Trazabilidad de criterios (script), un revisor sonnet de una pasada, corrección por un agente nuevo | El usuario aprueba plan y tests |
| **3. La implementación** | RED, implementación (en paralelo por repo si conviene), GREEN, reglas críticas (script) y revisión del diff | El usuario valida el diff |
| **4. La entrega** | Crónica, review, bajar el entorno | La review salió y el entorno está abajo |
```

En el párrafo "El hilo principal es el orquestador", `En las fases 1 y 2 no genera ni defiende nada` → `En las fases 1 y 2 no genera nada (salvo arreglos de formato que pidan los scripts)`.

- [ ] **Step 3: Paso 0**

1. Después del párrafo **Escritura.**, agregar: `Con la escritura cerrada, el Escribano numera los criterios de `spec.md` (`CA1…CAn`): la trazabilidad de la fase 2 cruza esos números.`
2. En el árbol, la línea de `juicio/` pasa a:

```
├── revision/    ← fases 1-3 (consultas del Baqueano, trazabilidad, reglas, revisiones,
│                  notas de los implementadores, testeo/ con RED y GREEN, hechos.md)
```

3. En "Llevá el registro", `juicio/testeo/` → `revision/testeo/`.

- [ ] **Step 4: 1.3 Los agentes generativos**

1. Reemplazar el primer párrafo ("Los dos reciben las reglas del oficio de `juicio-ticket`… Guardá el id de cada uno: en el juicio se los retoma…") por:

```markdown
Cada uno trabaja solo desde `spec.md` y no ve el artefacto del otro. **Guardá el id de cada
uno** solo para pasarle las respuestas a sus DUDAS durante esta fase: después no se los
retoma (la revisión y las correcciones las hacen agentes nuevos).
```

2. En los dos prompts: borrar `<reglas del oficio: tests>` / `<reglas del oficio: plan>`; `como agente generativo de juicio-ticket` → `como agente generativo`; `Escribí tests.md y juicio/bitacora-tests.md` → `Escribí tests.md (columna Criterio con los CA# de spec.md)`; `Escribí plan.md y juicio/bitacora-plan.md` → `Escribí plan.md (línea Cubre: en cada Parte)`.
3. `juicio/exploracion-<ms>.md` → `revision/exploracion-<ms>.md`.
4. Última línea: `La fase 1 termina cuando los dos entregaron su artefacto.`

- [ ] **Step 5: Fase 2**

Reemplazar la sección `## Fase 2 — El juicio` entera por:

```markdown
## Fase 2 — Revisión

Invocá `revisar-ticket` en modo plan-tests y seguí su procedimiento:

1. `trazabilidad.py` → `revision/trazabilidad.txt`. Los errores de formato y las líneas
   `Cubre:` faltantes los arreglás vos; un criterio sin Parte o sin caso es hallazgo
   bloqueante.
2. Un revisor sonnet nuevo, una pasada → `revision/revision-plan-tests.md`.
3. Si hay hallazgos: un sonnet nuevo corrige `plan.md` y otro `tests.md` (en paralelo),
   cada uno con sus hallazgos y nada más. Los triviales los corregís vos. **No retomes a los
   agentes generativos.**
4. `trazabilidad.py` otra vez.
5. Le presentás al usuario los hallazgos (copiados, sin resumir), qué se corrigió y los
   DESACUERDOS, uno por línea. Lo que decida va a `spec.md` § Decisiones de contrato y, si
   cambia un artefacto, lo aplica un sonnet nuevo.

La fase 2 termina cuando el usuario aprueba `plan.md` y `tests.md`.
```

- [ ] **Step 6: Fase 3**

1. 3.2: `Quien implementa anota en juicio/implementacion/bitacora-<ms>.md lo que no sale literal del plan` → `Quien implementa anota en revision/notas-<ms>.md lo que no sale literal del plan`. En el prompt paralelo, `Escribí juicio/implementacion/bitacora-<ms>.md` → `Anotá los desvíos del plan en revision/notas-<ms>.md`. El párrafo "**Guardá el id de cada implementador:** en el juicio de la implementación se los retoma para que se defiendan, y para corregir lo que el Juez sostenga." → "**Guardá el id de cada implementador:** se los retoma para corregir los bugs de GREEN y los hallazgos de la revisión."
2. 3.3: en `test-mal-documentado`, `Después de un juicio es raro: anotalo para el resumen, porque el juicio no lo detectó.` → `Anotalo: la revisión no lo detectó. Lo corrige un sonnet nuevo y se repite el RED de ese caso.`
3. Reemplazar 3.4 y 3.5 por:

```markdown
### 3.4 Revisión de la implementación
Con GREEN completo, `revisar-ticket` en modo implementación, un revisor por repo en
paralelo: `reglas.py` sobre el snapshot del worktree (incluye archivos nuevos) y un revisor
sonnet con el diff, el plan, las alertas y las notas. Los bloqueantes los corrige quien
implementó ese repo; si cambió código, otro GREEN y otra vez `reglas.py`. No hay segunda
revisión.

### 3.5 Exponer los cambios
El usuario valida el diff en `mostrar-diff` junto con las revisiones de la implementación.
La fase 3 termina con su OK.
```

- [ ] **Step 7: Fase 4 y Errores comunes**

1. En la fila 4.1, agregar al principio de la Nota: `Antes, armá los hechos: python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hechos.py {ticket} --worktree .worktrees/T#####-{slug}/<ms> … > {ticket}/revision/hechos.md.`
2. En Errores comunes: eliminar los ítems que mencionan Juez, peritos, defensa, sentencia, bitácora o reglas del oficio, y agregar:

```markdown
- **Retomar a un agente generativo para corregir** → corrige un sonnet nuevo con el
  artefacto y los hallazgos.
- **Pedirle al revisor que verifique cobertura o reglas a mano** → eso lo hacen
  `trazabilidad.py` y `reglas.py`.
- **Revisar con `git diff master`** → no ve los archivos nuevos; `revisar-ticket` usa el
  snapshot.
```

- [ ] **Step 8: Verificar y commit**

Run: `grep -n -i -E 'juicio|juez|perito|bit[aá]cora|prontuario|sentencia|defensa' skills/resolver-ticket/SKILL.md`
Expected: sin resultados.

```bash
git add skills/resolver-ticket
git commit -m "resolver-ticket: fase 2 de revisión y revisión de la implementación

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `ciclo-ticket`

**Files:**
- Modify: `skills/ciclo-ticket/SKILL.md` (frontmatter, Etapa 0 ~30-34, definición de terminado ~42, Etapas 2-4 ~57-85, provisorias ~94, implementador ~102-116, firma ~136-142, Errores comunes)

- [ ] **Step 1: Editar**

1. `description`: `prepara, juzga, implementa, testea` → `prepara, revisa, implementa, testea`.
2. Todas las rutas `juicio/provisorias.md` → `revision/provisorias.md`; `juicio/testeo/` → `revision/testeo/`.
3. Definición de terminado, punto 3 → `3. `reglas.py` sin alertas abiertas (confirmadas y sin corregir) y la última revisión de la implementación sin bloqueantes.`
4. Etapa 2 → reemplazar por:

```markdown
### Etapa 2 — Revisión del plan y los tests
Fase 2 de `resolver-ticket` (`revisar-ticket`, modo plan-tests), con un cambio: **"sin
bloqueantes" reemplaza la aprobación del usuario.** Los DESACUERDOS de los correctores
pasan por el Baqueano, que los resuelve como menor o como provisoria.
```

5. Etapa 3: `la falla vuelve al agente de tests (test-no-discrimina, test-mal-documentado) y el juicio se reabre para tests.md` → `un sonnet nuevo corrige los casos (test-no-discrimina, test-mal-documentado), corre trazabilidad.py y se repite el RED de esos casos`.
6. Etapa 4, paso 3 → `3. **Revisión de la implementación**, si el GREEN pasó completo: `revisar-ticket` modo implementación. La primera vez sobre el diff completo; después, solo el delta desde la última revisión (`revision/ultima-revision-<ms>.txt`).`
7. Tabla de fallas de la Etapa 4:

```markdown
| Falla | Vuelve a | Qué pasa |
|-------|----------|----------|
| `bug-implementacion` | El implementador de ese repo | Corrige; la próxima vuelta lo prueba |
| Hallazgo bloqueante o alerta confirmada | El implementador | Corrige solo lo marcado; GREEN y `reglas.py` en la próxima vuelta |
| `hueco-del-plan` | Un sonnet nuevo | Agrega la Parte que falta con su `Cubre:`; `trazabilidad.py`; después se implementa |
| `test-mal-documentado` | Un sonnet nuevo | Corrige el caso; `trazabilidad.py`; se repite el RED de ese caso |
| `ambiguedad-negocio` | El Baqueano | La resuelve como menor o como provisoria |
```

8. Sección del implementador: `recibe las reglas del oficio (juicio-ticket), escribe bitácora y se defiende en el juicio de la implementación` → `anota sus desvíos en revision/notas-<ms>.md`. En su tabla de faltas, eliminar las filas `fabricacion` y `defensa-perdida` (queda `sin-progreso`). "Las faltas van al prontuario y las cuenta el Cronista" → "`sin-progreso` lo cuenta el Cronista". "con el código actual, su bitácora y el último reporte de GREEN" → "con el código actual, sus notas y el último reporte de GREEN".
9. Firma: el ejemplo pasa a `- Firma: C9 bug-implementacion · C12 bug-implementacion · H2 bloqueante` y la oración de arriba a `los casos que fallan con su clasificación, más los hallazgos bloqueantes`. Borrar la línea `- Faltas: …` del ejemplo y poner `- sin-progreso: implementador apigateway-psp`.
10. En "El final", `cuenta todas las vueltas (firma, faltas, costo, …)` → `cuenta todas las vueltas (firma, sin-progreso, costo, …)`.

- [ ] **Step 2: Verificar y commit**

Run: `grep -n -i -E 'juicio|juez|perito|bit[aá]cora|prontuario|fabricaci|defensa' skills/ciclo-ticket/SKILL.md`
Expected: sin resultados.

```bash
git add skills/ciclo-ticket
git commit -m "ciclo-ticket: revisión de una pasada y delta por vuelta

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Cronista

**Files:**
- Modify: `skills/cronista/SKILL.md` (frontmatter, Fuentes ~49-68, plantilla ~93-112, Análisis ~115-116, Errores comunes)

- [ ] **Step 1: Editar**

1. `description`: `(implementado, testeado y juzgado, …)` → `(implementado, testeado y revisado, …)`.
2. Reemplazar la sección `## Las fuentes` (tabla incluida) por:

```markdown
## Las fuentes

Primero, **`revision/hechos.md`**: lo arma `hechos.py` antes de despacharte y trae los
datos duros ya contados (economía por rol, RED y cada GREEN, repos, hallazgos por revisión,
decisiones textuales). Los números de la crónica salen de ahí, sin recalcular.

Después, solo lo que haga falta para contar o chequear un dato puntual:

| Archivo | Para qué |
|---------|----------|
| `spec.md` | Lo pedido y las decisiones de contrato |
| `escritura.md` | Lo que el Escribano anticipó y lo que respondió el usuario |
| `revision/provisorias.md` | En el ciclo: las provisorias, cuáles confirmó y cuáles vetó el usuario |
| `revision/revision-*.md` | Los hallazgos y las alertas descartadas |
| `revision/consultas-*.md` | Qué contestó el Baqueano y qué subió al usuario |
| `revision/notas-<ms>.md` | Los desvíos del plan |
| `plan.md`, `tests.md` | Lo planeado y cómo se verificó |

Si un archivo esperado no existe, la sección correspondiente dice "sin registro" y sigue.
```

3. En la plantilla: eliminar las secciones `## Tribunales` y `## Prontuario`; agregar, antes de `## Economía`:

```markdown
## Revisión
Qué marcaron las revisiones (plan-tests e implementación), qué se corrigió, qué alertas de
reglas se descartaron y por qué, y los desacuerdos que decidió el usuario.
```

4. `## Economía`: reemplazar la tabla por `La tabla de `hechos.md` § Economía, tal cual.` y dejar el resto de las líneas.
5. `## Fe de erratas`: `tests corregidos después del juicio, documentación que el proceso mostró desactualizada ("Documentación a revisar" de las sentencias)` → `tests corregidos después de la revisión, documentación que el proceso mostró desactualizada`.
6. `## Análisis del cronista`: `(reglas del Juez, del perito, del Baqueano, de los agentes)` → `(checklist del revisor, patrones de reglas.py, Baqueano, agentes)`.
7. Regla 4 del oficio: `Cuenta las faltas, las correcciones fallidas, …` → `Cuenta los hallazgos, las correcciones fallidas, …`.
8. Registro de decisiones: `las de las sentencias` → `los desacuerdos que decidió`.
9. Errores comunes: `Suavizar las faltas, los vetos o las vueltas de GREEN` → `Suavizar los hallazgos, los vetos o las vueltas de GREEN`; agregar `- **Recalcular lo que ya está en hechos.md** → los números salen de ahí.`

- [ ] **Step 2: Verificar y commit**

Run: `grep -n -i -E 'juicio|juez|perito|prontuario|sentencia|tribunal|falta' skills/cronista/SKILL.md`
Expected: sin resultados (salvo "faltaron" en `SIN_REGISTRO: <datos que faltaron…>`, que se queda).

```bash
git add skills/cronista
git commit -m "Cronista: lee hechos.md y cuenta la revisión en vez del juicio

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Puerta de entrada, README, versión y verificación final

**Files:**
- Modify: `skills/clarabella/SKILL.md` (tabla ~31-34)
- Modify: `README.md` (tabla de skills, flujo, modo ciclo, modelos por rol)
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: `clarabella`**

Reemplazar la fila de `juicio-ticket` por:

```markdown
| Revisar el plan y los tests (o la implementación) de un ticket, "revisá T#####", "chequeá la trazabilidad" | `clarabella:revisar-ticket` |
```

y eliminar la fila de `ensayar-juicio`.

- [ ] **Step 2: README**

1. Tabla de skills: eliminar `juicio-ticket` y `ensayar-juicio`; agregar `| `revisar-ticket` | Trazabilidad y reglas críticas por script, y un revisor sonnet de una pasada (plan y tests, o implementación) |`; en `planear-ticket` agregar "con `Cubre: CA#` por Parte"; en `planear-tests-ticket`, "con columna `Criterio`".
2. Agregar después de la tabla:

```markdown
### Scripts (`scripts/`, Python stdlib)

| Script | Qué hace |
|--------|----------|
| `trazabilidad.py <ticket>` | Cruza los `CA#` de la spec con `Cubre:` del plan y la columna `Criterio` de los tests |
| `reglas.py --worktree … --ownership …` | Alertas de tabla ajena, llamada entre ms y estado en clase sobre el diff (incluye archivos nuevos) |
| `hechos.py <ticket> --worktree …` | Datos duros para el Cronista |

Tests: `python3 -m unittest discover -s tests -v`.
```

3. Flujo de `resolver-ticket`, punto 2 → `2. **Revisión** (`revisar-ticket`): `trazabilidad.py`, un revisor sonnet de una pasada, corrección por un agente nuevo (nunca se retoma al autor). Aprueba el usuario`. En el punto 3, `→ juicio de la implementación →` → `→ `reglas.py` + revisión de la implementación →`. En el punto 0, agregar "y numerar los criterios `CA#`". En el punto 1, eliminar "sus dudas van al `baqueano`…" solo si menciona el juicio (si no, queda).
4. Modo ciclo: `→ juicio →` → `→ revisión →`; `vueltas de implementar, GREEN y juicio de la implementación` → `vueltas de implementar, GREEN y revisión de la implementación (solo el delta)`.
5. Modelos por rol → `**Modelos por rol:** opus para el agente del plan; sonnet para el agente de tests, el Baqueano, el Escribano, los revisores, los correctores, los implementadores, RED/GREEN y el Cronista; haiku para los exploradores.`

- [ ] **Step 3: Versión**

En `.claude-plugin/plugin.json`: `"version": "0.4.0"` → `"version": "0.5.0"`, y en `description` `resume, envía a review` → `revisa con scripts y un revisor de una pasada, resume, envía a review`.

- [ ] **Step 4: Verificación final**

Run: `grep -rn -i -E 'juicio|juez|perito|prontuario|ensayar' --include=*.md --include=*.json --include=*.py --include=*.sh . | grep -v '^./docs/'`
Expected: sin resultados.

Run: `python3 -m unittest discover -s tests -v`
Expected: 27 tests OK.

Run: `ls skills`
Expected: sin `juicio-ticket` ni `ensayar-juicio`; con `revisar-ticket`.

- [ ] **Step 5: Commit**

```bash
git add skills/clarabella README.md .claude-plugin/plugin.json
git commit -m "Clarabella 0.5.0: revisión en vez de juicio

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Medición (después del merge, con Marcos)**

Correr un ticket real con `resolver-ticket` o `ciclo-ticket` y comparar `revision/hechos.md` § Economía contra el `registro.md` de un ticket de la 0.4.0 (por ejemplo, `docs/permisos-psp/desarrollo/T23815-tablas-y-repositorios/registro.md`). No es parte de este plan: es la verificación del criterio de éxito del spec.
