# vacunar-repos — diseño

Fecha: 2026-10-15 · Base: 0.6.0 · Versión objetivo: 0.7.0

## Problema

El prediff de Jenkins (`repository-prediff-nodejs` → `isolated-npm-unittest`) corta un diff
de un repo Node si `npm audit` reporta HIGH o CRITICAL, devDependencies incluidas. El
hallazgo aparece recién cuando la Differential ya está creada, repo por repo, y se resuelve
a mano: así se fue T23833 en `bridge-node` (7 HIGH de `braces` vía `tsc-alias` y `nodemon`).

Hoy no hay forma de preguntarle al workspace "¿qué repos Node tienen vulnerabilidades y
cuáles se arreglan sin romper nada?" sin recorrerlos de a uno.

## Objetivo

Una skill que, sobre los repos Node del workspace, escanee vulnerabilidades, aplique **solo
el fix seguro**, valide que no rompió nada, y deje el resto como decisión del usuario — con
el diff a la vista y el envío a review gateado por su OK.

**Criterios de éxito**

- El scan corre sin instalar nada en el host: node y trivy van en contenedores efímeros.
- La versión de node de cada repo sale de su Dockerfile, no del host ni de una suposición.
- El único cambio que la skill aplica sola es `npm audit fix` no-breaking, validado con los
  tests del repo.
- Nada se silencia: lo que no se arregla se reporta con severidad y motivo.
- Los JSON crudos de `npm audit` y trivy no entran al contexto de ningún agente.
- El canónico de cada repo nunca cambia de rama.

## Alcance

**Entra:** dependencias npm (lockfile), imagen base declarada en el `FROM`, y secretos en el
contenido versionado.

**No entra:** misconfig de Dockerfile (`trivy config`), vulnerabilidades de código propio
(SAST), y cualquier repo que no sea Node.

## Decisiones tomadas

| Decisión | Motivo |
|----------|--------|
| Todo en contenedores efímeros | Trivy no está instalado en el host y el host tiene node 18 por default: la versión del repo solo se garantiza con su propia imagen |
| La imagen base se escanea **por su tag**, sin construirla | `docker build -f Dockerfile.prod` es caro y frágil (registry privado, build args), y como bumpear el `FROM` está prohibido el hallazgo es informativo igual |
| El fix va a un **worktree**, no al canónico | Regla del plugin (`preparar-repo`): el canónico queda en su rama base, solo lectura |
| Sin ticket obligatorio | La corrida no nace de un ticket; el `T#####` es opcional y se pasa al momento del envío |
| Informe solo en el chat | No deja archivos de informe en el workspace |
| Un subagente por repo | Los repos son independientes: no hay nada que coordinar entre ellos salvo el gate final |

## Piezas

| Pieza | Qué es |
|-------|--------|
| `skills/vacunar-repos/SKILL.md` | La skill: alcance, flujo, gates, formato de salida |
| `agents/veterinario.md` | El agente por repo (sonnet · medio), con `disallowedTools: Agent` |
| `scripts/vacunas.py` | Scan determinístico: detecta repos, lee la versión de node, corre audit y trivy, normaliza a JSON resumido |
| `tests/test_vacunas.py` | unittest de la parte determinística |

Integración: fila nueva en la tabla de `skills/clarabella/SKILL.md`, filas en el README
(skills y scripts), y `plugin.json` a 0.7.0.

## Flujo

### Paso 0 — alcance

El usuario nombra los repos, o dice "todos" y `vacunas.py --detectar` los lista: carpeta de
`microservicios/` con `package.json` y algún Dockerfile con `FROM node:`.

Se informan los que quedan afuera, no se adivinan:

- Sin `FROM node:` en ningún Dockerfile (ej. `api-testing-end2end`, que corre sobre
  `cypress/base:16`) → no se audita, se reporta.
- Sin `package-lock.json` → `npm audit` no tiene qué leer: se reporta.

Repos Node del workspace al momento de escribir esto: `apigateway-psp`, `bridge-node`,
`ms-compliance`, `ms-psp`, `ms-multimedia-psp` (node 22), `ms-permisos`, `onboarding-psp`,
`gestor-cuentas-mfe`, `dcp-frontend`, `web-cliente-react` (node 20), y
`api-testing-end2end` (cypress, fuera de alcance automático). La lista no se hardcodea: se
detecta en cada corrida.

### Paso 1 — preparar (por repo)

1. `git -C microservicios/<repo> status --porcelain`. Si hay cambios sin commitear →
   **frena ese repo** y avisa cuál. No hace stash ni descarta: ese trabajo es del usuario.
2. Rama base actualizada en el canónico: `master`, salvo excepción conocida (`ms-psp` →
   `migracion-psp`). Si la base no está clara, pregunta; no asume `main`.
3. Worktree `.worktrees/vacuna-AAAA-MM-DD/<repo>` en branch `vacuna-AAAA-MM-DD`, desde la
   rama base. Reanudable: si ya existe, lo reusa.

Que el worktree sea limpio tiene un efecto buscado: el scan de secretos ve **solo contenido
versionado**, así que los `.env` locales del canónico no pueden terminar en el informe.

### Paso 2 — scan (`vacunas.py`, sin tokens)

**Versión de node.** Del Dockerfile, en orden `Dockerfile.test` → `Dockerfile.dev` →
`Dockerfile` → `Dockerfile.prod`; dentro de cada uno, el primer `FROM node:<tag>`. Si
`engines.node` del `package.json` o un `.nvmrc` contradicen ese tag, se reporta como duda:
el script no elige por su cuenta. El Dockerfile manda.

**Comandos** (todos contenedores efímeros, `--rm`):

```bash
# dependencias npm — mount read-only, HOME y cache en /tmp
docker run --rm -v <worktree>:/app:ro -w /app -e HOME=/tmp \
  node:<tag> npm audit --json

# segunda opinión sobre el lockfile
docker run --rm -v clarabella-trivy-cache:/root/.cache/trivy -v <worktree>:/src:ro \
  <trivy> fs --scanners vuln --skip-dirs node_modules --format json /src

# imagen base, por su tag — no se construye nada
docker run --rm -v clarabella-trivy-cache:/root/.cache/trivy \
  <trivy> image --format json node:<tag>

# secretos en el contenido versionado
docker run --rm -v clarabella-trivy-cache:/root/.cache/trivy -v <worktree>:/src:ro \
  <trivy> fs --scanners secret --format json /src
```

La DB de trivy vive en el volumen `clarabella-trivy-cache`: se baja una vez, no once. La
imagen de trivy se fija por constante en el script (`--trivy-image` la sobreescribe), no
`latest`.

**Salida.** Un JSON resumido por repo en `--out <dir>` (la skill le pasa el scratchpad de la
sesión, nunca una ruta dentro del repo):

```json
{
  "repo": "bridge-node",
  "node_tag": "22-alpine",
  "node_tag_origen": "Dockerfile.test",
  "base": "master",
  "npm": {"critical": 0, "high": 7, "moderate": 2, "low": 1,
          "hallazgos": [{"paquete": "braces", "severidad": "high", "via": ["tsc-alias"],
                         "advisory": "GHSA-grv7-fg5c-xmjg", "fix_disponible": true,
                         "fix_breaking": false}]},
  "trivy_lock": {"criticos_altos": []},
  "imagen_base": {"tag": "node:22-alpine", "critical": 0, "high": 2, "hallazgos": []},
  "secretos": [{"archivo": "src/config.ts", "linea": 14, "tipo": "generic-api-key"}],
  "notas": []
}
```

El valor de un secreto **nunca** se incluye: archivo, línea y tipo. El normalizador arma cada
hallazgo con una lista blanca de campos, así que un valor que trivy repita en otro campo
tampoco se filtra.

`vacunas.py` escanea **un repo por invocación**: el paralelismo lo maneja la skill lanzando
hasta 3 invocaciones a la vez. El script no hace threads.

El script también expone `--comandos`, que imprime los comandos de fix y de validación ya
armados para ese repo. El Veterinario los copia de ahí en vez de reconstruirlos: así el
`--package-lock-only`, el `--user` y la ausencia de `--force` tienen una sola fuente.

### Paso 3 — fan-out de Veterinarios

Un subagente por repo, en tandas de 3. El límite es de recursos: la VM de Docker tiene
~3,6 GiB y hay tope de uso del plan.

Cada Veterinario, en su worktree:

1. Lee su JSON de scan (no vuelve a correr el scan).
2. Aplica el fix seguro, con el usuario del host para que el lock no quede de root:

```bash
docker run --rm -v <worktree>:/app -w /app -e HOME=/tmp -e npm_config_cache=/tmp/.npm \
  --user $(id -u):$(id -g) node:<tag> npm audit fix --package-lock-only
```

`--package-lock-only` toca `package-lock.json` (y `package.json` si hace falta) sin escribir
`node_modules`. **Sin `--force`.**

3. Re-audita igual que el paso 2 y mide qué bajó.
4. Valida, copiando el worktree **dentro** del contenedor para no escribir nada en el host
   ni pelearse con el ownership de un volumen:

```bash
docker run --rm -v <worktree>:/src:ro -w /tmp -e HOME=/tmp node:<tag> sh -c \
  "mkdir -p /work && cd /work && cp -a /src/. . && npm ci && npm run build && \
   npm run test -- --maxWorkers=2 --workerIdleMemoryLimit=512MB"
```

El comando de tests es el exacto del prediff. Si el repo no tiene script `build` o `test`,
lo saltea y lo dice.

5. Si los tests quedan rojos, repite la validación con el lock original
   (`git stash` del cambio) para distinguir dos casos:
   - **ya estaba rojo** → el fix se mantiene, y la validación se reporta como no concluyente;
   - **lo rompió el fix** → `git checkout` del lock y el hallazgo pasa a pendiente con el
     motivo. No intenta otra cosa.

**Prohibido para el Veterinario** (todo esto es duda, no decisión suya):

- `npm audit fix --force` y cualquier bump breaking.
- Cambiar la versión de node, el `FROM`, o la imagen base.
- Agregar `overrides` o `resolutions` en `package.json`.
- `.trivyignore`, `npm audit --omit=dev`, o cualquier forma de silenciar un hallazgo.
- Tocar código de producción, o commitear.

**Contrato de salida:**

```
ARTEFACTO: <repo> → <n> vulns resueltas (C:<n> H:<n> M:<n> L:<n>), lock actualizado | sin cambios
VALIDACIÓN: npm ci <OK|falla> · build <OK|falla|sin script> · tests <n passed|RED|sin script>
PENDIENTES:
  - [P1] <paquete> <advisory> <severidad> · vía <cadena> · <por qué no se arregló>
  - [P2] imagen base node:<tag> · <n> HIGH · bumpear el FROM está fuera de alcance
  - [P3] secreto en <archivo>:<línea> · <tipo>
DUDAS:
  - [D1] <decisión que requiere al usuario> · bloqueante | no bloqueante
ESTADO: completo | sin-cambios | frenado-por-duda | frenado-por-tests
```

### Paso 4 — consolidar

La sesión principal arma una tabla en el chat, una fila por repo: resueltas, pendientes por
severidad, imagen base, secretos, estado de la validación. Sin archivo de informe.

Las dudas de **todos** los repos se juntan en **una sola ronda** con `AskUserQuestion`. Un
secreto se nombra por archivo, línea y tipo; el valor no se imprime.

### Paso 5 — diff

Por cada repo con cambios, `mostrar-diff --repo .worktrees/vacuna-AAAA-MM-DD/<repo> --base
<rama base>`, en background, y la URL al chat. Los repos sin cambios se nombran y listo.

### Paso 6 — envío (gateado)

Solo con el OK explícito del usuario en el chat, `enviar-review` por repo, en paralelo:

- Commit firmado con el `git config` del repo. Nunca atribución a la IA.
- `Maniphest Tasks: T#####` solo si el usuario lo pasa en ese momento; si no, el campo se
  omite entero.
- Reviewers los decide el usuario; no se inventan.
- Un error de `arc`, un conflicto o un prompt interactivo **frena ese repo** y queda para el
  usuario. Los demás siguen.

### Paso 7 — limpieza

Los worktrees sin cambios se borran (`git worktree remove`) junto con su branch. Los que
quedaron con un diff enviado se dejan: el land es del usuario.

## Errores y hard stops

| Situación | Qué hace |
|-----------|----------|
| Docker no disponible | Hard stop global, antes de tocar nada |
| Trivy no puede bajar la DB (sin red) | Frena el scan de ese repo y lo reporta; no sigue a ciegas con datos viejos |
| Canónico con cambios sin commitear | Frena ese repo (paso 1) |
| Sin `package-lock.json` | No corre audit fix; lo reporta |
| Sin `FROM node:` | Fuera de alcance automático; lo reporta |
| `engines.node` o `.nvmrc` contra el Dockerfile | Duda, no decisión del script |
| Tests rojos después del fix | Revalida con el lock original: si ya estaba rojo, mantiene el fix y lo dice; si lo rompió el fix, revierte el lock y el hallazgo pasa a pendiente |
| `npm ci` falla en las dos corridas | El repo se reporta como no validable y el fix se revierte: sin validación no se entrega un lock nuevo |

## Tests del plugin

`tests/test_vacunas.py`, unittest, sin Docker (los comandos se arman y se comparan como
strings):

- Detección de la versión de node: multi-stage, `Dockerfile.test` por sobre `.prod`,
  `FROM node:20` sin sufijo, ausencia de `FROM node:`, y `cypress/base:16`.
- Conflicto entre `engines.node` / `.nvmrc` y el `FROM` → nota de duda.
- Normalización del JSON de `npm audit` (formato v7+) a conteos y hallazgos.
- Normalización del JSON de trivy (fs, image, secret), con el valor del secreto descartado.
- El comando de `audit fix` nunca incluye `--force`, y siempre incluye `--package-lock-only`
  y `--user`.
- Detección de repos Node sobre un árbol de prueba.

## Fuera de alcance de esta versión

- `trivy config` (misconfig de Dockerfile).
- Construir la imagen del repo para escanearla.
- Bump de la imagen base, `overrides`, o reemplazo de dependencias: son dudas, y si el
  usuario decide avanzar, van por un ticket con su propio flujo.
- Repos PHP (Composer) y el legacy `webadmin`.
