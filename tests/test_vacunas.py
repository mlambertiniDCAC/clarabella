import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'scripts'))

import vacunas


def repo(tmp, nombre, dockerfiles, package=None, nvmrc=None, lock=True):
    d = Path(tmp) / nombre
    d.mkdir(parents=True)
    if lock:
        (d / 'package-lock.json').write_text('{"lockfileVersion": 3}', encoding='utf-8')
    for archivo, contenido in dockerfiles.items():
        (d / archivo).write_text(contenido, encoding='utf-8')
    if package is not None:
        (d / 'package.json').write_text(json.dumps(package), encoding='utf-8')
    if nvmrc is not None:
        (d / '.nvmrc').write_text(nvmrc, encoding='utf-8')
    return d


class TagNode(unittest.TestCase):
    def test_multistage_toma_el_primer_from(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine AS build\nRUN npm ci\nFROM node:22-alpine\n'})
            self.assertEqual(vacunas.tag_node(d), ('22-alpine', 'Dockerfile.test'))

    def test_test_tiene_prioridad_sobre_prod(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-permisos', {
                'Dockerfile.prod': 'FROM node:18-alpine AS build\n',
                'Dockerfile.test': 'FROM node:20 AS build\n',
            })
            self.assertEqual(vacunas.tag_node(d), ('20', 'Dockerfile.test'))

    def test_front_solo_con_dockerfile_prod(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'onboarding-psp', {'Dockerfile.prod': 'FROM node:20 AS builder\nFROM nginx:alpine AS production\n'})
            self.assertEqual(vacunas.tag_node(d), ('20', 'Dockerfile.prod'))

    def test_sin_from_node(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'api-testing-end2end', {'Dockerfile': 'FROM cypress/base:16\n'})
            self.assertEqual(vacunas.tag_node(d), (None, None))

    def test_pineado_por_digest_no_da_tag(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-x', {'Dockerfile': 'FROM node@sha256:abc123 AS build\n'})
            self.assertEqual(vacunas.tag_node(d), (None, None))


class DetectarRepos(unittest.TestCase):
    def test_detecta_solo_los_node_con_package_json(self):
        with TemporaryDirectory() as tmp:
            repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={'name': 'ms-psp'})
            repo(tmp, 'ms-faena', {'Dockerfile': 'FROM php:8.1-fpm\n'}, package=None)
            repo(tmp, 'web-cliente-react', {'Dockerfile.prod': 'FROM node:20 AS build\n'}, package={'name': 'web'})
            repo(tmp, 'sin-package', {'Dockerfile': 'FROM node:20\n'}, package=None)
            self.assertEqual(vacunas.detectar_repos(Path(tmp)), ['ms-psp', 'web-cliente-react'])


class NotasVersion(unittest.TestCase):
    def test_engines_coincide_no_genera_nota(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'},
                     package={'engines': {'node': '>= 22 <23'}})
            self.assertEqual(vacunas.notas_version(d, '22-alpine'), [])

    def test_engines_en_conflicto_genera_nota(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-x', {'Dockerfile': 'FROM node:20-alpine\n'},
                     package={'engines': {'node': '>= 22 <23'}})
            notas = vacunas.notas_version(d, '20-alpine')
            self.assertEqual(len(notas), 1)
            self.assertIn('engines.node', notas[0])
            self.assertIn('20-alpine', notas[0])

    def test_nvmrc_en_conflicto_genera_nota(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-x', {'Dockerfile': 'FROM node:22-alpine\n'}, package={}, nvmrc='18.19.1\n')
            notas = vacunas.notas_version(d, '22-alpine')
            self.assertEqual(len(notas), 1)
            self.assertIn('.nvmrc', notas[0])

    def test_package_json_ilegible_no_explota(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp) / 'ms-roto'
            d.mkdir()
            (d / 'Dockerfile').write_text('FROM node:22-alpine\n', encoding='utf-8')
            (d / 'package.json').write_text('{roto', encoding='utf-8')
            self.assertEqual(vacunas.notas_version(d, '22-alpine'), [])


AUDIT_OK = {
    'auditReportVersion': 2,
    'vulnerabilities': {
        'braces': {
            'name': 'braces', 'severity': 'high', 'isDirect': False,
            'via': [{'source': 1098094, 'name': 'braces',
                     'url': 'https://github.com/advisories/GHSA-grv7-fg5c-xmjg',
                     'severity': 'high', 'range': '<3.0.3'}],
            'effects': ['tsc-alias'], 'range': '<3.0.3',
            'fixAvailable': {'name': 'tsc-alias', 'version': '1.8.10', 'isSemVerMajor': False},
        },
        'tsc-alias': {
            'name': 'tsc-alias', 'severity': 'high', 'isDirect': True,
            'via': ['braces'], 'effects': [], 'range': '<=1.8.9',
            'fixAvailable': {'name': 'tsc-alias', 'version': '2.0.0', 'isSemVerMajor': True},
        },
        'js-yaml': {
            'name': 'js-yaml', 'severity': 'moderate', 'isDirect': False,
            'via': [{'source': 1, 'name': 'js-yaml',
                     'url': 'https://github.com/advisories/GHSA-8j8c-7jfh-h6hx',
                     'severity': 'moderate', 'range': '<3.13.1'}],
            'effects': [], 'range': '<3.13.1', 'fixAvailable': False,
        },
    },
    'metadata': {'vulnerabilities': {'info': 0, 'low': 1, 'moderate': 1, 'high': 2,
                                     'critical': 0, 'total': 4}},
}

TRIVY_VULN = {
    'Results': [
        {'Target': 'package-lock.json', 'Vulnerabilities': [
            {'VulnerabilityID': 'CVE-2024-4068', 'PkgName': 'braces', 'Severity': 'HIGH',
             'InstalledVersion': '3.0.2', 'FixedVersion': '3.0.3'},
            {'VulnerabilityID': 'CVE-2024-0001', 'PkgName': 'lodash', 'Severity': 'LOW',
             'InstalledVersion': '4.17.20', 'FixedVersion': '4.17.21'},
        ]},
        {'Target': 'otro', 'Vulnerabilities': None},
    ]
}

TRIVY_SECRET = {
    'Results': [
        {'Target': 'src/config.ts', 'Class': 'secret', 'Secrets': [
            {'RuleID': 'generic-api-key', 'Category': 'general', 'Severity': 'HIGH',
             'Title': 'Generic API Key AKIAIOSFODNN7EXAMPLE', 'StartLine': 14, 'EndLine': 14,
             'Match': 'const key = "AKIAIOSFODNN7EXAMPLE"',
             'Code': {'Lines': [{'Number': 14, 'Content': 'AKIAIOSFODNN7EXAMPLE'}]}},
        ]},
        {'Target': 'src/otro.ts', 'Class': 'secret', 'Secrets': None},
    ]
}


class NormalizarNpm(unittest.TestCase):
    def test_conteos_y_hallazgos(self):
        r = vacunas.normalizar_npm(AUDIT_OK)
        self.assertEqual((r['critical'], r['high'], r['moderate'], r['low']), (0, 2, 1, 1))
        self.assertEqual([h['paquete'] for h in r['hallazgos']], ['braces', 'tsc-alias', 'js-yaml'])
        self.assertNotIn('error', r)

    def test_campos_del_hallazgo(self):
        h = vacunas.normalizar_npm(AUDIT_OK)['hallazgos'][0]
        self.assertEqual(h, {'paquete': 'braces', 'severidad': 'high',
                             'advisory': 'GHSA-grv7-fg5c-xmjg', 'via': ['tsc-alias'],
                             'fix_disponible': True, 'fix_breaking': False})

    def test_fix_breaking_y_sin_fix(self):
        hallazgos = {h['paquete']: h for h in vacunas.normalizar_npm(AUDIT_OK)['hallazgos']}
        self.assertTrue(hallazgos['tsc-alias']['fix_breaking'])
        self.assertFalse(hallazgos['js-yaml']['fix_disponible'])
        self.assertIsNone(hallazgos['tsc-alias']['advisory'])

    def test_reporte_con_error_no_explota(self):
        r = vacunas.normalizar_npm({'error': {'code': 'ENOLOCK', 'summary': 'no lockfile'}})
        self.assertEqual((r['critical'], r['high'], r['moderate'], r['low']), (0, 0, 0, 0))
        self.assertEqual(r['hallazgos'], [])
        self.assertIn('ENOLOCK', r['error'])

    def test_json_vacio_no_explota(self):
        r = vacunas.normalizar_npm({})
        self.assertEqual(r['hallazgos'], [])
        self.assertEqual(r['high'], 0)


class NormalizarTrivy(unittest.TestCase):
    def test_conteos_y_solo_altos_en_hallazgos(self):
        r = vacunas.normalizar_trivy_vuln(TRIVY_VULN)
        self.assertEqual((r['critical'], r['high'], r['medium'], r['low']), (0, 1, 0, 1))
        self.assertEqual([h['id'] for h in r['hallazgos']], ['CVE-2024-4068'])

    def test_vulnerabilities_null_no_explota(self):
        self.assertEqual(vacunas.normalizar_trivy_vuln({'Results': [{'Target': 'x', 'Vulnerabilities': None}]}),
                         {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'hallazgos': []})

    def test_sin_results_no_explota(self):
        self.assertEqual(vacunas.normalizar_trivy_vuln({})['hallazgos'], [])

    def test_campos_del_hallazgo(self):
        h = vacunas.normalizar_trivy_vuln(TRIVY_VULN)['hallazgos'][0]
        self.assertEqual(h, {'id': 'CVE-2024-4068', 'paquete': 'braces', 'instalada': '3.0.2',
                             'fixada': '3.0.3', 'severidad': 'HIGH'})


class NormalizarSecretos(unittest.TestCase):
    def test_archivo_linea_y_tipo(self):
        self.assertEqual(vacunas.normalizar_secretos(TRIVY_SECRET),
                         [{'archivo': 'src/config.ts', 'linea': 14, 'tipo': 'generic-api-key'}])

    def test_el_valor_del_secreto_no_sale_en_ningun_campo(self):
        salida = json.dumps(vacunas.normalizar_secretos(TRIVY_SECRET))
        self.assertNotIn('AKIAIOSFODNN7EXAMPLE', salida)
        self.assertNotIn('Match', salida)

    def test_secrets_null_no_explota(self):
        self.assertEqual(vacunas.normalizar_secretos({'Results': [{'Target': 'x', 'Secrets': None}]}), [])


class Comandos(unittest.TestCase):
    def test_audit_monta_read_only_y_usa_el_tag(self):
        cmd = vacunas.cmd_audit('/w/ms-psp', '22-alpine')
        self.assertEqual(cmd, ['docker', 'run', '--rm', '-v', '/w/ms-psp:/app:ro', '-w', '/app',
                               '-e', 'HOME=/tmp', '-e', 'npm_config_cache=/tmp/.npm',
                               'node:22-alpine', 'npm', 'audit', '--json'])

    def test_trivy_fs_usa_el_cache_y_salta_node_modules(self):
        cmd = vacunas.cmd_trivy_fs('/w/ms-psp')
        self.assertIn('-v', cmd)
        self.assertIn(f'{vacunas.CACHE_TRIVY}:/root/.cache/trivy', cmd)
        self.assertIn('/w/ms-psp:/src:ro', cmd)
        self.assertIn(vacunas.TRIVY, cmd)
        self.assertEqual(cmd[-8:], ['fs', '--scanners', 'vuln', '--skip-dirs', 'node_modules',
                                    '--format', 'json', '/src'])

    def test_trivy_image_no_monta_el_repo(self):
        cmd = vacunas.cmd_trivy_image('22-alpine')
        self.assertNotIn('/src:ro', ' '.join(cmd))
        self.assertEqual(cmd[-4:], ['image', '--format', 'json', 'node:22-alpine'])

    def test_trivy_secret_pide_el_scanner_secret(self):
        cmd = vacunas.cmd_trivy_secret('/w/ms-psp')
        self.assertIn('secret', cmd)
        self.assertEqual(cmd[-1], '/src')

    def test_fix_sin_force_con_package_lock_only_y_user(self):
        cmd = vacunas.cmd_audit_fix('/w/ms-psp', '22-alpine', 1000, 1000)
        self.assertNotIn('--force', cmd)
        self.assertIn('--package-lock-only', cmd)
        self.assertIn('--user', cmd)
        self.assertIn('1000:1000', cmd)
        self.assertIn('/w/ms-psp:/app', cmd)
        self.assertNotIn('/w/ms-psp:/app:ro', cmd)

    def test_validar_copia_adentro_y_usa_el_comando_del_prediff(self):
        cmd = vacunas.cmd_validar('/w/ms-psp', '22-alpine')
        self.assertIn('/w/ms-psp:/src:ro', cmd)
        guion = cmd[-1]
        self.assertIn('cp -a /src/. .', guion)
        self.assertIn('npm ci', guion)
        self.assertIn('npm run build', guion)
        self.assertIn('--maxWorkers=2', guion)
        self.assertIn('--workerIdleMemoryLimit=512MB', guion)

    def test_rutas_con_espacios_no_se_parten(self):
        cmd = vacunas.cmd_audit('/w/ms psp', '20')
        self.assertIn('/w/ms psp:/app:ro', cmd)
        self.assertEqual(len([a for a in cmd if 'ms psp' in a]), 1)

    def test_imagen_de_trivy_sobreescribible_y_nunca_latest(self):
        self.assertNotIn('latest', vacunas.TRIVY)
        self.assertIn('aquasec/trivy:9.9.9', vacunas.cmd_trivy_fs('/w/x', 'aquasec/trivy:9.9.9'))


class Escanear(unittest.TestCase):
    def _ejecutar(self, respuestas):
        llamadas = []

        def ejecutar(cmd):
            llamadas.append(cmd)
            for clave in ('audit', 'secret', 'image', 'fs'):
                if clave in cmd:
                    return respuestas.get(clave, (0, '{}', ''))
            return 0, '{}', ''

        return ejecutar, llamadas

    def test_arma_el_json_de_la_spec(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'bridge-node', {'Dockerfile.test': 'FROM node:22-alpine\n'},
                     package={'name': 'bridge-node'})
            ejecutar, llamadas = self._ejecutar({
                'audit': (1, json.dumps(AUDIT_OK), 'npm warn audit'),
                'fs': (0, json.dumps(TRIVY_VULN), 'INFO Vulnerability scanning is enabled'),
                'image': (0, json.dumps({'Results': []}), 'INFO Detected OS: alpine'),
                'secret': (0, json.dumps(TRIVY_SECRET), 'INFO Secret scanning is enabled'),
            })
            r = vacunas.escanear(str(d), 'bridge-node', 'master', ejecutar)
            self.assertEqual(r['repo'], 'bridge-node')
            self.assertEqual(r['node_tag'], '22-alpine')
            self.assertEqual(r['node_tag_origen'], 'Dockerfile.test')
            self.assertEqual(r['base'], 'master')
            self.assertEqual(r['npm']['high'], 2)
            self.assertEqual(r['imagen_base']['tag'], 'node:22-alpine')
            self.assertEqual(r['secretos'][0]['tipo'], 'generic-api-key')
            self.assertEqual(r['notas'], [])
            self.assertEqual(len(llamadas), 4)

    def test_sin_tag_de_node_no_corre_nada(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'api-testing-end2end', {'Dockerfile': 'FROM cypress/base:16\n'},
                     package={'name': 'e2e'})
            ejecutar, llamadas = self._ejecutar({})
            r = vacunas.escanear(str(d), 'api-testing-end2end', 'master', ejecutar)
            self.assertIsNone(r['node_tag'])
            self.assertIn('FROM node:', r['error'])
            self.assertEqual(llamadas, [])

    def test_trivy_que_falla_queda_como_error_no_como_vacio(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            ejecutar, _ = self._ejecutar({
                'audit': (0, json.dumps(AUDIT_OK), ''),
                'fs': (1, '', 'FATAL failed to download vulnerability DB'),
                'image': (1, '', 'FATAL failed to download vulnerability DB'),
                'secret': (1, '', 'FATAL failed to download vulnerability DB'),
            })
            r = vacunas.escanear(str(d), 'ms-psp', 'master', ejecutar)
            self.assertIn('error', r['trivy_lock'])
            self.assertIn('error', r['imagen_base'])
            self.assertIn('DB', r['trivy_lock']['error'])

    def test_salida_no_parseable_queda_como_error(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            ejecutar, _ = self._ejecutar({'audit': (1, '', 'npm ERR! code ENOLOCK')})
            r = vacunas.escanear(str(d), 'ms-psp', 'master', ejecutar)
            self.assertIn('error', r['npm'])
            self.assertIn('ENOLOCK', r['npm']['error'])


class ComandosFix(unittest.TestCase):
    def test_imprime_fix_y_validacion(self):
        lineas = vacunas.comandos_fix('/w/ms-psp', '22-alpine', 1000, 1000)
        self.assertEqual(len(lineas), 2)
        self.assertIn('--package-lock-only', lineas[0])
        self.assertNotIn('--force', lineas[0])
        self.assertIn('npm ci', lineas[1])


class Cli(unittest.TestCase):
    def test_detectar_imprime_los_repos(self):
        with TemporaryDirectory() as tmp:
            repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            repo(tmp, 'ms-faena', {'Dockerfile': 'FROM php:8.1\n'}, package=None)
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = vacunas.main(['--detectar', '--raiz', tmp])
            self.assertEqual(rc, 0)
            self.assertIn('ms-psp dentro', buf.getvalue())
            self.assertNotIn('ms-faena', buf.getvalue())

    def test_escanear_escribe_el_json_en_out(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            out = Path(tmp) / 'salida'
            out.mkdir()
            import io
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                rc = vacunas.main(['--worktree', str(d), '--repo', 'ms-psp', '--out', str(out),
                                   '--base', 'migracion-psp', '--dry-run'])
            self.assertEqual(rc, 0)
            datos = json.loads((out / 'ms-psp.json').read_text(encoding='utf-8'))
            self.assertEqual(datos['base'], 'migracion-psp')
            self.assertEqual(datos['node_tag'], '22-alpine')


class RutasAbsolutas(unittest.TestCase):
    def test_escanear_monta_ruta_absoluta(self):
        with TemporaryDirectory() as tmp:
            repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            llamadas = []

            def ejecutar(cmd):
                llamadas.append(cmd)
                return 0, '{}', ''

            import os as _os
            previo = _os.getcwd()
            _os.chdir(tmp)
            try:
                vacunas.escanear('ms-psp', 'ms-psp', 'master', ejecutar)
            finally:
                _os.chdir(previo)
            montajes = [a for cmd in llamadas for a in cmd if ':/app' in a or ':/src' in a]
            self.assertTrue(montajes)
            for m in montajes:
                self.assertTrue(m.startswith('/'), m)

    def test_comandos_fix_imprime_ruta_absoluta(self):
        with TemporaryDirectory() as tmp:
            repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            import io
            import contextlib
            import os as _os
            previo = _os.getcwd()
            _os.chdir(tmp)
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    vacunas.main(['--comandos', '--worktree', 'ms-psp'])
            finally:
                _os.chdir(previo)
            self.assertNotIn('-v ms-psp:', buf.getvalue())
            self.assertIn(f'-v {Path(tmp).resolve()}/ms-psp:', buf.getvalue())


class EjecutarReal(unittest.TestCase):
    def test_separa_stdout_de_stderr(self):
        rc, salida, err = vacunas._ejecutar_real(
            [sys.executable, '-c', 'import sys;print("{}");print("INFO log", file=sys.stderr)'])
        self.assertEqual(rc, 0)
        self.assertEqual(salida.strip(), '{}')
        self.assertIn('INFO log', err)
        self.assertNotIn('INFO log', salida)


class SeccionSinFuga(unittest.TestCase):
    def test_json_valido_con_log_en_stderr_se_parsea(self):
        def ejecutar(cmd):
            return 0, json.dumps(TRIVY_SECRET), 'INFO Secret scanning is enabled\n'

        r = vacunas._seccion(ejecutar, ['x'], vacunas.normalizar_secretos, secreto=True)
        self.assertEqual(r, [{'archivo': 'src/config.ts', 'linea': 14, 'tipo': 'generic-api-key'}])

    def test_error_no_incluye_la_salida_cruda(self):
        def ejecutar(cmd):
            return 1, json.dumps(TRIVY_VULN)[:60], 'FATAL failed to download vulnerability DB\n'

        r = vacunas._seccion(ejecutar, ['x'], vacunas.normalizar_trivy_vuln)
        self.assertNotIn('CVE-2024-4068', json.dumps(r))
        self.assertIn('failed to download', r['error'])

    def test_la_seccion_de_secretos_no_propaga_ninguna_salida(self):
        def ejecutar(cmd):
            return 1, 'AKIAIOSFODNN7EXAMPLE', 'leak AKIAIOSFODNN7EXAMPLE en stderr'

        r = vacunas._seccion(ejecutar, ['x'], vacunas.normalizar_secretos, secreto=True)
        self.assertNotIn('AKIA', json.dumps(r))
        self.assertIn('error', r)

    def test_json_que_no_es_objeto_queda_como_error(self):
        def ejecutar(cmd):
            return 0, '"texto"', ''

        r = vacunas._seccion(ejecutar, ['x'], vacunas.normalizar_npm)
        self.assertIn('error', r)


class EscanearSinFuga(unittest.TestCase):
    def test_el_secreto_no_llega_al_json_si_trivy_no_devuelve_json(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            crudo = json.dumps(TRIVY_SECRET)

            def ejecutar(cmd):
                if 'secret' in cmd:
                    return 1, crudo[:120], 'INFO scanning'
                return 0, '{}', ''

            r = vacunas.escanear(str(d), 'ms-psp', 'master', ejecutar)
            self.assertNotIn('AKIAIOSFODNN7EXAMPLE', json.dumps(r, ensure_ascii=False))


class SinLockfile(unittest.TestCase):
    def test_escanear_no_corre_audit_sin_lockfile(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-permisos', {'Dockerfile.test': 'FROM node:20-alpine\n'},
                     package={}, lock=False)
            llamadas = []

            def ejecutar(cmd):
                llamadas.append(cmd)
                return 0, '{}', ''

            r = vacunas.escanear(str(d), 'ms-permisos', 'master', ejecutar)
            self.assertTrue(r['sin_lock'])
            self.assertIn('package-lock.json', r['npm']['error'])
            self.assertFalse([cmd for cmd in llamadas if 'audit' in cmd])
            self.assertIn('npm', r['scan_incompleto'])

    def test_comandos_no_imprime_el_fix_sin_lockfile(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-permisos', {'Dockerfile.test': 'FROM node:20-alpine\n'},
                     package={}, lock=False)
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                rc = vacunas.main(['--comandos', '--worktree', str(d)])
            self.assertEqual(rc, 1)
            self.assertNotIn('audit fix', buf.getvalue())


class ScanIncompleto(unittest.TestCase):
    def test_npm_con_error_no_se_reporta_como_limpio(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})

            def ejecutar(cmd):
                if 'audit' in cmd:
                    return 1, '', 'npm ERR! code E500'
                return 0, '{}', ''

            r = vacunas.escanear(str(d), 'ms-psp', 'master', ejecutar)
            self.assertIn('npm', r['scan_incompleto'])
            self.assertTrue([n for n in r['notas'] if 'npm' in n])


class PlanValidacion(unittest.TestCase):
    def test_salta_el_script_que_no_existe(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'web-cliente-react', {'Dockerfile.prod': 'FROM node:20 AS build\n'},
                     package={'scripts': {'build': 'vite build'}})
            correr, salteados, flags = vacunas.plan_validacion(d)
            self.assertEqual(correr, ['build'])
            self.assertEqual(salteados, ['test'])

    def test_flags_de_jest_solo_cuando_el_runner_es_jest(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'},
                     package={'scripts': {'build': 'nest build', 'test': 'jest'}})
            self.assertIn('--maxWorkers=2', vacunas.plan_validacion(d)[2])

    def test_vitest_no_recibe_flags_de_jest(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'onboarding-psp', {'Dockerfile.prod': 'FROM node:20 AS builder\n'},
                     package={'scripts': {'build': 'vite build', 'test': 'vitest run'}})
            self.assertEqual(vacunas.plan_validacion(d)[2], '')

    def test_run_in_band_no_recibe_maxworkers(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'bridge-node', {'Dockerfile.test': 'FROM node:22-alpine\n'},
                     package={'scripts': {'test': 'jest --runInBand'}})
            self.assertNotIn('--maxWorkers', vacunas.plan_validacion(d)[2])

    def test_validar_solo_corre_los_scripts_pedidos(self):
        guion = vacunas.cmd_validar('/w/x', '20', correr=['build'], flags='')[-1]
        self.assertIn('npm run build', guion)
        self.assertNotIn('npm run test', guion)

    def test_validar_neutraliza_prepare_y_git(self):
        guion = vacunas.cmd_validar('/w/x', '22-alpine')[-1]
        self.assertIn('rm -rf .git', guion)
        self.assertIn('npm pkg delete scripts.prepare', guion)

    def test_comandos_avisa_los_scripts_salteados(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'web-cliente-react', {'Dockerfile.prod': 'FROM node:20 AS build\n'},
                     package={'scripts': {'build': 'vite build'}})
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                vacunas.main(['--comandos', '--worktree', str(d)])
            self.assertIn('SALTEADOS: test', buf.getvalue())


class Clasificacion(unittest.TestCase):
    def test_detectar_informa_los_que_quedan_afuera_con_motivo(self):
        with TemporaryDirectory() as tmp:
            repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            repo(tmp, 'ms-permisos', {'Dockerfile': 'FROM node:20-alpine\n'}, package={}, lock=False)
            repo(tmp, 'api-testing-end2end', {'Dockerfile': 'FROM cypress/base:16\n'}, package={})
            repo(tmp, 'ms-faena', {'Dockerfile': 'FROM php:8.1\n'}, package=None)
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                vacunas.main(['--detectar', '--raiz', tmp])
            salida = buf.getvalue()
            self.assertIn('ms-psp dentro', salida)
            self.assertIn('ms-permisos fuera sin-package-lock', salida)
            self.assertIn('api-testing-end2end fuera sin-FROM-node', salida)
            self.assertNotIn('ms-faena', salida)


class OutDir(unittest.TestCase):
    def test_crea_el_directorio_de_salida(self):
        with TemporaryDirectory() as tmp:
            d = repo(tmp, 'ms-psp', {'Dockerfile.test': 'FROM node:22-alpine\n'}, package={})
            out = Path(tmp) / 'nueva' / 'carpeta'
            import io
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                rc = vacunas.main(['--worktree', str(d), '--repo', 'ms-psp', '--out', str(out),
                                   '--dry-run'])
            self.assertEqual(rc, 0)
            self.assertTrue((out / 'ms-psp.json').is_file())


class SinForce(unittest.TestCase):
    def test_ningun_comando_lleva_force_ni_omit_dev(self):
        todos = [vacunas.cmd_audit('/w/x', '20'), vacunas.cmd_trivy_fs('/w/x'),
                 vacunas.cmd_trivy_image('20'), vacunas.cmd_trivy_secret('/w/x'),
                 vacunas.cmd_audit_fix('/w/x', '20', 1000, 1000), vacunas.cmd_validar('/w/x', '20')]
        for cmd in todos:
            texto = ' '.join(cmd)
            self.assertNotIn('--force', texto)
            self.assertNotIn('--omit=dev', texto)
            self.assertNotIn('trivyignore', texto)


if __name__ == '__main__':
    unittest.main()
