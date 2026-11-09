---
name: vacunar-repos
description: Usar cuando hay que buscar y arreglar vulnerabilidades de dependencias en los repos Node del workspace dcac-ia-context — scan con npm audit y trivy en la versión de node que declara cada Dockerfile, fix seguro, validación con los tests del repo y diff por repo. Triggers — "vacuná los repos", "buscá vulnerabilidades en los repos node", "el prediff está rojo por npm audit", "pasá trivy por los microservicios". NO usar para repos PHP, ni para vulnerabilidades de código propio (SAST).
---

# Vacunar repos

Escanea vulnerabilidades en los repos **Node** del workspace, aplica **solo el fix seguro**,
lo valida con los tests del repo, y deja el diff listo para que el usuario decida el envío.

El objetivo concreto: que el prediff de Jenkins (`isolated-npm-unittest`, que corta con
`npm audit` HIGH o CRITICAL incluyendo devDependencies) no sea el lugar donde se descubre una
vulnerabilidad.

## Lo que esta skill NO hace

Nada de esto se decide acá: son **dudas** para el usuario.

- `npm audit fix --force` o cualquier bump breaking.
- Cambiar la versión de node, el `FROM`, o la imagen base.
- `overrides` / `resolutions` en `package.json`.
- `.trivyignore`, `npm audit --omit=dev`, o silenciar un hallazgo de cualquier forma.
- Tocar código de producción.

Tampoco entra misconfig de Dockerfile (`trivy config`), SAST, ni repos PHP.

## Antes de arrancar

- **Docker tiene que estar corriendo.** Si no, hard stop: todo (node y trivy) va en
  contenedores efímeros, no hay nada instalado en el host.
- La primera corrida baja la DB de trivy al volumen `clarabella-trivy-cache`. Tarda; después
  se reusa.

## Paso 0 — alcance

Si el usuario nombró repos, son esos. Si dijo "todos":

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vacunas.py --detectar --raiz microservicios
```

Imprime una línea por repo con veredicto y motivo (`ms-psp dentro`,
`api-testing-end2end fuera sin-FROM-node`, `ms-permisos fuera sin-package-lock`).
**Reportale al usuario esa salida tal cual** — los que quedan afuera y por qué no se
adivinan ni se nombran de memoria: salen de la corrida.

## Paso 1 — preparar (por repo, en paralelo)

1. `git -C microservicios/<repo> status --porcelain`. Con cambios sin commitear → **frená
   ese repo** y avisá cuál. No hagas stash ni descartes: ese trabajo es del usuario.
2. Rama base al día en el canónico: `master`, salvo excepción conocida (`ms-psp` →
   `migracion-psp`). Si la base no está clara, preguntá; no asumas `main`.
3. Worktree propio de la corrida:
   `git -C microservicios/<repo> worktree add <path absoluto>/.worktrees/vacuna-AAAA-MM-DD/<repo> -b vacuna-AAAA-MM-DD <base>`.
   Es reanudable: si el worktree ya existe, reusalo sin tocarlo; si la branch existe pero el
   worktree no, el mismo comando **sin `-b`** la engancha (con `-b` falla).

El canónico se queda en su rama base, solo lectura. Que el worktree sea limpio es a
propósito: el scan de secretos ve solo contenido versionado, así que los `.env` locales no
pueden terminar en el informe.

## Paso 2 — scan (sin tokens)

Un repo por invocación, hasta **3 en paralelo** (la VM de Docker tiene ~3,6 GiB):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vacunas.py \
  --worktree .worktrees/vacuna-AAAA-MM-DD/<repo> --repo <repo> --base <base> \
  --out <scratchpad>/vacuna-AAAA-MM-DD
```

Escribe un JSON chico por repo. **No lo leas entero**: es el input del Veterinario.

Cada JSON trae `scan_incompleto` con las secciones que no se pudieron leer — `npm` incluido
(registry caído, repo sin lockfile) además de `trivy_lock`, `imagen_base` y `secretos`.
**Una sección en esa lista no es "sin vulnerabilidades"**: es un scan incompleto y se
reporta como tal, con el motivo que está en `notas`.

Un repo con `sin_lock: true` no tiene fix posible: va a la tabla del paso 4 como pendiente,
no se le despacha Veterinario para arreglar nada.

## Paso 3 — un Veterinario por repo

Despachá `clarabella:veterinario` en tandas de 3, uno por repo. A cada uno pasale: nombre
del repo, path del worktree, rama base, y el path de su JSON de scan. Devuelven el contrato
de su agente (ARTEFACTO / VALIDACIÓN / PENDIENTES / DUDAS / ESTADO).

## Paso 4 — consolidar en el chat

Una tabla, una fila por repo: resueltas por severidad, pendientes, imagen base, secretos,
estado de la validación. **Sin archivo de informe.**

Juntá las dudas de **todos** los repos y preguntá en **una sola ronda** con
`AskUserQuestion`. Un secreto se nombra por archivo, línea y tipo — el valor no se imprime
nunca.

## Paso 5 — diff

Por cada repo con cambios:

```bash
python3 -u ${CLAUDE_PLUGIN_ROOT}/skills/mostrar-diff/serve.py \
  --repo .worktrees/vacuna-AAAA-MM-DD/<repo> --base <base> --ticket vacuna-AAAA-MM-DD \
  > /tmp/diff-vacuna-<repo>.log 2>&1 &
disown
```

Pasale las URLs al usuario. Los repos sin cambios se nombran y listo.

## Paso 6 — envío (gateado)

**Solo con el OK explícito del usuario en el chat.** No lo infieras de que el diff esté
lindo.

Con el OK, invocá `clarabella:enviar-review` por repo, en paralelo. Particularidades de esta
corrida:

- La branch es `vacuna-AAAA-MM-DD`, no `T#####`, y el merge previo al `arc diff` es de
  **`<base>`** (la rama base de ese repo), no de `master` — en `ms-psp` mergear `master`
  sería incorrecto.
- Sin ticket no hay `borradores/arc-diff-<ms>.md` ni bloque de `template-pr.md`: el título
  es `Vulnerabilidades de dependencias en <repo> (npm audit fix)` y el Summary dice qué
  advisories bajaron, con qué comando, y cómo se validó. La línea `Ticket:` se omite.
- `Maniphest Tasks: T#####` solo si el usuario te pasa el ticket en ese momento; si no, el
  campo se omite entero.
- Reviewers los decide el usuario; no se inventan.
- Un error de `arc`, un conflicto o un prompt interactivo **frena ese repo** y queda para el
  usuario. Los demás siguen.

## Paso 7 — limpieza

Worktrees sin cambios: `git -C microservicios/<repo> worktree remove <path>` y borrar la
branch. Los que ya tienen diff enviado se dejan: el land es del usuario.

## Errores comunes

- **Tratar un scan con error de trivy como "sin vulnerabilidades"** → es incompleto, decilo.
- **Leer el JSON de scan completo en la sesión principal** → para eso está el Veterinario;
  acá solo se consolida su contrato.
- **Correr el fix en `microservicios/<repo>`** → va en el worktree; el canónico es lectura.
- **Asumir `master` en `ms-psp`** → su base es `migracion-psp`.
- **Dar por aprobado el envío porque los tests pasaron** → el gate es la palabra del usuario.
- **Despachar los 10 repos a la vez** → tandas de 3; la VM de Docker se queda sin memoria y
  se lleva puesta la DB compartida.
