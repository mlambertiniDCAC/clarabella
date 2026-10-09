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

    def test_caso_justificado_por_una_decision(self):
        spec = SPEC.replace('- CA9 se menciona acá pero no es un criterio.',
                            '- **E1 · Formato de ids:** string.')
        tests = TESTS.replace('| T03 | regresión |', '| T03 | E1 |')
        rc, out = correr(spec=spec, tests=tests)
        self.assertEqual(rc, 0, out)

    def test_decision_citada_que_no_existe(self):
        tests = TESTS.replace('| T03 | regresión |', '| T03 | E4 |')
        rc, out = correr(tests=tests)
        self.assertEqual(rc, 1)
        self.assertIn('Decisiones citadas que no existen en spec.md: E4 (tests.md · T03)', out)

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
