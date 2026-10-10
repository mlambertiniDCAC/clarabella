# resolver-ticket de 8 pasos y resolver-proyecto — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clarabella 0.6.0 con dos modos: `resolver-ticket` manual de 8 pasos (0.3.0 restaurado) y `resolver-proyecto` autónomo para uno o más tickets (Coordinador Haiku, generadores, Alineador, corrección con evidencia, juicio de valor en sesión aparte, Implementador que despacha Obreros, casos como scripts).

**Architecture:** Tres scripts Python stdlib nuevos (`contratos.py`, `fichas.py`, `correr_casos.py`) se suman a los de 0.5.0; cada rol es un tipo de agente del plugin (`agents/*.md`) con `model`, `effort`, `skills` y `tools: Agent(...)`; dos skills nuevas (`resolver-proyecto` para el Coordinador, `juzgar-proyecto` para el Juez); `resolver-ticket` y `resumir-ticket` vuelven de 0.3.0; `ciclo-ticket` se elimina; dos tests de consistencia (`test_agentes.py`, `test_referencias.py`) fijan los roles del spec y que no queden referencias rotas.

**Tech Stack:** Python 3.12 stdlib, bash, git, Markdown (skills y agentes de Claude Code).

**Spec:** `docs/specs/2026-10-09-resolver-proyecto-design.md`

## Global Constraints

- Repo `/home/marcos/projects/clarabella`, branch `revision-en-vez-de-juicio`. Paths relativos a esa raíz.
- Versión objetivo `0.6.0` en `.claude-plugin/plugin.json`.
- Scripts: Python stdlib, en `scripts/`, invocados como `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py`. Salida: 0 sin problemas, 1 con problemas, 2 error de formato/entrada.
- Tests: `python3 -m unittest discover -s tests -v` desde la raíz.
- Subagentes: hasta 3 capas (default de Claude Code ≥ v2.1.219); el diseño usa 2: Coordinador → Implementador → Obrero.
- Roles, modelo · esfuerzo (del spec): Coordinador Haiku · medio; Escribano Sonnet · alto; Generador de plan Sonnet · alto; Generador de tests Sonnet · alto; Alineador Opus · alto; Verificador Sonnet · medio; Corrector Sonnet · medio; Juez Opus · alto; QA Sonnet · alto; Implementador Sonnet · medio; Obrero Sonnet · medio (alto al escalar); Revisor Sonnet · medio; Cronista Sonnet.
- El Coordinador corre como sesión principal: `claude --agent clarabella:coordinador`. El Juez corre en sesión aparte: `claude --agent clarabella:juez`.
- Nadie despacha salvo el Coordinador y el Implementador. Todo agente sin `Agent(...)` en `tools` lleva `disallowedTools: Agent`.
- `## Contrato` en `plan.md`: `### Expone` y `### Consume`, bullets `` - `VERBO /ruta` — … ``; un Consume dice `de T#####` o `existente`.
- `resolver-ticket` (manual): sesión principal, sin subagentes, 8 pasos, aprobación del usuario en cada paso.
- Textos en español rioplatense, mismo tono que las skills vecinas. Commits terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Parámetros de ruta con distinto nombre** (`/a/:id` expuesto, `/a/{sujetoId}` consumido): tienen que cruzar como la misma ruta. → test en Task 1.
2. **Plan sin `## Contrato`, o con la sección sin `### Expone`/`### Consume`:** error de formato (exit 2), nunca "OK". → test en Task 1.
3. **Ciclo de dependencias entre tickets:** se reporta, el script termina y el orden devuelve lo que no está en el ciclo. → test en Task 1.
4. **Un caso que se cuelga** (servicio que no responde): el timeout lo marca como falla y el resto de los casos corre. → test en Task 3.
5. **Un caso de `tests.md` sin script** (el QA no lo escribió): se reporta como `sin script` y cuenta como problema, tanto en RED como en GREEN. → test en Task 3.

---

## File Structure

| Archivo | Responsabilidad |
|---------|-----------------|
| `scripts/contratos.py` | Parsear `## Contrato`, cruzar Expone/Consume del lote, orden topológico, `--deriva` |
| `scripts/fichas.py` | Ficha de un ticket para el juicio |
| `scripts/correr_casos.py` | Correr `casos/<ms>/T##.sh`, modo GREEN y modo RED (contra "Esperado en RED") |
| `tests/test_contratos.py`, `tests/test_fichas.py`, `tests/test_correr_casos.py` | Tests de los scripts |
| `tests/test_agentes.py` | Los tipos de agente cumplen la tabla de roles del spec |
| `tests/test_referencias.py` | Ninguna skill/agente/README referencia algo que no existe o que se eliminó |
| `agents/*.md` (15) | Un tipo de agente por rol |
| `skills/resolver-proyecto/SKILL.md` | Procedimiento del Coordinador |
| `skills/juzgar-proyecto/SKILL.md` | Procedimiento del Juez |
| `skills/resolver-ticket/SKILL.md` | 0.3.0 restaurado con ajustes |
| `skills/resumir-ticket/SKILL.md` | 0.3.0 restaurado |
| `skills/ciclo-ticket/` | Se elimina |

---

### Task 1: `scripts/contratos.py`

**Files:**
- Create: `scripts/contratos.py`
- Test: `tests/test_contratos.py`

**Interfaces:**
- Consumes: `lineas_agregadas(worktree, base, tree)` y `snapshot(worktree)` de `scripts/reglas.py`.
- Produces:
  - CLI `contratos.py <carpeta de ticket>...` → líneas de problemas u `OK: N tickets, contratos cruzados`, y siempre una última línea `ORDEN: T1 T2 …`.
  - CLI `contratos.py --deriva <carpeta>... --worktree T#####=<ruta> [...] [--base master]`.
  - Funciones importables: `seccion(texto, titulo, nivel) -> str | None`, `contrato(carpeta) -> dict` con claves `ticket`, `expone: [(verbo, ruta)]`, `consume: [(verbo, ruta, origen)]` (origen `'existente'`, `'T#####'` o `None`); `ValueError` ante formato inválido.

- [ ] **Step 1: Escribir los tests**

`tests/test_contratos.py`:

```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'contratos.py'


def plan(expone, consume):
    lineas = ['# Plan', '', '## Parte 1 — ms-a', 'Cubre: CA1', '', '## Contrato', '### Expone']
    lineas += [f'- `{e}` — algo' for e in expone] or ['- (nada)']
    lineas += ['### Consume']
    lineas += [f'- `{c}`' for c in consume] or ['- (nada)']
    lineas += ['', '## Verificación', '']
    return '\n'.join(lineas)


class Contratos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def ticket(self, nombre, texto_plan):
        carpeta = Path(self.tmp.name, nombre)
        carpeta.mkdir()
        if texto_plan is not None:
            (carpeta / 'plan.md').write_text(texto_plan, encoding='utf-8')
        return carpeta

    def correr(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_consumo_de_otro_ticket_y_orden(self):
        t1 = self.ticket('T1001-a', plan(['POST /internal/a/:id'], []))
        t2 = self.ticket('T1002-b', plan([], ['POST /internal/a/{sujetoId}` — de T1001']))
        rc, out = self.correr(t2, t1)
        self.assertEqual(rc, 0, out)
        self.assertIn('OK: 2 tickets, contratos cruzados', out)
        self.assertIn('ORDEN: T1001 T1002', out)

    def test_consumo_existente_se_acepta(self):
        t1 = self.ticket('T1001-a', plan([], ['GET /usuarios/:id` — existente']))
        rc, out = self.correr(t1)
        self.assertEqual(rc, 0, out)

    def test_consumo_sin_duenio(self):
        t1 = self.ticket('T1001-a', plan([], ['GET /nadie/lo/expone']))
        rc, out = self.correr(t1)
        self.assertEqual(rc, 1)
        self.assertIn('T1001 consume GET /nadie/lo/expone y nadie del lote lo expone', out)

    def test_origen_que_no_lo_expone(self):
        t1 = self.ticket('T1001-a', plan(['GET /x'], []))
        t2 = self.ticket('T1002-b', plan([], ['GET /y` — de T1001']))
        rc, out = self.correr(t1, t2)
        self.assertEqual(rc, 1)
        self.assertIn('T1002 consume GET /y de T1001, pero T1001 no lo expone', out)

    def test_origen_fuera_del_lote(self):
        t1 = self.ticket('T1001-a', plan([], ['GET /y` — de T9999']))
        rc, out = self.correr(t1)
        self.assertEqual(rc, 1)
        self.assertIn('T1001 consume GET /y de T9999, que no está en el lote', out)

    def test_expuesto_dos_veces(self):
        t1 = self.ticket('T1001-a', plan(['GET /x/:id'], []))
        t2 = self.ticket('T1002-b', plan(['GET /x/:otro'], []))
        rc, out = self.correr(t1, t2)
        self.assertEqual(rc, 1)
        self.assertIn('expuesto dos veces: GET /x/:otro (T1001 y T1002)', out)

    def test_ciclo(self):
        t1 = self.ticket('T1001-a', plan(['GET /a'], ['GET /b` — de T1002']))
        t2 = self.ticket('T1002-b', plan(['GET /b'], ['GET /a` — de T1001']))
        t3 = self.ticket('T1003-c', plan([], []))
        rc, out = self.correr(t1, t2, t3)
        self.assertEqual(rc, 1)
        self.assertIn('ciclo de dependencias entre: T1001, T1002', out)
        self.assertIn('ORDEN: T1003', out)

    def test_sin_seccion_contrato_es_error(self):
        t1 = self.ticket('T1001-a', '# Plan\n\n## Parte 1 — ms-a\nCubre: CA1\n')
        rc, out = self.correr(t1)
        self.assertEqual(rc, 2)
        self.assertIn('no tiene "## Contrato"', out)
        self.assertNotIn('OK', out)

    def test_contrato_sin_subsecciones_es_error(self):
        t1 = self.ticket('T1001-a', '# Plan\n\n## Contrato\n- `GET /x`\n')
        rc, out = self.correr(t1)
        self.assertEqual(rc, 2)
        self.assertIn('"### Expone" y "### Consume"', out)

    def test_falta_plan(self):
        t1 = self.ticket('T1001-a', None)
        rc, out = self.correr(t1)
        self.assertEqual(rc, 2)
        self.assertIn('falta plan.md', out)

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

    def test_deriva_con_rastro(self):
        t1 = self.ticket('T1001-a', plan(['POST /internal/permisos/usuarios'], []))
        wt = self.repo('ms-a')
        (wt / 'c.ts').write_text("@Controller('internal/permisos')\nclass C {\n  @Post('usuarios')\n  crear() {}\n}\n")
        rc, out = self.correr('--deriva', t1, '--worktree', f'T1001={wt}')
        self.assertEqual(rc, 0, out)
        self.assertIn('OK: cada Expone tiene rastro en su diff', out)

    def test_deriva_sin_rastro(self):
        t1 = self.ticket('T1001-a', plan(['POST /internal/permisos/usuarios'], []))
        wt = self.repo('ms-a')
        (wt / 'c.ts').write_text("@Post('otra-cosa')\n")
        rc, out = self.correr('--deriva', t1, '--worktree', f'T1001={wt}')
        self.assertEqual(rc, 1)
        self.assertIn('T1001: POST /internal/permisos/usuarios no tiene rastro en el diff', out)


if __name__ == '__main__':
    unittest.main()
```

Nota: el helper `plan()` arma cada Consume como `` - `VERBO /ruta` `` y el test agrega `` ` — de T1001 `` dentro del string, así que el backtick de cierre queda después de la ruta.

- [ ] **Step 2: Correr y verificar que fallan**

Run: `python3 -m unittest tests.test_contratos -v`
Expected: FAIL/ERROR en los 12 tests (el script no existe).

- [ ] **Step 3: Implementar**

`scripts/contratos.py`:

```python
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `python3 -m unittest tests.test_contratos -v`
Expected: 12 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/contratos.py tests/test_contratos.py
git commit -m "contratos.py: cruce Expone/Consume, orden del lote y deriva

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `scripts/fichas.py`

**Files:**
- Create: `scripts/fichas.py`
- Test: `tests/test_fichas.py`

**Interfaces:**
- Consumes: `contrato(carpeta)`, `seccion(texto, titulo, nivel)` de `contratos.py`; `economia(ticket: Path) -> list[str]` y `SIN_REGISTRO` de `hechos.py`.
- Produces: CLI `fichas.py <carpeta del ticket>` → Markdown de la ficha por stdout. Exit 0; 2 si la carpeta no existe.

- [ ] **Step 1: Escribir los tests**

`tests/test_fichas.py`:

```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'fichas.py'

SPEC = """# E9 — Orquestar la aceptación

## Objetivo

Que aceptar un compliance deje los permisos listos.

## Criterios de aceptación
- [ ] **CA1** — Acepta.

## Decisiones de contrato
- **E1 · Formato de ids:** string. Decisión del usuario.
- **E2 · P1 · Re-otorgar:** fila nueva (provisoria).
- **C1 · DECISIÓN MENOR del Baqueano · Nombres:** sin prefijo I.
"""

PLAN = """# Plan

## Parte 1 — ms-psp
Cubre: CA1
Crea la migración de las tablas nuevas.

## Parte 2 — apigateway-psp
Cubre: CA1

## Contrato
### Expone
- `POST /internal/permisos/usuarios` — alta
### Consume
- `GET /compliance/:id/permisos-psp` — de T23821

## Verificación
"""

REGISTRO = """| # | Rol | Modelo | Resultado | Duración / tokens |
|---|---|---|---|---|
| 1 | Generador de plan | sonnet | ok | 300 s · 120k tokens |
"""


class Fichas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name, 'T23822-orquestar')
        self.t.mkdir()
        (self.t / 'spec.md').write_text(SPEC, encoding='utf-8')
        (self.t / 'plan.md').write_text(PLAN, encoding='utf-8')
        (self.t / 'registro.md').write_text(REGISTRO, encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def correr(self):
        r = subprocess.run([sys.executable, str(SCRIPT), str(self.t)], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_ficha_completa(self):
        rc, out = self.correr()
        self.assertEqual(rc, 0, out)
        self.assertIn('# Ficha — E9 — Orquestar la aceptación', out)
        self.assertIn('Que aceptar un compliance deje los permisos listos.', out)
        self.assertIn('- ms-psp\n- apigateway-psp', out)
        self.assertIn('Crea la migración de las tablas nuevas.', out)
        self.assertIn('- Expone: POST /internal/permisos/usuarios', out)
        self.assertIn('- Consume: GET /compliance/:id/permisos-psp (de T23821)', out)
        self.assertIn('- **E2 · P1 · Re-otorgar:** fila nueva (provisoria).', out)
        self.assertIn('- **C1 · DECISIÓN MENOR del Baqueano · Nombres:** sin prefijo I.', out)
        self.assertNotIn('E1 · Formato de ids', out)
        self.assertIn('| Generador de plan | sonnet | 1 | 300 | 120000 | 0 | 0 |', out)

    def test_plan_sin_contrato_no_rompe(self):
        (self.t / 'plan.md').write_text('# Plan\n\n## Parte 1 — ms-psp\nCubre: CA1\n', encoding='utf-8')
        rc, out = self.correr()
        self.assertEqual(rc, 0, out)
        self.assertIn('## Contrato\nsin registro', out)

    def test_sin_spec_ni_plan(self):
        (self.t / 'spec.md').unlink()
        (self.t / 'plan.md').unlink()
        rc, out = self.correr()
        self.assertEqual(rc, 0, out)
        self.assertIn('# Ficha — T23822-orquestar', out)
        self.assertIn('## Qué pide\nsin registro', out)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `python3 -m unittest tests.test_fichas -v`
Expected: FAIL en los 3.

- [ ] **Step 3: Implementar**

`scripts/fichas.py`:

```python
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `python3 -m unittest tests.test_fichas -v`
Expected: 3 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/fichas.py tests/test_fichas.py
git commit -m "fichas.py: ficha de cada ticket para el juicio de valor

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `scripts/correr_casos.py`

**Files:**
- Create: `scripts/correr_casos.py`
- Test: `tests/test_correr_casos.py`

**Interfaces:**
- Consumes: `casos_de_tests(tests) -> [(id, criterio)]` y `seccion(texto, titulo)` de `trazabilidad.py`.
- Produces: CLI `correr_casos.py <carpeta del ticket> [--red] [--solo T01,T05] [--timeout 300]`. GREEN: líneas `T01 · <ms> · PASA|FALLA`, salida cruda indentada de cada falla, `RESULTADO: X pasan / Y fallan` (+ ` / Z sin script`). RED: líneas `… · esperado falla|pasa · OK|NO`, `RESULTADO RED: X dieron lo esperado / Y no`. Exit 0 / 1 / 2.

- [ ] **Step 1: Escribir los tests**

`tests/test_correr_casos.py`:

```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'correr_casos.py'

TESTS = """# Tests

## Tabla de casos de prueba

| ID | Criterio | Precondición | Acción | Esperado | Código | Esperado en RED |
|---|---|---|---|---|---|---|
| T01 | CA1 | nada | `curl -s x | jq .` | 201 | 201 | falla |
| T02 | regresión | nada | listar | 200 | 200 | pasa |

## Preparación de datos de prueba
"""


class CorrerCasos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name, 'T1001-a')
        (self.t / 'casos' / 'ms-a').mkdir(parents=True)
        (self.t / 'tests.md').write_text(TESTS, encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def caso(self, caso_id, cuerpo, ms='ms-a'):
        carpeta = self.t / 'casos' / ms
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / f'{caso_id}.sh').write_text('#!/usr/bin/env bash\n' + cuerpo + '\n')

    def correr(self, *extra):
        r = subprocess.run([sys.executable, str(SCRIPT), str(self.t), *extra], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_green_pasa_y_falla_con_salida_cruda(self):
        self.caso('T01', 'echo "esperaba 201, vino 500"; exit 1')
        self.caso('T02', 'echo ok; exit 0')
        rc, out = self.correr()
        self.assertEqual(rc, 1)
        self.assertIn('T01 · ms-a · FALLA', out)
        self.assertIn('    esperaba 201, vino 500', out)
        self.assertIn('T02 · ms-a · PASA', out)
        self.assertIn('RESULTADO: 1 pasan / 1 fallan', out)

    def test_green_todo_pasa(self):
        self.caso('T01', 'exit 0')
        self.caso('T02', 'exit 0')
        rc, out = self.correr()
        self.assertEqual(rc, 0, out)
        self.assertIn('RESULTADO: 2 pasan / 0 fallan', out)

    def test_timeout_marca_falla_y_sigue(self):
        self.caso('T01', 'sleep 5')
        self.caso('T02', 'exit 0')
        rc, out = self.correr('--timeout', '1')
        self.assertEqual(rc, 1)
        self.assertIn('T01 · ms-a · FALLA', out)
        self.assertIn('TIMEOUT tras 1 s', out)
        self.assertIn('T02 · ms-a · PASA', out)

    def test_red_lo_esperado(self):
        self.caso('T01', 'exit 1')
        self.caso('T02', 'exit 0')
        rc, out = self.correr('--red')
        self.assertEqual(rc, 0, out)
        self.assertIn('T01 · ms-a · FALLA · esperado falla · OK', out)
        self.assertIn('RESULTADO RED: 2 dieron lo esperado / 0 no', out)

    def test_red_no_discrimina(self):
        self.caso('T01', 'exit 0')
        self.caso('T02', 'exit 0')
        rc, out = self.correr('--red')
        self.assertEqual(rc, 1)
        self.assertIn('T01 · ms-a · PASA · esperado falla · NO', out)

    def test_caso_sin_script(self):
        self.caso('T01', 'exit 0')
        rc, out = self.correr()
        self.assertEqual(rc, 1)
        self.assertIn('T02 · sin script', out)
        self.assertIn('/ 1 sin script', out)

    def test_solo(self):
        self.caso('T01', 'exit 1')
        self.caso('T02', 'exit 0')
        rc, out = self.correr('--solo', 'T02')
        self.assertEqual(rc, 0, out)
        self.assertNotIn('T01', out)

    def test_sin_carpeta_casos_es_error(self):
        (self.t / 'casos' / 'ms-a').rmdir()
        (self.t / 'casos').rmdir()
        rc, out = self.correr()
        self.assertEqual(rc, 2)
        self.assertIn('no hay casos', out)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `python3 -m unittest tests.test_correr_casos -v`
Expected: FAIL en los 8.

- [ ] **Step 3: Implementar**

`scripts/correr_casos.py`:

```python
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
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `python3 -m unittest tests.test_correr_casos -v`
Expected: 8 tests OK.

- [ ] **Step 5: Suite completa y commit**

Run: `python3 -m unittest discover -s tests`
Expected: OK (34 previos + 23 nuevos = 57).

```bash
git add scripts/correr_casos.py tests/test_correr_casos.py
git commit -m "correr_casos.py: RED y GREEN como scripts, sin tokens

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Tipos de agente y su test

**Files:**
- Create: `agents/coordinador.md`, `agents/escribano.md`, `agents/baqueano.md`, `agents/generador-plan.md`, `agents/generador-tests.md`, `agents/alineador.md`, `agents/verificador.md`, `agents/corrector.md`, `agents/qa.md`, `agents/implementador.md`, `agents/obrero.md`, `agents/obrero-alto.md`, `agents/revisor.md`, `agents/cronista.md`, `agents/juez.md`
- Test: `tests/test_agentes.py`

**Interfaces:**
- Consumes: skills existentes (`escribano`, `baqueano`, `planear-ticket`, `planear-tests-ticket`, `implementar-ticket`, `revisar-ticket`, `cronista`) y las de Task 5/6 (`resolver-proyecto`, `juzgar-proyecto`).
- Produces: tipos `clarabella:<nombre>` para `Agent(subagent_type: "clarabella:<nombre>")` y `claude --agent clarabella:<nombre>`.

Formato del frontmatter (una clave por línea; `skills` como lista `[…]`; `tools` como texto separado por comas):

- [ ] **Step 1: Escribir el test**

`tests/test_agentes.py`:

```python
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
AGENTES = RAIZ / 'agents'

ROLES = {
    'coordinador': ('haiku', 'medium'),
    'escribano': ('sonnet', 'high'),
    'baqueano': ('sonnet', 'medium'),
    'generador-plan': ('sonnet', 'high'),
    'generador-tests': ('sonnet', 'high'),
    'alineador': ('opus', 'high'),
    'verificador': ('sonnet', 'medium'),
    'corrector': ('sonnet', 'medium'),
    'qa': ('sonnet', 'high'),
    'implementador': ('sonnet', 'medium'),
    'obrero': ('sonnet', 'medium'),
    'obrero-alto': ('sonnet', 'high'),
    'revisor': ('sonnet', 'medium'),
    'cronista': ('sonnet', 'medium'),
    'juez': ('opus', 'high'),
}
DESPACHAN = {'coordinador', 'implementador'}


def frontmatter(ruta):
    texto = ruta.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n(.+)', texto, re.S)
    assert m, f'{ruta.name}: sin frontmatter o sin cuerpo'
    campos = {}
    for linea in m.group(1).splitlines():
        clave, _, valor = linea.partition(':')
        campos[clave.strip()] = valor.strip()
    return campos


def lista(valor):
    return [x.strip() for x in valor.strip('[]').split(',') if x.strip()]


class Agentes(unittest.TestCase):
    def test_estan_todos_los_roles(self):
        self.assertEqual({p.stem for p in AGENTES.glob('*.md')}, set(ROLES))

    def test_modelo_y_esfuerzo_del_spec(self):
        for nombre, (modelo, esfuerzo) in ROLES.items():
            f = frontmatter(AGENTES / f'{nombre}.md')
            self.assertEqual(f.get('name'), nombre)
            self.assertTrue(f.get('description'), nombre)
            self.assertEqual(f.get('model'), modelo, nombre)
            self.assertEqual(f.get('effort'), esfuerzo, nombre)

    def test_skills_existen(self):
        for ruta in AGENTES.glob('*.md'):
            for skill in lista(frontmatter(ruta).get('skills', '')):
                self.assertTrue(skill.startswith('clarabella:'), f'{ruta.name}: {skill}')
                self.assertTrue((RAIZ / 'skills' / skill.split(':', 1)[1] / 'SKILL.md').is_file(),
                                f'{ruta.name}: no existe la skill {skill}')

    def test_quien_despacha_y_a_quien(self):
        for ruta in AGENTES.glob('*.md'):
            f = frontmatter(ruta)
            despachados = re.findall(r'Agent\(([^)]*)\)', f.get('tools', ''))
            if ruta.stem in DESPACHAN:
                self.assertTrue(despachados, f'{ruta.name} tiene que listar a quién despacha')
                for tipo in lista(despachados[0]):
                    self.assertTrue(tipo.startswith('clarabella:'), f'{ruta.name}: {tipo}')
                    self.assertTrue((AGENTES / f'{tipo.split(":", 1)[1]}.md').is_file(),
                                    f'{ruta.name}: no existe el agente {tipo}')
            else:
                self.assertFalse(despachados, f'{ruta.name} no despacha')
                self.assertIn('Agent', lista(f.get('disallowedTools', '')), f'{ruta.name}')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python3 -m unittest tests.test_agentes -v`
Expected: FAIL (no existe `agents/`).

- [ ] **Step 3: Crear los 15 agentes**

`agents/coordinador.md`:
```markdown
---
name: coordinador
description: Coordinador de resolver-proyecto. Corre como sesión principal con `claude --agent clarabella:coordinador` desde la raíz del workspace dcac-ia-context; despacha a los roles del lote y lleva estado.json. No usar como subagente.
model: haiku
effort: medium
skills: [clarabella:resolver-proyecto]
tools: Read, Write, Edit, Bash, Glob, Grep, Skill, Agent(clarabella:escribano, clarabella:baqueano, clarabella:generador-plan, clarabella:generador-tests, clarabella:alineador, clarabella:verificador, clarabella:corrector, clarabella:qa, clarabella:implementador, clarabella:revisor, clarabella:cronista)
---

Sos el Coordinador de Clarabella en `resolver-proyecto` (skill precargada). Seguila al pie
de la letra.

- Tu trabajo es mecánico: leer `estado.json`, despachar con las plantillas de la skill,
  guardar rutas, registrar cada subagente en `registro.md` y actualizar el estado.
- No resumís, no decidís, no interpretás. Al usuario le mostrás rutas de archivos o le
  copiás textual lo que devolvió un rol.
- Lo que necesita criterio lo hace el rol que corresponde. Si no sabés qué rol, pausá y
  preguntale al usuario.
- Hablás en español rioplatense, corto.
```

`agents/escribano.md`:
```markdown
---
name: escribano
description: Escribano de resolver-proyecto — revisa la spec de un ticket antes de despacharle generadores y lista lo que falta definir.
model: sonnet
effort: high
skills: [clarabella:escribano]
disallowedTools: Agent
---

Sos el Escribano de un ticket. Seguí la skill `escribano` (precargada) para el ticket y la
carpeta que te pasa el prompt. Escribí `escritura.md` y devolvé el contrato de la skill.
```

`agents/baqueano.md`:
```markdown
---
name: baqueano
description: Baqueano de resolver-proyecto — contesta desde las fuentes las DUDAS de un generador y prepara para el usuario solo las decisiones.
model: sonnet
effort: medium
skills: [clarabella:baqueano]
disallowedTools: Agent
---

Sos el Baqueano de un generador. Seguí la skill `baqueano` (precargada). En
`resolver-proyecto` podés clasificar `DECISIÓN MENOR` y `PROVISORIA` (ver la skill).
Devolvé el contrato de la skill.
```

`agents/generador-plan.md`:
```markdown
---
name: generador-plan
description: Generador del plan de un ticket en resolver-proyecto — escribe plan.md desde la spec, con Cubre por Parte y la sección Contrato.
model: sonnet
effort: high
skills: [clarabella:planear-ticket]
disallowedTools: Agent
---

Sos el generador del plan de un ticket. Seguí `planear-ticket` (precargada) en modo
orquestado y su sección "Como generador de `resolver-proyecto`". Tu única fuente de lo
pedido es `spec.md`; nunca leas `tests.md`. Cada Parte lleva `Cubre:` y el plan lleva
`## Contrato`. Devolvé ARTEFACTO/DUDAS/SUGERENCIAS/ESTADO.
```

`agents/generador-tests.md`:
```markdown
---
name: generador-tests
description: Generador de los tests de un ticket en resolver-proyecto — escribe tests.md desde la spec, sin ver el plan.
model: sonnet
effort: high
skills: [clarabella:planear-tests-ticket]
disallowedTools: Agent
---

Sos el generador de los tests de un ticket. Seguí `planear-tests-ticket` (precargada) en
modo orquestado y su sección "Como generador de `resolver-proyecto`". Tu única fuente es
`spec.md`; nunca leas `plan.md`. Columna `Criterio` en cada caso. Devolvé
ARTEFACTO/DUDAS/SUGERENCIAS/ESTADO.
```

`agents/alineador.md`:
```markdown
---
name: alineador
description: Alineador de resolver-proyecto — cruza los contratos de todos los tickets del lote y marca los choques del hilado, con fuente, antes de implementar.
model: opus
effort: high
disallowedTools: Agent, Edit
---

Sos el Alineador del lote. Una sola pasada. No corregís nada: marcás.

**Leés:** `lote/contratos.txt` (salida de `contratos.py`, con la línea `ORDEN:`), el
`revision/trazabilidad.txt` de cada ticket, la sección `## Contrato` de cada `plan.md`, y
`## Criterios de aceptación` y `## Decisiones de contrato` de cada `spec.md`. Abrís un
`plan.md` o un `tests.md` entero **solo** cuando un choque lo requiere, y solo la sección
que vas a citar. No ejecutás nada.

**Buscás:** consumos cuya firma (body, respuesta, códigos) no coincide con la del que
expone; supuestos de un ticket sobre el estado que deja otro; el mismo dato con dos nombres
o dos formatos entre tickets; decisiones de un ticket que contradicen las de otro; tests de
un ticket que asumen un comportamiento de otro que su plan no implementa; un orden del lote
que no cierra con lo que cada plan dice que necesita.

**Escribís** `lote/alineacion.md`:

    # Alineación — <lote>

    ## Orden del lote
    <copiado de la línea ORDEN: de contratos.txt; si propone cambiarlo, por qué>

    ## Choques
    ### A1 · bloqueante | menor
    - **Tickets:** T##### (plan|tests) ↔ T##### (plan|tests)
    - **Dice uno:** <cita, archivo § sección>
    - **Dice el otro:** <cita, archivo § sección>
    - **Propuesta:** <qué cambiar y en cuál>
    - **Va a:** T##### plan.md | T##### tests.md

    ## Lo que el hilado no resuelve
    <decisiones que ningún artefacto toma y que hacen falta para que el lote cierre>

Hasta 15 choques, bloqueantes primero. Lo que no tiene fuente no se reporta.

**Contrato de salida:**

    ARTEFACTO: lote/alineacion.md
    CHOQUES: <n> (<b> bloqueantes)
    SIN_RESOLVER: <n>
    ESTADO: completo
```

`agents/verificador.md`:
```markdown
---
name: verificador
description: Verificador de resolver-proyecto — Chain-of-Verification sobre un ticket; arma preguntas desde la spec sin ver el plan y las contesta leyendo solo plan y tests.
model: sonnet
effort: medium
disallowedTools: Agent, Edit
---

Sos el Verificador de un ticket. Técnica: Chain-of-Verification. La independencia es el
punto: no leés nada del generador salvo sus artefactos, y las preguntas las escribís
**antes** de leerlos.

1. Leé `spec.md` (criterios, alcance, decisiones de contrato). **Escribí ya** en
   `revision/verificacion.md` la sección `## Preguntas`: hasta 12, concretas y respondibles
   ("¿qué devuelve si el permiso está revocado?", "¿qué tabla guarda X?"), cada una con la
   parte de la spec de la que sale. No abras `plan.md` ni `tests.md` antes de escribirlas.
2. Recién después leé `plan.md` y `tests.md` y contestá cada pregunta con lo que dicen
   (cita y sección). No uses tu conocimiento ni el código para completar.
3. Hallazgo = una pregunta que el artefacto no contesta, o que contesta contradiciendo la
   spec, o que plan y tests contestan distinto.

Formato de `revision/verificacion.md`:

    # Verificación — T#####

    ## Preguntas
    | # | Pregunta | Sale de (spec § …) |

    ## Respuestas
    | # | Plan dice | Tests dicen | Resultado: OK, FALTA o CONTRADICE |

    ## Hallazgos
    ### V1 · bloqueante | menor
    - **Pregunta:** <#>
    - **Dice la spec:** <cita>
    - **Dice el artefacto:** <cita o "no lo contesta">
    - **Va a:** plan.md | tests.md

No ejecutás nada. **Contrato:** `ARTEFACTO / PREGUNTAS: n / HALLAZGOS: n (b bloqueantes) / ESTADO`.
```

`agents/corrector.md`:
```markdown
---
name: corrector
description: Corrector de resolver-proyecto — corrige un artefacto (plan.md o tests.md) solo en lo que marcan los hallazgos que recibe, sin rehacer nada.
model: sonnet
effort: medium
disallowedTools: Agent
---

Sos un Corrector nuevo. Recibís un artefacto (`plan.md` o `tests.md` de un ticket) y una
lista de hallazgos con su evidencia (choques del Alineador, hallazgos del Verificador,
errores de formato de un script, o una falla clasificada por el Implementador).

- Cambiás **solo** lo que marcan. No reescribís secciones enteras ni "mejorás" lo demás.
- Mantené los formatos: `Cubre:` por Parte, `## Contrato` con `### Expone`/`### Consume`,
  columna `Criterio` segunda y `Esperado en RED` última.
- Si un hallazgo no corresponde, no lo apliques: devolvé `DESACUERDO: <id> — <por qué, con
  fuente>`.
- Nunca leas el otro artefacto del ticket (si corregís `plan.md`, no leas `tests.md`, y al
  revés), salvo que el hallazgo cite una línea puntual de él.

**Contrato:** `ARTEFACTO / CORREGIDOS: <ids> / DESACUERDOS: <ids o (ninguno)> / ESTADO`.
```

`agents/qa.md`:
```markdown
---
name: qa
description: QA de resolver-proyecto — convierte los casos de tests.md de un ticket en scripts ejecutables casos/<ms>/T##.sh, una sola vez, para que RED y GREEN no gasten tokens.
model: sonnet
effort: high
disallowedTools: Agent
---

Sos el QA de un ticket. Escribís **un script por caso** de la tabla de `tests.md`:
`casos/<ms>/<ID>.sh` (el `<ms>` es el servicio al que pega el caso). No implementás nada ni
corrés los casos (eso lo hace `correr_casos.py`).

**`casos/env.sh`** (uno por ticket): exporta host, puertos, token y la conexión a la DB de
pruebas **del ticket** (contenedores `T#####-<ms>`, DB `T#####-db`), sacados de
`tests.md` § Lista de curls y del entorno del ticket. Nunca la DB de desarrollo (:3306).

**Cada caso:**

    #!/usr/bin/env bash
    set -u
    source "$(dirname "$0")/../env.sh"
    # T05 — <título del caso> (Criterio: CA2)
    <preparación de datos del caso, con ids propios del caso>
    trap '<teardown de lo que creó este caso>' EXIT
    respuesta=$(curl -s -o /tmp/T05.body -w '%{http_code}' …)
    echo "HTTP $respuesta"; head -c 2000 /tmp/T05.body; echo
    <query de verificación, imprimiendo su resultado>
    [ "$respuesta" = "201" ] || { echo "esperaba 201"; exit 1; }
    <aserción sobre la query> || { echo "esperaba <…>"; exit 1; }
    exit 0

- Autocontenido: prepara, ejecuta, verifica, limpia. Exit 0 pasa, 1 falla.
- Imprime la evidencia cruda (código, body recortado, resultado de la query): es lo que
  después lee quien clasifica una falla.
- Las aserciones salen de "Esperado" y "Código" de la tabla y de "Cómo verificar éxito".
  No inventes esperados: si `tests.md` no los define, es DUDA.

Si te re-despachan con un RED que no dio lo esperado, corregí **solo** los scripts de los
casos marcados.

**Contrato:** `ARTEFACTO: casos/ / CASOS: <n> / DUDAS / ESTADO`.
```

`agents/implementador.md`:
```markdown
---
name: implementador
description: Implementador de resolver-proyecto — lleva un ticket de RED a GREEN despachando un Obrero por microservicio, corriendo los casos y clasificando cada falla.
model: sonnet
effort: medium
skills: [clarabella:implementar-ticket]
tools: Read, Write, Edit, Bash, Glob, Grep, Skill, Agent(clarabella:obrero, clarabella:obrero-alto, clarabella:corrector, clarabella:qa)
---

Sos el Implementador de un ticket. No escribís código: lo escriben los Obreros. Vos
despachás, corrés los casos y decidís a quién vuelve cada falla.

**Recibís:** ticket, carpeta, repos y worktrees, presupuesto de vueltas, y (si es una
corrección post-revisión) la ruta de `revision/revision-impl-<ms>.md`.

**Cada vuelta:**
1. Despachá un `clarabella:obrero` por microservicio con trabajo pendiente, todos en el mismo
   mensaje (nunca dos en el mismo repo):

       Agent(subagent_type: "clarabella:obrero", description: "Obrero <ms> T#####",
             prompt: "Implementá la Parte <N> (<ms>) de T##### (carpeta <ticket>) en el
                      worktree <ruta>, siguiendo implementar-ticket § Como Obrero de
                      resolver-proyecto. <En vueltas siguientes: corregí solo esto: <salida
                      cruda de los casos que fallan en tu repo>.> Devolvé el contrato.")

2. GREEN: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/correr_casos.py <ticket> > <ticket>/revision/testeo/green-<n>.txt`
3. Si todo pasa: terminaste (`ESTADO: green`).
4. Clasificá cada caso que falla leyendo su salida cruda y el plan:
   - `bug-implementacion` → vuelve al Obrero de ese repo.
   - `hueco-del-plan` → un `clarabella:corrector` con `plan.md` y la evidencia; después el
     Obrero implementa lo agregado.
   - `test-mal-documentado` → un `clarabella:corrector` con `tests.md` y la evidencia, y un
     `clarabella:qa` para rehacer solo ese script.
   - `ambiguedad-negocio` o `regresion-preexistente` → no se arregla acá: `ESTADO: pausa`.
5. **Escalado:** si el mismo caso falló en las dos últimas vueltas, el próximo intento de
   ese repo va a `clarabella:obrero-alto` con tu diagnóstico.
6. Anotá la vuelta en `revision/implementacion.md`:

       ## Vuelta <n>
       - Firma: T03 bug-implementacion · T07 hueco-del-plan
       - Despachos: obrero ms-psp, corrector plan
       - sin-progreso: <repo, si sus bug-implementacion no bajaron en dos vueltas>

**Cortás** con: GREEN completo (`green`); la misma firma tres vueltas seguidas
(`estancado`); vueltas agotadas (`presupuesto`); `ambiguedad-negocio`,
`regresion-preexistente`, entorno caído o una corrección que falló dos veces (`pausa`).
`sin-progreso` en un repo: pedile al Obrero un diagnóstico antes de la vuelta siguiente; si
el enfoque estaba mal, `git -C <worktree> stash push -u -m "T##### impl <ms>"` y que
reescriba desde master.

**Contrato:**

    ARTEFACTO: revision/implementacion.md
    ESTADO: green | estancado | presupuesto | pausa
    MOTIVO: <solo si no es green>
    VUELTAS: <n>
```

`agents/obrero.md`:
```markdown
---
name: obrero
description: Obrero de resolver-proyecto — implementa la Parte de un microservicio de un ticket en su worktree.
model: sonnet
effort: medium
skills: [clarabella:implementar-ticket]
disallowedTools: Agent
---

Sos un Obrero. Seguí `implementar-ticket` (precargada), sección "Como Obrero de
`resolver-proyecto`": implementás solo la Parte de tu repo, en tu worktree, anotás desvíos
en `revision/notas-<ms>.md` y no corrés los casos. Devolvé el contrato de modo orquestado
de la skill.
```

`agents/obrero-alto.md`: el mismo contenido que `obrero.md`, con `name: obrero-alto`, `effort: high` y esta `description`: `Obrero de resolver-proyecto con esfuerzo alto — para un caso que falló dos vueltas seguidas; recibe el diagnóstico del Implementador.` y una línea más al final del cuerpo: `Te despacharon porque este caso falló dos veces: empezá por el diagnóstico que trae el prompt.`

`agents/revisor.md`:
```markdown
---
name: revisor
description: Revisor de resolver-proyecto — revisa la implementación de un microservicio en una sola pasada, después de GREEN.
model: sonnet
effort: medium
skills: [clarabella:revisar-ticket]
disallowedTools: Agent, Edit
---

Sos el revisor de `revisar-ticket` (precargada), rol revisor, modo implementación. Una
pasada, hasta 10 hallazgos con fuente. Devolvé el contrato de la skill.
```

`agents/cronista.md`:
```markdown
---
name: cronista
description: Cronista de resolver-proyecto — cuenta lo que pasó en un ticket desde revision/hechos.md y redacta los borradores para Phabricator.
model: sonnet
effort: medium
skills: [clarabella:cronista]
disallowedTools: Agent
---

Sos el Cronista. Seguí la skill `cronista` (precargada) para el ticket del prompt. Devolvé
su contrato.
```

`agents/juez.md`:
```markdown
---
name: juez
description: Juez de resolver-proyecto. Corre como sesión aparte con `claude --agent clarabella:juez` desde la raíz del workspace; dictamina si la solución de un lote sirve al proyecto antes de implementarla. No usar como subagente.
model: opus
effort: high
skills: [clarabella:juzgar-proyecto]
disallowedTools: Agent
---

Sos el Juez de Clarabella. Seguí `juzgar-proyecto` (precargada). No participaste del lote y
eso es lo que te hace útil: juzgás si la solución **sirve**, no si está bien hecha. Hablás
en español rioplatense, directo. La decisión es del usuario.
```

- [ ] **Step 4: Correr el test**

Run: `python3 -m unittest tests.test_agentes -v`
Expected: FAIL solo en `test_skills_existen` (faltan `resolver-proyecto` y `juzgar-proyecto`, que crean las Tasks 5 y 6). Los otros 3 OK.

- [ ] **Step 5: Commit**

```bash
git add agents tests/test_agentes.py
git commit -m "Tipos de agente de resolver-proyecto con modelo y esfuerzo por rol

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Skill `juzgar-proyecto`

**Files:**
- Create: `skills/juzgar-proyecto/SKILL.md`

**Interfaces:**
- Consumes: `lote/fichas/*.md` (Task 2), `lote/alineacion.md` y `lote/contratos.txt` (Task 6).
- Produces: `lote/dictamen.md` con una línea `DECISIÓN: PENDIENTE | APROBADO | RECORTADO: … | FRENADO: …` que lee el Coordinador.

- [ ] **Step 1: Crear la skill**

````markdown
---
name: juzgar-proyecto
description: Usar en una sesión aparte (claude --agent clarabella:juez) para dictaminar si la solución de un lote de resolver-proyecto sirve al proyecto, antes de implementarla — no si está bien hecha, eso lo cubren la alineación y los tests. Lee las fichas, la alineación y los contratos, escribe dictamen.md y deja que el usuario decida aprobar, recortar o frenar. Triggers — "juzgá el lote L-…", "¿vale la pena esto?", "dictamen del proyecto". NO revisa calidad técnica, NO implementa.
---

# Juzgar proyecto

El Juez no participó del lote. Por eso puede preguntar lo que nadie adentro pregunta:
**¿esto sirve?** Si está bien hecho ya lo cubrieron la alineación, la corrección y los
tests. Acá no se discute calidad técnica.

## Qué leés

En `docs/{proyecto}/lotes/<lote>/`:
- `fichas/*.md`: una por ticket (qué pide, repos, migraciones, contrato, lo decidido sin el
  usuario, costo hasta acá).
- `alineacion.md`: choques y lo que el hilado no resuelve.
- `contratos.txt`: el cruce de contratos y el orden del lote.
- `riesgos.md`, si existe: lo que la corrección no cerró.

De cada ticket, de `spec.md` solo `## Objetivo` (o la descripción) y `## Criterios de
aceptación`. Si existe, `docs/{proyecto}/decisiones.md`. Del negocio,
`dcac-context/context/business/` solo para verificar algo puntual que vas a afirmar.

**No leés** planes ni tests enteros ni código: si un dato del dictamen lo necesita, abrís
solo la sección que vas a citar.

## Las cuatro preguntas

1. **¿Resuelve el problema que originó los tickets?** Si se implementa todo, ¿el problema
   deja de existir? ¿Queda algo del problema sin ticket?
2. **¿El costo y la complejidad están a la altura del beneficio?** Repos tocados,
   migraciones, contratos nuevos, decisiones tomadas sin el usuario, frente a lo que se
   gana.
3. **¿Hay una alternativa más simple que nadie consideró?** Una concreta, con qué se
   ahorra y qué se pierde. "Se podría simplificar" no es una alternativa.
4. **¿Qué riesgo deja?** Datos, permisos, el módulo financiero (DCP / `ms-decampopagos`),
   deuda técnica, dependencias con tickets fuera del lote.

## El dictamen — `dictamen.md`

```markdown
# Dictamen — <lote>

## Veredicto propuesto
SIRVE | SIRVE CON RECORTE | NO SIRVE — <una línea>

## 1. ¿Resuelve el problema?
## 2. Costo y beneficio
## 3. Alternativa más simple
## 4. Riesgo

## Recorte propuesto
<solo si SIRVE CON RECORTE: qué tickets salen o cambian, y por qué>

## Decisión del usuario
DECISIÓN: PENDIENTE
```

Reglas: cada afirmación con su fuente (archivo § sección). Hechos y opinión separados: la
opinión dice "a mi juicio". Nada sobre calidad técnica.

## Después

Le presentás el dictamen al usuario y lo discuten. **Decide el usuario.** Cuando decide,
reemplazás la línea `DECISIÓN: PENDIENTE` por exactamente una de:

- `DECISIÓN: APROBADO`
- `DECISIÓN: RECORTADO: <qué tickets salen y qué cambia en los que quedan>`
- `DECISIÓN: FRENADO: <motivo>`

Y le decís que vuelva a la sesión del Coordinador y le avise. No tocás nada más.

## Errores comunes

- **Juzgar si está bien hecho** → no es tu pregunta.
- **Proponer "simplificar" sin una alternativa concreta** → no es una alternativa.
- **Escribir la decisión vos** → la toma el usuario; vos escribís la línea con lo que dijo.
- **Leer los planes enteros** → solo la sección que vas a citar.
````

- [ ] **Step 2: Commit**

```bash
git add skills/juzgar-proyecto
git commit -m "juzgar-proyecto: el Juez dictamina si la solución sirve, antes de implementar

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Skill `resolver-proyecto`

**Files:**
- Create: `skills/resolver-proyecto/SKILL.md`

**Interfaces:**
- Consumes: CLIs de Tasks 1-3 y de 0.5.0 (`trazabilidad.py`, `reglas.py`, `hechos.py`); tipos de agente de Task 4; `dictamen.md` de Task 5.
- Produces: el procedimiento que precarga `clarabella:coordinador`; `estado.json`; `lote/contratos.txt`, `lote/riesgos.md`, `lote/cierre.md`.

- [ ] **Step 1: Crear la skill**

````markdown
---
name: resolver-proyecto
description: Usar cuando el usuario quiere que Clarabella resuelva sola uno o más tickets relacionados del workspace dcac-ia-context — un Coordinador despacha generadores de plan y tests, alinea los contratos entre tickets, corrige con evidencia, frena para el juicio de valor (sesión aparte) antes de implementar, y después implementa y testea en el orden de las dependencias. La precarga el agente clarabella:coordinador (claude --agent clarabella:coordinador). Triggers — "resolvé estos tickets", "resolvé T##### solo", "proyecto con T#####, T#####", "resolvelo solo". NO para resolver un ticket paso a paso: eso es resolver-ticket.
---

# Resolver proyecto

Sos el **Coordinador**. Tu trabajo es mecánico: leer `estado.json`, despachar con las
plantillas de abajo, guardar rutas, registrar y actualizar el estado. **No resumís, no
decidís, no interpretás.** Al usuario le mostrás rutas o le copiás textual lo que devolvió
un rol.

**Cómo se arranca:** `claude --agent clarabella:coordinador` desde la raíz del workspace
dcac-ia-context. Si no tenés la herramienta `Agent`, no estás corriendo como el
Coordinador: decíselo al usuario con ese comando y no sigas.

## El lote

```
docs/{proyecto}/lotes/L-<AAAA-MM-DD>-<slug>/      ({lote})
├── estado.json   ├── registro.md   ├── contratos.txt   ├── alineacion.md
├── riesgos.md    ├── fichas/       ├── dictamen.md     └── cierre.md
docs/{proyecto}/{tipo}/T#####-{slug}/             ({ticket}, uno por ticket)
```

`estado.json`:

```json
{
  "lote": "L-2026-10-09-permisos", "proyecto": "permisos-psp", "carpeta": "docs/permisos-psp/lotes/L-2026-10-09-permisos",
  "paso": "0-armar",
  "juicio": true,
  "presupuesto": {"vueltas_green": 8},
  "orden": [],
  "tickets": {
    "T23815": {"tipo": "desarrollo", "slug": "tablas-y-repositorios", "carpeta": "docs/permisos-psp/desarrollo/T23815-tablas-y-repositorios",
               "repos": ["ms-psp"], "worktrees": {"ms-psp": ".worktrees/T23815-tablas-y-repositorios/ms-psp"},
               "estado": "spec"}
  },
  "pausa": null
}
```

`paso`: `0-armar`, `1-generar`, `3-alinear`, `4-corregir`, `5-juicio`, `6-implementar`,
`7-cierre`, `terminado`. `estado` de un ticket: `spec`, `generado`, `corregido`,
`aprobado`, `fuera`, `red`, `green`, `revisado`, `cronica`, `enviado`. `pausa`: `null` o
`{"motivo": "...", "ticket": "...", "archivo": "..."}`.

Al retomar una sesión, leé `estado.json` y seguí desde `paso`.

## Registro

Cada subagente que despachás es una fila de `{lote}/registro.md`, con la duración y los
tokens de su notificación:

```
| # | Ticket | Rol | Resultado | Duración / tokens |
| 7 | T23815 | generador-plan | plan.md, 0 dudas | 312 s · 118k tokens |
```

## Paso 0 — Armar el lote

1. Preguntale al usuario, en un solo mensaje: los tickets (`T#####` y título), el tipo de
   cada uno, el proyecto (una carpeta de `docs/`), el texto de cada ticket, el presupuesto
   (default: 8 vueltas de GREEN por ticket) y si hay juicio (default: sí con dos o más
   tickets; con uno, que elija).
2. Creá `{lote}`, `estado.json`, `registro.md` y la carpeta de cada ticket con su
   `spec.md` (el texto tal cual).
3. Por cada repo de cada ticket, invocá `preparar-repo` (etapa A). La etapa B de
   `aislar-ticket` (contenedores y DB del ticket) corrés con Bash en background.
4. Despachá un Escribano por ticket, todos en el mismo mensaje (plantilla **E**).
5. Mostrale al usuario la lista de `escritura.md` (rutas) y pedile que conteste punto por
   punto. No los resumas.
6. Con las respuestas: anotalas en cada `escritura.md` ("Decisión del usuario") y en
   `spec.md` § Decisiones de contrato (`E1`, `E2`…). Numerá los criterios de cada spec:
   `- [ ] **CA1** — <texto tal cual>`.
7. `paso: 1-generar`.

## Pasos 1 y 2 — Generadores

Por ticket, un generador de plan y uno de tests, todos en el mismo mensaje (plantillas
**GP** y **GT**). Guardá el id de cada uno solo para pasarle respuestas a sus DUDAS.

DUDAS de un generador → un Baqueano para ese generador (plantilla **B**):
- `RESPONDIDA`, `PRECEDENTE`, `DECISIÓN MENOR` → se la pasás al generador con
  `SendMessage`, textual.
- `PROVISORIA` → igual, y la copiás a `{ticket}/revision/provisorias.md`.
- `AL USUARIO` → juntás las de todos y se las mostrás al usuario (rutas de
  `revision/consultas-*.md`). Lo que decida va a `spec.md` § Decisiones de contrato y a los
  dos generadores de ese ticket.

Ticket con los dos artefactos → `estado: generado`. Todos → `paso: 3-alinear`.

## Paso 3 — Alineación

1. Por ticket: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/trazabilidad.py {ticket} > {ticket}/revision/trazabilidad.txt`
2. Lote: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/contratos.py <carpeta de cada ticket> > {lote}/contratos.txt`
3. Si un script sale con 2 (formato), despachá un Corrector con el error (plantilla **C**)
   y volvé a correrlo. No lo arregles vos.
4. Copiá los tickets de la línea `ORDEN:` de `contratos.txt` a `estado.orden`.
5. Con dos o más tickets, despachá al Alineador (plantilla **A**). Con uno, salteá este
   punto.
6. `paso: 4-corregir`.

## Paso 4 — Corrección

1. Un Verificador por ticket, todos en el mismo mensaje (plantilla **V**).
2. Por cada artefacto con algo marcado (choques de `alineacion.md` que "Van a" él,
   hallazgos de `revision/verificacion.md`, problemas de `trazabilidad.txt` o
   `contratos.txt`): un Corrector nuevo (plantilla **C**). Nunca retomes a un generador.
3. Corré de nuevo `trazabilidad.py` y `contratos.py`.
4. Lo que siga abierto y los `DESACUERDOS` de los correctores: copialos textuales a
   `{lote}/riesgos.md`, con el ticket y la ruta de origen. **Una sola vuelta.**
5. Tickets → `estado: corregido`. `paso: 5-juicio` (o `6-implementar` sin juicio; en ese
   caso, mostrale al usuario `riesgos.md` y esperá su OK).

## Paso 5 — Juicio de valor

1. Por ticket: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fichas.py {ticket} > {lote}/fichas/T#####.md`
2. Decile al usuario, textual:
   > Para el juicio abrí otra terminal en la raíz del workspace y corré
   > `claude --agent clarabella:juez`. Pedile que juzgue `{lote}`. Cuando `dictamen.md`
   > tenga tu decisión, avisame acá.
3. Esperá. Cuando te avise, leé la línea `DECISIÓN:` de `{lote}/dictamen.md`:
   - `APROBADO` → tickets `aprobado`, `paso: 6-implementar`.
   - `RECORTADO: …` → los tickets que salen, `estado: fuera`. Si cambia lo que piden los
     que quedan, mostrale al usuario qué tickets tocan y pedile el cambio de texto para su
     `spec.md`; después volvé al paso 1 solo para esos tickets.
   - `FRENADO: …` → `paso: terminado`, Cronista por ticket con estado "frenado" (plantilla
     **CR**), y fin.
   - `PENDIENTE` → decile que el dictamen todavía no tiene decisión.

## Paso 6 — Implementación (en el orden del lote)

Un ticket por vez, en `estado.orden`, salteando los `fuera`. El siguiente arranca cuando el
anterior está `revisado`.

1. Verificá que la etapa B del ticket terminó (contenedores arriba). Si no, esperá.
2. QA (plantilla **Q**).
3. RED: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/correr_casos.py {ticket} --red > {ticket}/revision/testeo/red.txt`
   - Exit 0 → `estado: red`.
   - Exit 1 por un caso nuevo que pasa o un caso sin script → QA de nuevo con `red.txt`
     (una vez). Si sigue → pausa.
   - Un caso de regresión que falla → pausa (`regresion-preexistente`).
4. Implementador (plantilla **I**). Según su `ESTADO`:
   - `green` → `estado: green`.
   - `pausa`, `estancado`, `presupuesto` → pausa con su `MOTIVO` y
     `revision/implementacion.md`.
5. Revisión, por cada repo del ticket:
   ```bash
   wt=<worktree>
   tree=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reglas.py --snapshot --worktree $wt)
   git -C $wt diff master $tree > {ticket}/revision/diff-<ms>.patch
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reglas.py --worktree $wt --ownership dcac-context/back/database-ownership.md > {ticket}/revision/reglas-<ms>.txt
   ```
   y un Revisor por repo, en el mismo mensaje (plantilla **R**). Con bloqueantes: un
   Implementador nuevo con las revisiones (plantilla **I2**), una sola vez. Lo que quede →
   `riesgos.md`.
6. `estado: revisado`.

## Paso 7 — Cierre

1. **Integración:** `correr_casos.py` de cada ticket no `fuera`, en orden, todo a
   `{lote}/cierre.md` § Integración.
2. **Deriva:** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/contratos.py --deriva <tickets> --worktree T#####=<wt> … >> {lote}/cierre.md`
3. **Medición:** por ticket, `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hechos.py {ticket} --worktree <wt> … > {ticket}/revision/hechos.md`,
   y la sección Economía de cada uno a `cierre.md` § Medición.
4. **Crónica:** un Cronista por ticket (plantilla **CR**).
5. **Provisorias:** mostrale al usuario la ruta de cada `revision/provisorias.md`.
   Confirmadas → `spec.md`. Vetadas → pausa: el ticket vuelve al paso 4.
6. **Envío:** decile al usuario el orden del lote y que apruebe el envío. Con su
   aprobación explícita, `enviar-review` por ticket, en orden. Después `bajar-entorno`.
7. `paso: terminado`.

## Pausas

Pausás (`estado.pausa`, y le mostrás al usuario el motivo y la ruta) por: una decisión en
terreno sensible (financiero, permisos, datos); una corrección que falló dos veces; una
regresión preexistente; el entorno caído; estancamiento; presupuesto agotado; una
provisoria vetada. Con la respuesta del usuario, seguís desde donde quedó.

## Provisorias

Una duda mayor fuera de terreno sensible no frena: el Baqueano la toma con la opción más
conservadora (`PROVISORIA`), queda en `revision/provisorias.md` con lo que depende de ella,
y el usuario la confirma o la veta en el cierre. En terreno sensible, siempre pausa.

## Plantillas

Reemplazá lo que está entre `<…>`. Nada más.

**E — Escribano**
```
Agent(subagent_type: "clarabella:escribano", description: "Escribano T#####",
      prompt: "Ticket T##### (proyecto <proyecto>, tipo <tipo>, slug <slug>), carpeta <ticket>.")
```

**GP — Generador de plan**
```
Agent(subagent_type: "clarabella:generador-plan", description: "Plan T#####",
      prompt: "Ticket T##### (proyecto <proyecto>, tipo <tipo>, slug <slug>), carpeta <ticket>.
               Worktrees: <ms>=<ruta>, …. Escribí <ticket>/plan.md.")
```

**GT — Generador de tests**
```
Agent(subagent_type: "clarabella:generador-tests", description: "Tests T#####",
      prompt: "Ticket T##### (proyecto <proyecto>, tipo <tipo>, slug <slug>), carpeta <ticket>.
               Escribí <ticket>/tests.md.")
```

**B — Baqueano**
```
Agent(subagent_type: "clarabella:baqueano", description: "Baqueano <plan|tests> T#####",
      prompt: "Ticket T#####, carpeta <ticket>, en resolver-proyecto. Dudas del generador de
               <plan|tests>, textuales: <DUDAS>. Escribí <ticket>/revision/consultas-<plan|tests>.md.")
```

**A — Alineador**
```
Agent(subagent_type: "clarabella:alineador", description: "Alineador <lote>",
      prompt: "Lote <lote>, carpeta <lote>. Tickets: T##### (<ticket>), …. Escribí <lote>/alineacion.md.")
```

**V — Verificador**
```
Agent(subagent_type: "clarabella:verificador", description: "Verificador T#####",
      prompt: "Ticket T#####, carpeta <ticket>. Escribí <ticket>/revision/verificacion.md.")
```

**C — Corrector**
```
Agent(subagent_type: "clarabella:corrector", description: "Corregir <plan|tests> T#####",
      prompt: "Corregí <ticket>/<plan.md|tests.md> según: <ids y rutas de los hallazgos, o el
               error del script, textual>.")
```

**Q — QA**
```
Agent(subagent_type: "clarabella:qa", description: "QA T#####",
      prompt: "Ticket T#####, carpeta <ticket>. Contenedores T#####-<ms>, DB T#####-db.
               Escribí <ticket>/casos/. <Si es re-despacho: corregí solo los casos marcados
               en <ticket>/revision/testeo/red.txt.>")
```

**I — Implementador**
```
Agent(subagent_type: "clarabella:implementador", description: "Implementador T#####",
      prompt: "Ticket T#####, carpeta <ticket>. Repos y worktrees: <ms>=<ruta>, ….
               Presupuesto: <n> vueltas de GREEN.")
```

**I2 — Implementador (corrección post-revisión)**
```
Agent(subagent_type: "clarabella:implementador", description: "Corregir revisión T#####",
      prompt: "Ticket T#####, carpeta <ticket>. Repos y worktrees: <ms>=<ruta>, ….
               Corregí solo los bloqueantes de <ticket>/revision/revision-impl-<ms>.md.
               Presupuesto: 2 vueltas de GREEN.")
```

**R — Revisor**
```
Agent(subagent_type: "clarabella:revisor", description: "Revisión <ms> T#####",
      prompt: "Ticket T#####, carpeta <ticket>, repo <ms>. Leé solo:
               revision/diff-<ms>.patch, plan.md, revision/reglas-<ms>.txt,
               revision/notas-<ms>.md, dcac-context/back/conventions.md y el CLAUDE.md del
               repo. Escribí revision/revision-impl-<ms>.md.")
```

**CR — Cronista**
```
Agent(subagent_type: "clarabella:cronista", description: "Cronista T#####",
      prompt: "Ticket T#####, carpeta <ticket>, estado <entregado|frenado>.")
```

## Errores comunes

- **Resumirle al usuario lo que devolvió un rol** → rutas o texto textual.
- **Arreglar vos un error de formato** → Corrector.
- **Retomar a un generador para corregir** → Corrector nuevo.
- **Implementar sin la decisión del juicio** (si hay juicio) → `dictamen.md` manda.
- **Arrancar un ticket antes de que el anterior del orden esté `revisado`** → el orden es
  el de `contratos.txt`.
- **Despachar un Obrero** → los despacha el Implementador.
- **Enviar a review sin aprobación explícita** → nunca.
````

- [ ] **Step 2: Correr el test de agentes**

Run: `python3 -m unittest tests.test_agentes -v`
Expected: 4 tests OK (ya existen `resolver-proyecto` y `juzgar-proyecto`).

- [ ] **Step 3: Commit**

```bash
git add skills/resolver-proyecto
git commit -m "resolver-proyecto: procedimiento del Coordinador

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `resolver-ticket` de 8 pasos y `resumir-ticket`

**Files:**
- Modify: `skills/resolver-ticket/SKILL.md` (restaurado de `70055e7`)
- Create: `skills/resumir-ticket/SKILL.md` (restaurado de `70055e7`)
- Delete: `skills/ciclo-ticket/`

- [ ] **Step 1: Restaurar de 0.3.0 y borrar el ciclo**

```bash
git show 70055e7:skills/resolver-ticket/SKILL.md > skills/resolver-ticket/SKILL.md
mkdir -p skills/resumir-ticket
git show 70055e7:skills/resumir-ticket/SKILL.md > skills/resumir-ticket/SKILL.md
git rm -r -q skills/ciclo-ticket
```

- [ ] **Step 2: Ajustes (reemplazos exactos sobre el texto de 0.3.0)**

| Dónde | Texto de 0.3.0 | Pasa a |
|-------|----------------|--------|
| Paso 0, lista | `- **Proyecto**: una carpeta de `docs/`. Listá las existentes y preguntá cuál, o si hay que\n  crear una nueva.` | lo mismo + `\n- **Texto del ticket**: la descripción y los criterios de aceptación tal cual vienen. Se\n  guarda en `spec.md` y los criterios se numeran: `- [ ] **CA1** — <texto>`. Si no trae\n  criterios claros, preguntá.` |
| Paso 0, árbol | `├── plan.md      ← paso 2` | `├── spec.md      ← paso 0 (texto del ticket, criterios CA#)\n├── plan.md      ← paso 2` |
| Fila 2 | `Con el `tipo` del paso 0: un ticket de soporte guarda su plan en `docs/{proyecto}/soporte/…`, no en `desarrollo/`.` | lo mismo + ` Cada Parte lleva `Cubre: CA#` y el plan, su sección `## Contrato`.` |
| Fila 3 | `Sobre el plan ya escrito en el paso 2.` | `Desde `spec.md`, **sin mirar el plan**: lo que no coincida aparece al testear. Columna `Criterio` en cada caso.` |
| Fila 5 | `Corré los casos documentados en el paso 3 contra la implementación real.` | `Lo corrés en esta sesión, modo GREEN, a la vista del usuario. Si querés ver que los tests discriminan, corré el modo RED antes del paso 4.` |
| Después de la tabla | (nada) | `\nDespués del paso 8, cuando el usuario dice que cerramos: `bajar-entorno`.\n\n**Herramientas a pedido** (no son pasos; solo si el usuario las pide): `trazabilidad.py`\ndespués del paso 3, `reglas.py` antes del paso 6, `revisar-ticket` sobre el plan y los tests.\n` |
| Errores comunes, 1er ítem | `- **Confundir esto con `pipeline-desarrollo`** → esa es la corrida autónoma con subagentes,\n  modelo por fase y dashboard.` | `- **Confundir esto con `resolver-proyecto` o `pipeline-desarrollo`** → esas son las corridas\n  autónomas con subagentes.` |

Aplicarlos con un script Python que haga `assert texto.count(viejo) == 1` antes de cada reemplazo.

- [ ] **Step 3: Verificar**

Run: `grep -n 'spec.md\|Cubre\|sin mirar el plan\|modo GREEN\|bajar-entorno\|resolver-proyecto' skills/resolver-ticket/SKILL.md`
Expected: una línea por cada ajuste. `ls skills | grep -c ciclo` → `0`.

- [ ] **Step 4: Commit**

```bash
git add skills/resolver-ticket skills/resumir-ticket
git commit -m "resolver-ticket vuelve a los 8 pasos de 0.3.0; vuelve resumir-ticket; sale ciclo-ticket

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Skills hoja y referencias

**Files:**
- Modify: `skills/{preparar-repo,aislar-ticket,implementar-ticket,baqueano,escribano,bajar-entorno,planear-ticket,planear-tests-ticket,testear-ticket,cronista,revisar-ticket,clarabella}/SKILL.md`
- Test: `tests/test_referencias.py`

**Interfaces:**
- Produces: secciones "Como generador de `resolver-proyecto`" (planear-ticket, planear-tests-ticket) y "Como Obrero de `resolver-proyecto`" (implementar-ticket), que citan los agentes de Task 4.

- [ ] **Step 1: Escribir el test de referencias**

`tests/test_referencias.py`:

```python
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PROHIBIDO = ['ciclo-ticket', 'modo ciclo', 'juicio-ticket', 'ensayar-juicio', 'coordinar-lote',
             'juzgar-lote', 'fase 2 de `resolver-ticket`', 'paso 3.4']


def archivos():
    yield from (RAIZ / 'skills').glob('*/SKILL.md')
    yield from (RAIZ / 'agents').glob('*.md')
    yield RAIZ / 'README.md'


class Referencias(unittest.TestCase):
    def test_referencias_existen(self):
        skills = {p.parent.name for p in (RAIZ / 'skills').glob('*/SKILL.md')}
        agentes = {p.stem for p in (RAIZ / 'agents').glob('*.md')}
        for ruta in archivos():
            for nombre in re.findall(r'clarabella:([\w-]+)', ruta.read_text(encoding='utf-8')):
                self.assertIn(nombre, skills | agentes, f'{ruta.relative_to(RAIZ)}: clarabella:{nombre}')

    def test_nada_eliminado(self):
        for ruta in archivos():
            texto = ruta.read_text(encoding='utf-8')
            for palabra in PROHIBIDO:
                self.assertNotIn(palabra, texto, f'{ruta.relative_to(RAIZ)}: "{palabra}"')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Correr y ver qué falla**

Run: `python3 -m unittest tests.test_referencias -v 2>&1 | tail -20`
Expected: FAIL en `test_nada_eliminado` (menciones de `ciclo-ticket`, `modo ciclo`, "paso 3.4", etc.) y en `test_referencias_existen` (`clarabella:ciclo-ticket` en `clarabella/SKILL.md`). Anotar la lista: es la guía del Step 3.

- [ ] **Step 3: Ajustes**

| Skill | Viejo | Nuevo |
|-------|-------|-------|
| `preparar-repo` | `DB del ticket) no la corras acá: `resolver-ticket` la despacha a un subagente en\n  background para no frenar el planeo.` | `DB del ticket) no la corras acá: la sesión de `resolver-ticket` (o el Coordinador de\n  `resolver-proyecto`) la corre con Bash en background para no frenar el planeo.` |
| `aislar-ticket` fila B | `Un subagente en background, despachado al terminar la A, mientras el hilo principal planea` | `En background (Bash), al terminar la A, mientras se planea: la sesión de `resolver-ticket` o el Coordinador de `resolver-proyecto`` |
| `implementar-ticket` | sección `## En el ciclo` completa | `## Como Obrero de `resolver-proyecto`\n\nTe despacha el Implementador del ticket (`clarabella:obrero`), uno por microservicio.\nImplementás **solo la Parte de tu repo**, en tu worktree, y anotás los desvíos del plan en\n`revision/notas-<ms>.md`. No corrés los casos: los corre el Implementador. Si te\nre-despacha con la salida cruda de un caso que falla, corregís solo eso.\n` |
| `baqueano` | `**Solo en el modo ciclo** (`ciclo-ticket`).` | `**Solo en `resolver-proyecto`.**` |
| `baqueano` | `**Solo en el modo ciclo.**` | `**Solo en `resolver-proyecto`.**` |
| `baqueano` | `El ciclo sigue sobre ese supuesto y el usuario la confirma o la veta al final (ver `ciclo-ticket`)` | `El lote sigue sobre ese supuesto y el usuario la confirma o la veta en el cierre (ver `resolver-proyecto` § Provisorias)` |
| `baqueano` | `En el ciclo, solo si además es terreno sensible` | `En `resolver-proyecto`, solo si además es terreno sensible` |
| `escribano` | `Un subagente nuevo (`general-purpose`, `model: "sonnet"`), despachado:\n- en el paso 0 de `resolver-ticket`, con `spec.md` ya guardada;\n- en la etapa 0 de `ciclo-ticket`.` | `El tipo de agente `clarabella:escribano`, despachado en el paso 0 de `resolver-proyecto`,\nuno por ticket, con `spec.md` ya guardada. También se puede pedir standalone.` |
| `bajar-entorno` | `Es el paso 9 de `resolver-ticket`, después de `enviar-review`.` | `Va después del paso 8 de `resolver-ticket` (`enviar-review`) y en el cierre de\n`resolver-proyecto`.` |
| `planear-ticket` | `En `resolver-ticket` los tests los escribe otro agente generativo, en paralelo, desde la\nspec.` | `Los tests se escriben aparte, desde la spec (paso 3 de `resolver-ticket`, o el generador\nde tests en `resolver-proyecto`).` |
| `planear-ticket` | `## Modo orquestado (subagente de `resolver-ticket` o del motor `pipeline-desarrollo`)` | `## Modo orquestado (subagente de `resolver-proyecto` o del motor `pipeline-desarrollo`)` |
| `planear-ticket` | encabezado `## Como agente generativo de `resolver-ticket` o `ciclo-ticket`` | `## Como generador de `resolver-proyecto`` |
| `planear-tests-ticket` | `## Modo orquestado (subagente de `resolver-ticket` o del motor `pipeline-desarrollo`)` | `## Modo orquestado (subagente de `resolver-proyecto` o del motor `pipeline-desarrollo`)` |
| `planear-tests-ticket` | `(`resolver-ticket` en su fase 1, como agente generativo, o el motor en su Fase 3)` | `(el generador de tests de `resolver-proyecto`, o el motor en su Fase 3)` |
| `planear-tests-ticket` | encabezado `## Como agente generativo de `resolver-ticket` o `ciclo-ticket`` | `## Como generador de `resolver-proyecto`` |
| `cronista` | `Reemplaza a resumir-ticket.` | `En `resolver-proyecto`; en el flujo manual (`resolver-ticket`) el resumen lo hace `resumir-ticket`.` |
| `cronista` | `(ver `resolver-ticket` § Fase 4)` | `(ver `resolver-proyecto` § Paso 7)` |
| `cronista` | `- en la fase 4 de `resolver-ticket`, antes de `enviar-review`;` | `- en el cierre de `resolver-proyecto` (paso 7), antes de `enviar-review`;` |
| `cronista` | `Un subagente **nuevo** (`general-purpose`, `model: "sonnet"`), que no participó del ticket:` | `El tipo de agente `clarabella:cronista` (sonnet), que no participó del ticket:` |
| `clarabella` | fila `ciclo-ticket` | `\| Que Clarabella resuelva sola uno o más tickets, "resolvé estos tickets", "resolvelo solo" \| `clarabella:resolver-proyecto` (se arranca con `claude --agent clarabella:coordinador`) \|` |
| `clarabella` | (nueva fila) | `\| Juzgar si la solución de un lote sirve, "¿vale la pena?" \| `clarabella:juzgar-proyecto` (sesión aparte: `claude --agent clarabella:juez`) \|` |
| `clarabella` | (nueva fila) | `\| Resumir un ticket resuelto a mano, "resumí T#####" \| `clarabella:resumir-ticket` \|` |

Más tres secciones de texto nuevo:

1. `planear-ticket`, dentro de "Como generador de `resolver-proyecto`", agregar un punto 5:

```markdown
5. **`## Contrato`**, al final del plan, siempre:

       ## Contrato
       ### Expone
       - `POST /internal/permisos/usuarios` — body `{usuarioId, sujetoId}` → 201 `{id}`
       ### Consume
       - `GET /compliance/:id/permisos-psp` — de T23821
       - `POST /internal/cuentas/:id/usuarios/sync-compliance` — existente

   Cada endpoint entre backticks como `VERBO /ruta`. Un Consume dice de qué ticket del lote
   sale (`de T#####`) o que ya existe (`existente`). Si no expone o no consume nada, la
   subsección lleva `- (nada)`. Lo lee `contratos.py`.
```

   Y en el cuerpo general de la skill (plantilla del plan), agregar `## Contrato` con el mismo formato antes de `## Verificación`, con la nota: "En `resolver-ticket` es opcional; en `resolver-proyecto`, obligatoria."

2. `testear-ticket`, reemplazar la sección `## Quién la ejecuta: un contexto que no escribió el código` completa por:

```markdown
## Quién la ejecuta

- En `resolver-ticket` (manual) la corre la **sesión principal**, a la vista del usuario:
  él es el contexto independiente que mira los resultados.
- En el motor `pipeline-desarrollo`, un **subagente nuevo** por corrida, con un prompt que
  dice "modo orquestado".
- En `resolver-proyecto` no se usa: los casos son scripts (`correr_casos.py`).

En cualquier caso: tus fuentes son `tests.md`, el código en los worktrees, los contenedores
y la DB. **No modificás código ni `tests.md`.** Ejecutás, verificás y clasificás.
```

3. `revisar-ticket`: en `description`, `Es la fase 2 (Revisión) de resolver-ticket, el paso 3.4 y la revisión de cada vuelta de ciclo-ticket.` → `El modo implementación es el paso 6 de resolver-proyecto; el modo plan-tests se usa a pedido.`; `## Modo plan-tests (fase 2 de `resolver-ticket`)` → `## Modo plan-tests (a pedido)`; `## Modo implementación (paso 3.4 de `resolver-ticket`, vueltas de `ciclo-ticket`)` → `## Modo implementación (paso 6 de `resolver-proyecto`)`; y cada "en el ciclo"/"del ciclo" que quede → "en `resolver-proyecto`".

Lo que `test_referencias` siga marcando después de la tabla se corrige con el mismo criterio: `ciclo-ticket` → `resolver-proyecto`, menciones de fases de la 0.5.0 de `resolver-ticket` → el paso equivalente de los 8 o de `resolver-proyecto`. Cada caso fuera de la tabla va al ledger como Ruling.

- [ ] **Step 4: Correr**

Run: `python3 -m unittest tests.test_referencias -v`
Expected: 2 tests OK.

- [ ] **Step 5: Commit**

```bash
git add skills tests/test_referencias.py
git commit -m "Skills hoja: Contrato, Obrero, testear en sesión principal, sin ciclo-ticket

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: README, versión y verificación final

**Files:**
- Modify: `README.md`, `.claude-plugin/plugin.json`

- [ ] **Step 1: README**

1. Después de "## Hablarle a Clarabella", sección nueva:

```markdown
## Dos modos

| Modo | Cómo | Para qué |
|------|------|----------|
| **Manual** | "Clarabella, ayudame con T#####" → `resolver-ticket` | Un ticket, vos con el control: 8 pasos en la sesión, sin subagentes |
| **Autónomo** | `claude --agent clarabella:coordinador` → `resolver-proyecto` | Uno o más tickets relacionados: generadores, alineación, juicio antes de implementar, Implementador con Obreros, casos como scripts |

El juicio de un proyecto corre en una sesión aparte: `claude --agent clarabella:juez`.
```

2. Tabla de skills: `resolver-ticket` → "Los 8 pasos manuales (0.3.0), sin subagentes"; sacar `ciclo-ticket`; agregar `resolver-proyecto`, `juzgar-proyecto`, `resumir-ticket` ("Resumen de cierre del flujo manual").
3. Tabla de scripts: agregar `contratos.py <tickets>` ("Cruza Expone/Consume entre tickets, orden del lote; `--deriva`"), `fichas.py <ticket>` ("Ficha para el juicio"), `correr_casos.py <ticket> [--red]` ("RED y GREEN sin tokens").
4. Sección nueva `## Roles de resolver-proyecto`: la tabla de roles del spec (rol, modelo · esfuerzo, qué hace), y la línea "Quién despacha: el Coordinador a todos; el Implementador a sus Obreros, Correctores y QA".
5. Reemplazar las secciones "Flujo de `resolver-ticket`", "Modo ciclo" y "Modelos por rol" por: el flujo de 8 pasos (lista numerada con la skill de cada paso) y el flujo de `resolver-proyecto` (pasos 0 a 7, una línea cada uno).

- [ ] **Step 2: Versión**

`.claude-plugin/plugin.json`: `"version": "0.5.0"` → `"version": "0.6.0"`; `description` → `"Una vaca a la que le mandás a resolver tickets (desarrollo y soporte): a mano, paso a paso, o sola, con un equipo de agentes que planea, alinea, se hace juzgar, implementa y testea."`

- [ ] **Step 3: Verificación final**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: OK, 63 tests (34 + 12 + 3 + 8 + 4 + 2).

Run: `python3 -m json.tool .claude-plugin/plugin.json > /dev/null && echo ok`
Expected: `ok`.

Run: `claude plugin validate . 2>&1 | tail -20`
Expected: sin errores. Si un agente no parsea o el formato de `tools`/`skills` no se acepta, corregir el frontmatter, ajustar `tests/test_agentes.py` al formato aceptado y anotar el Ruling.

- [ ] **Step 4: Commit**

```bash
git add README.md .claude-plugin/plugin.json
git commit -m "Clarabella 0.6.0: resolver-ticket manual y resolver-proyecto

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Prueba con Marcos (fuera del plan)**

1. `resolver-ticket`: un ticket chico de punta a punta, verificando que ningún paso despache subagentes y que el paso 7 use `resumir-ticket`.
2. `resolver-proyecto`: un lote de 2-3 tickets con una dependencia, con `claude --agent clarabella:coordinador --plugin-dir /home/marcos/projects/clarabella`, y comparar `cierre.md` contra T23815.
