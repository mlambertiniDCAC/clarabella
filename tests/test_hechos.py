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
| 5 | Agente del plan (retomado) | opus | ronda 2 | 35 s · 265k acumulados · 7 tools |
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
        self.assertIn('| Escribano | sonnet | 1 | 248 | 102000 | 0 | 0 |', out)
        self.assertIn('| Agente del plan | opus | 1 | 600 | 1500000 | 0 | 0 |', out)
        self.assertIn('| GREEN | sonnet | 2 | 300 | 80000 | 0 | 1 |', out)
        self.assertIn('| Agente del plan (retomado) | opus | 1 | 35 | 0 | 265000 | 0 |', out)
        self.assertIn('**Total:** 5 subagentes · 1183 s · 1682000 tokens · 265000 de contexto retomado · '
                      '1 sin registro', out)

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
