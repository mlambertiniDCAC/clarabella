---
name: preparar-repo
description: Usar cuando ya se identificaron los repositorios a tocar para un ticket del workspace dcac-ia-context y hay que dejarlos listos para trabajar ANTES de analizar/implementar — switch a master, pull, y aislar la branch del ticket en su propio worktree/lane (nunca directo en el canónico). Es una skill especial de setup, invocada por el motor pipeline-desarrollo (antes de Fase 2 y Fase 4) y por el flujo manual resolver-ticket. Triggers — "prepará el repo para T#####", "dejá los repos listos para trabajar", "switch a master y branch de T#####". NO commitea nada.
---

# Preparar repositorio

Deja cada repo identificado **listo para trabajar** antes de analizar o implementar un
ticket: rama de integración actualizada + branch del ticket. Se corre **una vez por cada
repo** donde el ticket necesita cambios (puede ser más de uno: p.ej. un ms + `apigateway`).

**Recordá la estructura del workspace:** cada carpeta de `microservicios/` (y
`webadmin/webadmin/`) es **su propio repo git**. Operá dentro de cada uno (`git -C
microservicios/<ms> ...` o `cd` a la carpeta). El repo del root (infra/contexto) NO se toca.

## Los 5 pasos (por repo)

Para cada repositorio identificado, en orden:

### 1. Switch a master (con guardia de cambios sin commitear)
- **Antes de cambiar de rama, verificá que no haya cambios sin commitear**
  (`git -C <repo> status --porcelain`).
- **Si hay algo sin commitear → FRENÁ TODO y notificá al usuario en qué repositorio pasa.**
  No hagas stash, ni descartes, ni cambies de rama: el trabajo sin guardar es del usuario.
  Esto es un **hard stop** (DUDA bloqueante).
- Si el working tree está limpio → `git -C <repo> switch master`.
- Si `master` **no existe** en ese repo → frená y avisá (no asumas `main` u otra rama).

### 2. Pull de los últimos cambios
`git -C <repo> pull` (fast-forward de `master`). Si el pull falla (conflicto, red, auth)
→ frená y reportá el repo y el error.

### 3. Análisis sobre los últimos cambios
Recién ahora, con el código **actualizado**, se hace el análisis (entender el código,
patrones, archivos a tocar). El objetivo de este paso es que la planificación/implementación
se haga **sobre la última versión de master**, nunca sobre código viejo. En el pipeline,
este paso lo consume Fase 2 (`planear-ticket`) leyendo el código ya actualizado.

### 4. Crear la branch del ticket — **delegado, nunca directo en el canónico**

**El canónico (`microservicios/<ms>`) nunca se queda en branch `T#####`.** Los pasos 1-3
lo dejan en `master` actualizado y ahí se queda — solo lectura. La branch del ticket y
todas las escrituras (implementación) pasan a vivir en un entorno aislado propio, según el
modo en que estés corriendo:

- **Modo manual** (`resolver-ticket`, standalone): invocá `aislar-ticket`
  con el ticket y este repo. Crea un `git worktree` en branch `T#####` + un contenedor
  Docker propio que lo monta (bind mount). Es reanudable: si el worktree ya existe, lo
  reusa.
- **Modo motor** (`pipeline-desarrollo`): invocá `entorno-ticket`. Clona el canónico
  (`git clone --shared`) en su propia lane (`.pipeline-lanes/T#####-{slug}/<ms>`), en branch
  `T#####`, con contenedor y DB propios.

Las dos son válidas y NO se mezclan entre sí (una usa worktree, la otra clone --shared) —
elegí según el flujo que esté corriendo esta skill, nunca ambas a la vez sobre el mismo
repo/ticket.

**Por qué no `git -C <repo> switch -c T##### master` directo en el canónico:** si dos
tickets independientes tocan el mismo repo, el segundo `switch` pisa la branch del primero
en la misma working directory — la colisión que este cambio de diseño existe para eliminar.

### 5. NO commitear (por ahora)
**De momento NO se commitean los cambios** — el usuario lo hace a mano. Nunca `git add`,
`git commit`, `git push`, ni crear PRs. El trabajo queda en el working tree del worktree o
la lane del ticket (según el modo), nunca en el canónico. (Esto se irá extendiendo de a
poco más adelante.)

## Dónde encaja

- Corre **después de identificar los repos** y **antes** de analizar/implementar (Fase 0/1
  → Fase 2 en el motor; primer paso de `resolver-ticket` en modo manual).
- Los pasos 1-3 dejan el canónico listo para **planificar** (lectura, siempre en master).
- El paso 4 deja el ticket listo para **implementar**: el código aterriza en `T#####`,
  aislado en worktree+contenedor (manual) o lane+contenedor (motor) — nunca en el canónico.
- Si se tocan varios repos, se repite el ciclo completo en cada uno. Un solo repo con
  cambios sin commitear frena **todo** el proceso (paso 1).

## Salida (modo orquestado)

Cuando la invoca el motor, devolvé:

```
ARTEFACTO: repos preparados → [<repo>: en branch T#####, master actualizado]
DUDAS:
  - [D1] <ej. "microservicios/ms-ofertas tiene cambios sin commitear"> · hard stop
SUGERENCIAS: (ninguna habitualmente)
ESTADO: completo | frenado-por-duda
```

`frenado-por-duda` si algún repo tiene cambios sin commitear, no existe, `master` no está,
o el pull falla.

## Errores comunes

- **Cambiar de rama con trabajo sin commitear** → jamás; frená y avisá qué repo (paso 1).
- **Hacer stash/reset para "destrabar"** → no; el trabajo sin guardar es del usuario.
- **Analizar antes de pullear** → el análisis va sobre master actualizado (pasos 2→3).
- **Nombrar la branch distinto al ticket** → la branch es `T#####`, apuntando a master.
- **Commitear/pushear** → no; por ahora es manual (paso 5).
- **Operar en el repo del root** → no; se trabaja dentro de cada repo de `microservicios/`.
- **Asumir `main` si no hay `master`** → no; frená y avisá.
- **Hacer `switch -c T##### master` directo en el canónico** → esto es lo que causa que dos
  tickets independientes se pisen en el mismo repo. El paso 4 siempre delega en
  `aislar-ticket` (manual) o `entorno-ticket` (motor); el canónico se queda en master.
- **Mezclar los dos modos sobre el mismo repo/ticket** → si ya hay un worktree de
  `aislar-ticket` para `T#####`, no crear además una lane de `entorno-ticket` (o
  viceversa): un ticket usa un solo modo de aislamiento por corrida.
