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
SESION_PRINCIPAL = {'coordinador', 'juez'}


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


    def test_sesion_principal_invoca_su_skill(self):
        # Con `claude --agent`, el campo skills no se precarga (verificado con Claude Code
        # 2.1.296): el cuerpo tiene que mandar a invocarla con la herramienta Skill.
        for nombre in SESION_PRINCIPAL:
            ruta = AGENTES / f'{nombre}.md'
            skill = lista(frontmatter(ruta)['skills'])[0]
            cuerpo = ruta.read_text(encoding='utf-8').split('---', 2)[2]
            self.assertIn(f'invocá la skill `{skill}` con la herramienta Skill', cuerpo, nombre)

if __name__ == '__main__':
    unittest.main()
