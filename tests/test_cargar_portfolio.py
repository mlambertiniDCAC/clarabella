import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SKILL = RAIZ / 'skills' / 'cargar-portfolio' / 'SKILL.md'


def frontmatter(ruta):
    texto = ruta.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n(.+)', texto, re.S)
    assert m, f'{ruta.name}: sin frontmatter o sin cuerpo'
    campos = {}
    for linea in m.group(1).splitlines():
        clave, _, valor = linea.partition(':')
        campos[clave.strip()] = valor.strip()
    return campos


class CargarPortfolio(unittest.TestCase):
    def test_tiene_frontmatter_con_name_y_description(self):
        fm = frontmatter(SKILL)
        self.assertEqual(fm['name'], 'cargar-portfolio')
        self.assertIn('cargar', fm['description'].lower())

    def test_declara_las_cuatro_clases_de_la_spec(self):
        texto = SKILL.read_text(encoding='utf-8').lower()
        for clase in ('info', 'estado', 'relaci', 'cambio dr'):
            self.assertIn(clase, texto)

    def test_manda_a_la_bandeja_lo_ambiguo_y_lo_desconocido(self):
        texto = SKILL.read_text(encoding='utf-8')
        self.assertIn('ambigua', texto)
        self.assertIn('desconocida', texto)
        self.assertIn('bandeja-encolar', texto)

    def test_prohibe_archivar_dato_financiero_sensible(self):
        texto = SKILL.read_text(encoding='utf-8')
        self.assertIn('CBU', texto)
        self.assertIn('CVU', texto)

    def test_no_instruye_pedir_confirmacion_de_lo_resuelto(self):
        self.assertNotIn('confirmá cada', SKILL.read_text(encoding='utf-8').lower())


if __name__ == '__main__':
    unittest.main()
