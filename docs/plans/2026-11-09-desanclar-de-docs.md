# Desanclar a Clarabella de `dcac-ia-context/docs` — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que todo el material de un ticket nazca dentro del cerebro de contexto
(`~/projects/portfolio`) en vez de `dcac-ia-context/docs/`, para que quede en un repo y no
solo en la máquina de Marcos.

**Architecture:** la forma de la carpeta deja de estar escrita a mano en 17 markdowns y pasa
a vivir en un único comando del cerebro, `cerebro ubicar`, que resuelve el nombre del
proyecto contra el catálogo, crea la carpeta y la imprime. Las skills dejan de construir
rutas: preguntan. `bin/publicar` pasa a subir el árbol completo de cada proyecto menos lo
ignorado, así el exhaust de las corridas vive en el repo sin viajar a GitHub.

**Tech Stack:** Python 3.12 solo stdlib; pytest en `~/projects/portfolio/.venv` para el
cerebro; `unittest` para el plugin `clarabella`; markdown para las skills.

**Spec:** no hay documento de diseño aparte. Las decisiones las tomó Marcos en la
conversación del 2026-11-09 y están abajo, en Global Constraints, como las dijo.

## Global Constraints

- **La documentación del ticket va al portfolio.** `plan.md`, `tests.md`, `spec.md`,
  `resumen.md`, `cronica.md`, `sentencia.md`, `revision/`, `decisiones.md` y `lotes/`.
- **El exhaust va al repo pero no se pushea.** `.pipeline/`, `pipeline/` y `_pipeline/` al
  `.gitignore` del portfolio.
- **Los worktrees se quedan en la máquina.** Este plan no los mueve.
- **Un proyecto que no resuelve contra el catálogo no frena el ciclo**: el material va a
  `proyectos/_sin-clasificar/T#####-<slug>/` y queda una entrada en la bandeja.
- **`docs/` queda congelado** como la copia vieja. No se borra: es decisión de Marcos.
  Ninguna skill vuelve a nombrarlo.
- **El CLI del cerebro se invoca por su ruta completa.** Resuelve el almacén desde su propia
  ubicación; un `cerebro` suelto archiva donde estés parado.
- **La raíz del cerebro se resuelve así**: `$CEREBRO_RAIZ`, o `~/projects/portfolio`.
- Sin comentarios en el código. `git add` nunca con `-A` ni con directorios.

## Review Focus

- **No hay cerebro en la máquina**: una skill de escritura no tiene dónde archivar. Debe
  frenar y decirlo, nunca escribir en un `proyectos/` relativo al directorio actual.
- **`publicar` sobre un árbol de 1300 archivos**: la lista explícita de rutas puede pasarse
  del largo de argumentos del sistema y hacer fallar el `git add`.
- **Un archivo ignorado en la lista de rutas**: `git add -- <ignorado>` devuelve error y
  tumba la publicación entera, incluso la del estado y la bandeja.
- **El mismo ticket ubicado dos veces con el proyecto resuelto distinto** (primero
  `_sin-clasificar`, después el slug real): quedan dos carpetas para un solo ticket y la
  segunda corrida no encuentra el `plan.md` de la primera.
- **Un proyecto transversal como destino de un ticket**: la carpeta cuelga de
  `transversal/<slug>/`, no de `proyectos/<slug>/`, y quien construya la ruta a mano la
  erra.

---

### Task 1: `cerebro ubicar` — la carpeta del ticket, en un solo lugar

**Files:**
- Create: `~/projects/portfolio/cerebro/ubicar.py`
- Modify: `~/projects/portfolio/cerebro/cli.py` (el `import` de `cerebro`, el subparser y la
  rama de `_ejecutar`)
- Test: `~/projects/portfolio/tests/test_ubicar.py`

**Interfaces:**
- Consumes: `catalogo.resolver(texto, entradas) -> Resolucion(certeza, slug, candidatos)`;
  `catalogo.cargar(raiz)`; `almacen.carpeta(slug, raiz, ambito)`;
  `almacen.escribir(proyecto, raiz, ambito)`;
  `bandeja.encolar(texto, motivo, candidatos, origen, fecha, raiz)`.
- Produces: `ubicar.ubicar(proyecto, raiz, fecha, tipo="", ticket="", nombre="") -> dict`
  con las claves `slug`, `ambito`, `certeza`, `carpeta` (ruta absoluta, ya creada) y
  `bandeja` (número o `None`) y `duplicado` (ruta de otra carpeta del mismo ticket, o
  `None`). `ubicar.SIN_CLASIFICAR = "_sin-clasificar"`.
  `ubicar.CIERTAS = ("exacta", "alias", "contenido")`.
  Subcomando `cerebro ubicar --proyecto <texto> [--tipo desarrollo|soporte --ticket T#####
  --nombre <slug-del-ticket>]`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
def test_ubica_la_carpeta_del_proyecto_resuelto(raiz_catalogo):
    r = ubicar.ubicar("alta productores psp", raiz_catalogo, "2026-11-09")
    assert r["slug"] == "alta-productores"
    assert r["certeza"] == "alias"
    assert r["carpeta"] == str(raiz_catalogo / "proyectos" / "alta-productores")
    assert Path(r["carpeta"]).is_dir()


def test_ubica_la_carpeta_del_ticket_bajo_su_tipo(raiz_catalogo):
    r = ubicar.ubicar(
        "alta productores psp", raiz_catalogo, "2026-11-09",
        tipo="soporte", ticket="T23456", nombre="cvu-trabada",
    )
    assert r["carpeta"].endswith("proyectos/alta-productores/soporte/T23456-cvu-trabada")
    assert Path(r["carpeta"]).is_dir()


def test_un_transversal_cuelga_de_transversal(raiz_catalogo):
    r = ubicar.ubicar("diagramas", raiz_catalogo, "2026-11-09")
    assert r["ambito"] == "transversal"
    assert r["carpeta"] == str(raiz_catalogo / "transversal" / "umls")


def test_siembra_el_proyecto_md_desde_el_catalogo(raiz_catalogo):
    ubicar.ubicar("alta productores psp", raiz_catalogo, "2026-11-09")
    assert almacen.leer("alta-productores", raiz_catalogo).squad == "pagos"


def test_un_proyecto_que_no_resuelve_va_a_sin_clasificar_y_a_la_bandeja(raiz_catalogo):
    r = ubicar.ubicar(
        "proyecto que no existe", raiz_catalogo, "2026-11-09",
        tipo="desarrollo", ticket="T99999", nombre="algo",
    )
    assert r["slug"] == "_sin-clasificar"
    assert r["certeza"] == "desconocida"
    assert r["carpeta"].endswith("proyectos/_sin-clasificar/desarrollo/T99999-algo")
    assert r["bandeja"] == 1
    assert bandeja.listar(raiz_catalogo)[0]["motivo"] == "desconocida"


def test_un_nombre_ambiguo_tambien_va_a_sin_clasificar_con_los_candidatos(raiz_catalogo):
    r = ubicar.ubicar("alta", raiz_catalogo, "2026-11-09")
    assert r["slug"] == "_sin-clasificar"
    assert r["certeza"] == "ambigua"
    assert bandeja.listar(raiz_catalogo)[0]["candidatos"]


def test_sin_clasificar_no_siembra_un_proyecto_md(raiz_catalogo):
    ubicar.ubicar("proyecto que no existe", raiz_catalogo, "2026-11-09")
    assert "_sin-clasificar" not in almacen.listar(raiz_catalogo)


def test_ubicar_dos_veces_no_duplica_la_entrada_de_bandeja(raiz_catalogo):
    for _ in range(2):
        ubicar.ubicar(
            "proyecto que no existe", raiz_catalogo, "2026-11-09",
            tipo="desarrollo", ticket="T99999", nombre="algo",
        )
    assert len(bandeja.listar(raiz_catalogo)) == 1


def test_avisa_si_el_mismo_ticket_ya_tiene_carpeta_en_otro_proyecto(raiz_catalogo):
    ubicar.ubicar(
        "proyecto que no existe", raiz_catalogo, "2026-11-09",
        tipo="desarrollo", ticket="T23456", nombre="cvu-trabada",
    )
    r = ubicar.ubicar(
        "alta productores psp", raiz_catalogo, "2026-11-09",
        tipo="desarrollo", ticket="T23456", nombre="cvu-trabada",
    )
    assert r["duplicado"].endswith("proyectos/_sin-clasificar/desarrollo/T23456-cvu-trabada")


def test_sin_duplicado_la_clave_viene_vacia(raiz_catalogo):
    r = ubicar.ubicar(
        "alta productores psp", raiz_catalogo, "2026-11-09",
        tipo="desarrollo", ticket="T23456", nombre="x",
    )
    assert r["duplicado"] is None


def test_el_comando_imprime_la_carpeta(raiz_catalogo, capsys):
    assert cli.main([
        "--raiz", str(raiz_catalogo), "ubicar", "--proyecto", "alta productores psp",
        "--tipo", "desarrollo", "--ticket", "T23456", "--nombre", "x",
    ]) == 0
    assert json.loads(capsys.readouterr().out)["slug"] == "alta-productores"


def test_el_tipo_tiene_que_ser_una_categoria_del_almacen(raiz_catalogo, capsys):
    assert cli.main([
        "--raiz", str(raiz_catalogo), "ubicar", "--proyecto", "alta productores psp",
        "--tipo", "inventado", "--ticket", "T1", "--nombre", "x",
    ]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "TipoInvalido"
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd ~/projects/portfolio && .venv/bin/python -m pytest tests/test_ubicar.py -q`
Expected: FAIL en la importación, `cannot import name 'ubicar' from 'cerebro'`.

- [ ] **Step 3: Implementar `cerebro/ubicar.py`**

`ubicar(proyecto, raiz, fecha, tipo="", ticket="", nombre="")`: resuelve con
`catalogo.resolver`; si la certeza está en `CIERTAS` usa el slug y el ámbito de la entrada y
siembra el `proyecto.md` como hace `cli._asegurar`; si no, usa `SIN_CLASIFICAR` en
`proyectos`, no siembra nada y encola en la bandeja con el motivo igual a la certeza y los
candidatos de la resolución. Cuando vienen `tipo`, `ticket` y `nombre`, la carpeta es
`<carpeta del proyecto>/<tipo>/<ticket>-<nombre>`. Crea la carpeta con `mkdir(parents=True,
exist_ok=True)` y devuelve la ruta absoluta como `str`.

La bandeja no se duplica: antes de encolar, revisá si ya hay una entrada con el mismo texto
en `bandeja.listar(raiz)` y en ese caso devolvé su número sin encolar de nuevo.

`TipoInvalido(Exception)` vive en `ubicar.py`; el `tipo`, cuando viene, tiene que estar en
`almacen.CATEGORIAS`.

`duplicado`: cuando viene `ticket`, buscá con `glob` otra carpeta `<ticket>-*` bajo cualquier
`<ambito>/<slug>/<tipo>/` que no sea la elegida, y devolvé la primera que encuentres. Es un
aviso, no un error: la carpeta elegida se crea igual.

- [ ] **Step 4: Cablear el subcomando en `cerebro/cli.py`**

Agregá `ubicar` al `import` de `cerebro`, un subparser `ubicar` con `--proyecto` (requerido)
y `--tipo`, `--ticket`, `--nombre` (opcionales, default `""`), y la rama
`if comando == "ubicar": return ubicar.ubicar(args.proyecto, raiz, fecha, args.tipo,
args.ticket, args.nombre)`. El subcomando **no** entra en `ESCRIBEN`: `ubicar` siembra por
su cuenta y no recibe un `slug`.

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `cd ~/projects/portfolio && .venv/bin/python -m pytest -q`
Expected: PASS, toda la suite verde.

- [ ] **Step 6: Commit**

```bash
cd ~/projects/portfolio
git add cerebro/ubicar.py cerebro/cli.py tests/test_ubicar.py
git commit -m "feat: ubicar resuelve la carpeta de un proyecto y de un ticket"
```

---

### Task 2: `publicar` sube el árbol del proyecto y deja el exhaust afuera

**Files:**
- Modify: `~/projects/portfolio/cerebro/publicar.py`
- Modify: `~/projects/portfolio/.gitignore`
- Test: `~/projects/portfolio/tests/test_publicar.py`,
  `~/projects/portfolio/tests/test_robustez.py`

**Interfaces:**
- Consumes: nada de la Task 1.
- Produces: `publicar._rutas(raiz) -> list[str]` devuelve **todos** los archivos bajo
  `proyectos/` y `transversal/` que git no ignora, más los `SUELTOS` que existan.

- [ ] **Step 1: Escribir los tests que fallan**

```python
def test_publica_el_material_del_ticket_no_solo_el_indice(repo_git):
    carpeta = repo_git / "proyectos" / "minimo" / "desarrollo" / "T1-x"
    carpeta.mkdir(parents=True)
    (carpeta / "plan.md").write_text("el plan", encoding="utf-8")
    _sembrar(repo_git, "proyectos", "minimo")
    publicar.publicar(repo_git, "sube el ticket")
    assert "proyectos/minimo/desarrollo/T1-x/plan.md" in _correr(repo_git, "show", "--name-only", "HEAD")


def test_no_publica_el_exhaust_ignorado(repo_git):
    (repo_git / ".gitignore").write_text(".pipeline/\n", encoding="utf-8")
    carpeta = repo_git / "proyectos" / "minimo" / "desarrollo" / "T1-x" / ".pipeline"
    carpeta.mkdir(parents=True)
    (carpeta / "actividad.jsonl").write_text("{}", encoding="utf-8")
    _sembrar(repo_git, "proyectos", "minimo")
    publicar.publicar(repo_git, "sube el ticket")
    assert "actividad.jsonl" not in _correr(repo_git, "show", "--name-only", "HEAD")


def test_un_archivo_ignorado_no_tumba_la_publicacion(repo_git):
    (repo_git / ".gitignore").write_text("pipeline/\n", encoding="utf-8")
    carpeta = repo_git / "proyectos" / "minimo" / "pipeline"
    carpeta.mkdir(parents=True)
    (carpeta / "T1_estado.json").write_text("{}", encoding="utf-8")
    _sembrar(repo_git, "proyectos", "minimo")
    assert publicar.publicar(repo_git, "sube el ticket") == 0


def test_publica_un_arbol_grande_sin_pasarse_del_largo_de_argumentos(repo_git):
    _sembrar(repo_git, "proyectos", "minimo")
    carpeta = repo_git / "proyectos" / "minimo" / "notas"
    carpeta.mkdir(parents=True)
    for n in range(600):
        (carpeta / f"n{n}.md").write_text(str(n), encoding="utf-8")
    assert publicar.publicar(repo_git, "sube muchos") == 0
    assert "proyectos/minimo/notas/n599.md" in _correr(repo_git, "show", "--name-only", "HEAD")


def test_el_gitignore_del_cerebro_tapa_el_exhaust():
    texto = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")
    for patron in (".pipeline/", "pipeline/", "_pipeline/"):
        assert patron in texto.split("\n")
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd ~/projects/portfolio && .venv/bin/python -m pytest tests/test_publicar.py -q`
Expected: FAIL — el `plan.md` no aparece en el commit, y el `.gitignore` todavía no tiene los
tres patrones.

- [ ] **Step 3: Agregar los tres patrones al `.gitignore` del portfolio**

`.pipeline/`, `pipeline/` y `_pipeline/`, una línea cada uno.

- [ ] **Step 4: Reescribir `publicar._rutas`**

Recorré `proyectos/` y `transversal/` con `rglob("*")`, quedate con los archivos, y sacá los
ignorados en **una sola** llamada a `git check-ignore --stdin` (código de salida 1 cuando
ninguno coincide: no es un fallo). Las rutas salen relativas a la raíz y con `/`.

Para no pasarse del largo de argumentos del sistema, `_git(raiz, "add", "--", *rutas)` y el
`status --porcelain` se mandan en tandas de 500 rutas. El `commit --only -- *rutas` también.

- [ ] **Step 5: Correr toda la suite**

Run: `cd ~/projects/portfolio && .venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/projects/portfolio
git add .gitignore cerebro/publicar.py tests/test_publicar.py tests/test_robustez.py
git commit -m "feat: publicar sube el material del ticket y deja el exhaust afuera"
```

---

### Task 3: las 13 skills del plugin dejan de nombrar `docs/`

**Files:**
- Modify: `~/projects/clarabella/tests/test_referencias.py` (la lista `PROHIBIDO`)
- Modify: `~/projects/clarabella/skills/{baqueano,cronista,escribano,implementar-ticket,juzgar-proyecto,leer-db,planear-tests-ticket,planear-ticket,resolver-proyecto,resolver-ticket,resumir-ticket,revisar-ticket,testear-ticket}/SKILL.md`
- Modify: `~/projects/clarabella/skills/consultar-portfolio/SKILL.md:39` (la única mención
  que queda, sobre las carpetas de `docs/`)
- Test: `~/projects/clarabella/tests/test_referencias.py`

**Interfaces:**
- Consumes: el subcomando `cerebro ubicar` de la Task 1, con la forma exacta de su bloque
  `Produces`.
- Produces: nada que consuma otra task.

- [ ] **Step 1: Escribir el test que falla**

En `tests/test_referencias.py`, agregá a `PROHIBIDO` las cadenas `'docs/{proyecto}'`,
`'docs/<proyecto>'`, `'docs/_pipeline'` y `'carpeta de `docs/`'`. Y un test nuevo que fije
el caso de la máquina sin cerebro:

```python
ESCRIBEN = ['planear-ticket', 'planear-tests-ticket', 'implementar-ticket', 'testear-ticket',
            'revisar-ticket', 'resumir-ticket', 'cronista', 'resolver-proyecto']


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
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd ~/projects/clarabella && python3 -m unittest tests.test_referencias -v`
Expected: FAIL nombrando los 14 archivos.

- [ ] **Step 3: Reemplazar las rutas en cada skill**

En cada una, la ruta escrita a mano pasa a ser una llamada. El bloque que va donde hoy se
pregunta por la carpeta de `docs/`:

```
La carpeta del ticket la da el cerebro, no la armes a mano:

~/projects/portfolio/bin/cerebro ubicar --proyecto "<lo que nombra el ticket>" \
  --tipo <desarrollo|soporte> --ticket T##### --nombre <slug-del-ticket>

Devuelve `carpeta` (ya creada), `slug` y `certeza`. Si `certeza` es `ambigua` o
`desconocida`, el material va igual a `_sin-clasificar` y queda una entrada en la bandeja:
decilo en el informe y seguí, no frenes a preguntar.
```

Donde la skill solo necesita la carpeta del proyecto (`decisiones.md`, `lotes/`), la misma
llamada sin `--tipo/--ticket/--nombre`.

Las que solo **leen** material de tickets anteriores (`baqueano:22,25,26`, `leer-db:235`,
`escribano:50`, `juzgar-proyecto:22`) arrancan por `consultar-portfolio` y después miran
`<carpeta>/`, sin nombrar `docs/`.

Las tres líneas de `description:` del frontmatter que hoy citan rutas de `docs/`
(`implementar-ticket`, `resumir-ticket`, `testear-ticket`) pasan a decir "en la carpeta del
ticket dentro del cerebro de contexto".

- [ ] **Step 4: Agregar el bloque de raíz del cerebro a las skills que escriben**

`planear-ticket`, `planear-tests-ticket`, `implementar-ticket`, `testear-ticket`,
`revisar-ticket`, `resumir-ticket`, `cronista` y `resolver-proyecto` llevan, antes de la
primera escritura:

```
Resolvé la raíz del cerebro así: `$CEREBRO_RAIZ`, o `~/projects/portfolio`. Si no existe,
**frená y decilo**: sin cerebro no hay dónde archivar el ticket. No escribas en un
`proyectos/` relativo al directorio donde estás parado.
```

- [ ] **Step 5: Correr la suite del plugin**

Run: `cd ~/projects/clarabella && python3 -m unittest discover -s tests`
Expected: PASS, 134 tests o más.

- [ ] **Step 6: Commit**

```bash
cd ~/projects/clarabella
git add tests/test_referencias.py skills/baqueano/SKILL.md skills/consultar-portfolio/SKILL.md skills/cronista/SKILL.md skills/escribano/SKILL.md skills/implementar-ticket/SKILL.md skills/juzgar-proyecto/SKILL.md skills/leer-db/SKILL.md skills/planear-tests-ticket/SKILL.md skills/planear-ticket/SKILL.md skills/resolver-proyecto/SKILL.md skills/resolver-ticket/SKILL.md skills/resumir-ticket/SKILL.md skills/revisar-ticket/SKILL.md skills/testear-ticket/SKILL.md
git commit -m "feat: el material del ticket vive en el cerebro, no en docs/"
```

---

### Task 4: las 4 skills globales y la máquina del pipeline

**Files:**
- Modify: `~/.claude/skills/pipeline-desarrollo/SKILL.md`
- Modify: `~/.claude/skills/dashboard-desarrollo/SKILL.md`
- Modify: `~/.claude/skills/entorno-ticket/SKILL.md`
- Modify: `~/.claude/skills/previsualizar-cambios/SKILL.md`

**Interfaces:**
- Consumes: `cerebro ubicar` de la Task 1 y los patrones del `.gitignore` de la Task 2.
- Produces: nada.

Estas cuatro no viven en un repo y no tienen suite. La verificación es un grep con salida
esperada, no un test.

- [ ] **Step 1: Mover la carpeta del ticket a la llamada a `ubicar`**

En las cuatro, `docs/{proyecto}/{tipo}/T#####-{slug}/` pasa a ser la `carpeta` que devuelve
`cerebro ubicar`, con el mismo bloque de la Task 3, Step 3.

- [ ] **Step 2: Mover el estado del dashboard al cerebro, ignorado**

`docs/{proyecto}/pipeline/*.json` → `<carpeta del proyecto>/pipeline/*.json`.
`docs/_pipeline/cola.json` y `docs/_pipeline/historial/` → `<raíz del cerebro>/_pipeline/`.
Los tres patrones ya están en el `.gitignore` del portfolio (Task 2), así que nada de esto
viaja a GitHub. Dejá dicho en `dashboard-desarrollo` que el estado es local y se puede
borrar sin perder documentación.

- [ ] **Step 3: Verificar que no queda ninguna mención**

Run: `grep -rn 'docs/{proyecto}\|docs/_pipeline\|docs/<proyecto>' ~/.claude/skills/ ~/projects/clarabella/skills/`
Expected: sin resultados.

- [ ] **Step 4: Verificar que el pipeline encuentra una carpeta de verdad**

Run: `~/projects/portfolio/bin/cerebro ubicar --proyecto "permisos psp" --tipo desarrollo --ticket T99999 --nombre humo`
Expected: JSON con `"slug": "back-permisos-psp"`, `"certeza": "alias"` y una `carpeta` que
existe. Después borrala: `rm -r ~/projects/portfolio/proyectos/back-permisos-psp/desarrollo/T99999-humo`.

---

### Task 5: dejar escrito dónde vive cada cosa

**Files:**
- Modify: `~/projects/portfolio/README.md`
- Modify: `~/projects/clarabella/README.md`
- Modify: `~/projects/portfolio/catalogo.md` (la sección `## Pendiente`, que ya no aplica)

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: nada.

- [ ] **Step 1: El README del portfolio**

Agregá `ubicar` al listado de comandos, y una sección corta que diga qué sube `publicar`
(todo menos lo ignorado), qué es exhaust y por qué `docs/` quedó congelado.

- [ ] **Step 2: El README de clarabella**

La fila de `cargar-portfolio`/`consultar-portfolio` ya está. Agregá una línea donde dice que
las skills asumen la estructura de `dcac-ia-context`: el material del ticket ahora sale del
cerebro, y el workspace queda solo para el código.

- [ ] **Step 3: La sección `## Pendiente` del catálogo**

Decía que LyC estaba incompleto. Ya no: reemplazala por lo que sigue abierto (las nueve
carpetas de `docs/` sin alias, si todavía aplica) o borrala.

- [ ] **Step 4: Correr las dos suites**

Run: `cd ~/projects/portfolio && .venv/bin/python -m pytest -q && cd ~/projects/clarabella && python3 -m unittest discover -s tests`
Expected: PASS las dos.

- [ ] **Step 5: Commit en los dos repos**

```bash
cd ~/projects/portfolio && git add README.md catalogo.md && git commit -m "docs: donde vive el material de un ticket"
cd ~/projects/clarabella && git add README.md && git commit -m "docs: el material del ticket sale del cerebro"
```
