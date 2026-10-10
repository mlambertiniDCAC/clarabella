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
