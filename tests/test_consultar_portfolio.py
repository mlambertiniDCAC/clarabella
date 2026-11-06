import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SKILL = RAIZ / 'skills' / 'consultar-portfolio' / 'SKILL.md'
PLANEAR = RAIZ / 'skills' / 'planear-ticket' / 'SKILL.md'


def frontmatter(ruta):
    texto = ruta.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n(.+)', texto, re.S)
    assert m, f'{ruta.name}: sin frontmatter o sin cuerpo'
    campos = {}
    for linea in m.group(1).splitlines():
        clave, _, valor = linea.partition(':')
        campos[clave.strip()] = valor.strip()
    return campos


class ConsultarPortfolio(unittest.TestCase):
    def test_tiene_frontmatter_valido(self):
        self.assertEqual(frontmatter(SKILL)['name'], 'consultar-portfolio')

    def test_no_bloquea_si_no_existe_el_repo_del_cerebro(self):
        texto = SKILL.read_text(encoding='utf-8').lower()
        self.assertTrue('no es un error' in texto or 'no bloqueante' in texto)

    def test_aclara_que_no_reemplaza_dcac_context(self):
        self.assertIn('dcac-context', SKILL.read_text(encoding='utf-8'))

    def test_planear_ticket_consulta_el_cerebro_antes_de_dcac_context(self):
        texto = PLANEAR.read_text(encoding='utf-8')
        self.assertLess(texto.index('consultar-portfolio'), texto.index('dcac-context/`'))

    def test_planear_ticket_sigue_teniendo_sus_tres_fases(self):
        texto = PLANEAR.read_text(encoding='utf-8')
        self.assertIn('entender → planificar → documentar', texto)


if __name__ == '__main__':
    unittest.main()
