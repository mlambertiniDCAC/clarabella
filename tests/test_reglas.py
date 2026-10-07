import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'reglas.py'

OWNERSHIP = """# Ownership de tablas

## Tablas por servicio

### ms-faena
- `dcac.negocios` — Tabla central de lotes (compartida con ms-invernada)
- `dcac.cobros_faena` — Cobros, discriminados por el campo `dinamica`

### ms-invernada
- `dcac.negocios` — Compartida con ms-faena
- `dcac.invernadas` — Propia

### ms-compra_inmediata
- `negocios.compra_inmediata_faena` — CI de faena
"""

SERVICIO_CON_ESTADO = """<?php
class Servicio
{
    private array $cache = [];

    public function __construct(private Repo $repo)
    {
        $this->cache = [];
    }

    public function buscar(int $id)
    {
        $this->cache[$id] = $this->repo->find($id);
        return $this->cache[$id];
    }
}
"""

MODELO = """<?php
class Lote extends Model
{
    public function cerrar()
    {
        $this->estado = 'cerrado';
    }
}
"""


class Reglas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ownership = Path(self.tmp.name, 'ownership.md')
        self.ownership.write_text(OWNERSHIP, encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, wt, *args):
        return subprocess.run(['git', '-C', str(wt), *args], check=True,
                              capture_output=True, text=True).stdout

    def repo(self, nombre):
        wt = Path(self.tmp.name, nombre)
        wt.mkdir()
        self.git(wt, 'init', '-q', '-b', 'master')
        self.git(wt, 'config', 'user.email', 't@t')
        self.git(wt, 'config', 'user.name', 't')
        (wt / 'README.md').write_text('base\n')
        self.git(wt, 'add', '-A')
        self.git(wt, 'commit', '-q', '-m', 'base')
        return wt

    def escribir(self, wt, ruta, texto):
        archivo = wt / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding='utf-8')

    def correr(self, wt, *extra):
        r = subprocess.run([sys.executable, str(SCRIPT), '--worktree', str(wt),
                            '--ownership', str(self.ownership), *extra],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_sin_cambios_es_ok(self):
        wt = self.repo('ms-faena')
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)
        self.assertIn('OK: sin alertas en ms-faena (base master)', out)

    def test_tabla_ajena_en_archivo_nuevo_sin_trackear(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Repo.php', "<?php\n$r = Db::table('dcac.invernadas')->get();\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 1, out)
        self.assertIn('app/Repo.php:2 · tabla-ajena · invernadas es de ms-invernada', out)

    def test_no_toca_el_index(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Repo.php', "<?php\n$r = Db::table('dcac.invernadas')->get();\n")
        self.correr(wt)
        self.assertIn('?? app/', self.git(wt, 'status', '--porcelain'))

    def test_tabla_compartida_no_alerta(self):
        wt = self.repo('ms-invernada')
        self.escribir(wt, 'app/Repo.php', "<?php\n$sql = 'SELECT * FROM dcac.negocios WHERE id = ?';\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)

    def test_tabla_sin_esquema_se_detecta(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Model/Ci.php',
                      "<?php\nclass Ci extends Model\n{\n    protected ?string $table = 'compra_inmediata_faena';\n}\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 1, out)
        self.assertIn('tabla-ajena · compra_inmediata_faena es de ms-compra_inmediata', out)

    def test_estado_en_clase_fuera_del_constructor(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Service/Servicio.php', SERVICIO_CON_ESTADO)
        rc, out = self.correr(wt)
        self.assertEqual(rc, 1, out)
        self.assertIn('app/Service/Servicio.php:13 · estado-en-clase', out)
        self.assertNotIn('Servicio.php:8 ', out)

    def test_modelo_no_alerta_estado(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Model/Lote.php', MODELO)
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)

    def test_llamada_entre_ms(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Client.php', "<?php\n$host = env('INVERNADA_SERVICE_HOST');\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 1, out)
        self.assertIn('app/Client.php:2 · llamada-entre-ms', out)

    def test_el_gateway_puede_llamar_a_los_ms(self):
        wt = self.repo('apigateway')
        self.escribir(wt, 'app/Client.php', "<?php\n$host = env('INVERNADA_SERVICE_HOST');\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)

    def test_comentarios_no_alertan(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/S.php', "<?php\n// update invernadas cuando cierre\n# INVERNADA_SERVICE_HOST\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)

    def test_hosts_de_infraestructura_no_alertan(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, '.env.example', "GRAYLOG_SERVICE_HOST=\nREDIS_SERVICE_HOST=\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)

    def test_carpeta_models_no_alerta_estado(self):
        wt = self.repo('apigateway')
        self.escribir(wt, 'app/Models/Stats.php',
                      "<?php\nclass Stats\n{\n    public function marcar($r)\n    {\n        $this->route = $r;\n    }\n}\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)

    def test_fixtures_de_tests_no_alertan_tablas(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'test/Fixture/InvernadaFixture.php', "<?php\npublic $table = 'invernadas';\n")
        self.escribir(wt, 'src/repo.spec.ts', "const sql = 'SELECT * FROM dcac.invernadas';\n")
        rc, out = self.correr(wt)
        self.assertEqual(rc, 0, out)

    def test_snapshot_y_base_para_el_delta(self):
        wt = self.repo('ms-faena')
        self.escribir(wt, 'app/Repo.php', "<?php\n$r = Db::table('dcac.invernadas')->get();\n")
        r = subprocess.run([sys.executable, str(SCRIPT), '--snapshot', '--worktree', str(wt)],
                           capture_output=True, text=True, check=True)
        tree = r.stdout.strip()
        self.assertRegex(tree, r'^[0-9a-f]{40}$')
        rc, out = self.correr(wt, '--base', tree)
        self.assertEqual(rc, 0, out)


if __name__ == '__main__':
    unittest.main()
