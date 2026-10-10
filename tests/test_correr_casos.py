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
