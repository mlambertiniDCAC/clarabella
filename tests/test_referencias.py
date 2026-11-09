import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PROHIBIDO = ['ciclo-ticket', 'modo ciclo', 'juicio-ticket', 'ensayar-juicio', 'coordinar-lote',
             'juzgar-lote', 'fase 2 de `resolver-ticket`', 'paso 3.4',
             'docs/{proyecto}', 'docs/<proyecto>', 'docs/_pipeline', 'carpeta de `docs/`']

ESCRIBEN = ['planear-ticket', 'planear-tests-ticket', 'implementar-ticket', 'testear-ticket',
            'revisar-ticket', 'resumir-ticket', 'cronista', 'resolver-proyecto']


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
                self.assertFalse(palabra in texto, f'{ruta.relative_to(RAIZ)}: "{palabra}"')


class RaizDelCerebro(unittest.TestCase):
    def test_las_skills_que_escriben_resuelven_la_raiz_y_frenan_sin_cerebro(self):
        for nombre in ESCRIBEN:
            texto = (RAIZ / 'skills' / nombre / 'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('CEREBRO_RAIZ', texto, nombre)
            self.assertIn('fren', texto.lower(), nombre)

    def test_las_skills_que_escriben_piden_la_carpeta_al_cerebro(self):
        for nombre in ESCRIBEN:
            texto = (RAIZ / 'skills' / nombre / 'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('cerebro ubicar', texto, nombre)


if __name__ == '__main__':
    unittest.main()
