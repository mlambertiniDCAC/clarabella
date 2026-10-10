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
