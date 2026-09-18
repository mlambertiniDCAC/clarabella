---
name: aislar-ticket
description: Usar para aislar un ticket de desarrollo del workspace dcac-ia-context en su propio git worktree + contenedor Docker, en el flujo MANUAL (resolver-ticket) — evita que dos tickets independientes que tocan el mismo repo se pisen entre sí. Triggers — "aislá T##### en su propio worktree", "levantá un entorno seguro para T#####", "evitá que T##### choque con otro ticket que estoy laburando". Standalone: no depende del dashboard ni de pipeline-desarrollo. NO usar en modo motor (ahí es entorno-ticket, que usa clone --shared en vez de worktree).
---

# Entorno seguro por ticket (worktree + Docker)

Aísla un ticket en el flujo manual: **un `git worktree` propio + un contenedor Docker que
monta ese worktree**, por cada repo que el ticket toca. La invoca `preparar-repo`
(modo manual) después de dejar el clon canónico en `master` actualizado — nunca la corras
antes de eso.

## Por qué worktree (no `clone --shared`, no branch directo en el canónico)

- **Git impide checkear la misma branch en dos worktrees a la vez** — la colisión entre
  tickets independientes queda prevenida por diseño, no por disciplina.
- **El canónico nunca cambia de branch.** Se queda siempre en `master`, de solo lectura;
  el worktree es quien vive en `T#####`. Así podés tener N tickets sobre el mismo repo sin
  que ninguno le pise la rama a otro.
- **Comparte objetos con el canónico** (a diferencia de un `clone`): liviano en disco, y
  como es literalmente el mismo repositorio, **no hace falta ningún sync-out/push** — la
  branch `T#####` ya es visible desde el canónico apenas se crea.

## Convención de directorios

`.worktrees/T#####-{slug}/<ms>` en la raíz del workspace — carpeta propia, sin relación con
`.pipeline-lanes/` (eso es del motor `pipeline-desarrollo`, no lo toques ni lo reuses acá).

## Provisionar (por cada repo que el ticket toca)

1. **Precondición:** el clon canónico (`microservicios/<ms>`) debe estar limpio y en
   `master` actualizado (lo deja así `preparar-repo`, pasos 1-3). Si no lo está,
   **frená y avisá** — no lo arregles vos acá.
2. **Crear el worktree:**
   ```bash
   git -C microservicios/<ms> worktree add ../../.worktrees/T#####-{slug}/<ms> -b T##### master
   ```
   **Reanudable:** si la branch `T#####` ya existe (ticket retomado), agregá el worktree
   sin `-b`: `git -C microservicios/<ms> worktree add ../../.worktrees/T#####-{slug}/<ms> T#####`.
   Si el worktree ya existe también, no falles: seguí.
3. **Copiar config no trackeada si falta:** si `.arcconfig` u otro archivo de credenciales
   está gitignoreado (no viaja con el checkout), copialo del canónico al worktree — sin
   esto, `enviar-review` no va a poder correr `arc diff` desde el worktree.
4. **Levantar el contenedor `T#####-<ms>`** a partir del `docker-compose.yml`/`Dockerfile`
   propio del servicio (ver `dcac-context/back/docker.md`), con un **bind mount** del
   worktree del paso 2 en el path de código de la imagen. **Bind mount, no copia:** el
   código se edita en el worktree del host (o desde dentro del contenedor, da igual) y
   se refleja al instante en el otro lado, sin rebuild de imagen.
5. **Levantar `T#####-db`** (copia del schema/datos de test) y apuntar el `.env` del
   contenedor a esa DB, en un puerto propio del ticket.
6. Si el ticket trae migración (`crear-migracion`), aplicarla contra **`T#####-db`**, nunca
   contra la DB compartida.

Los comandos exactos de compose/Dockerfile salen del propio repo — no inventar, seguir el
que ya usa el servicio.

## Teardown

- `docker rm -f T#####-*` + `docker volume rm` de los volúmenes de este ticket + drop de
  `T#####-db`.
- `git -C microservicios/<ms> worktree remove .worktrees/T#####-{slug}/<ms>` — **nunca**
  borres la carpeta a mano (`rm -rf`) sin este comando: deja metadata húmeda en
  `.git/worktrees/` que confunde a git después (`git worktree prune` la limpia si ya pasó).
- Si el ticket se cancela por completo (no solo una pausa): además
  `git -C microservicios/<ms> branch -D T#####`.

## Reglas duras

- **El canónico nunca cambia de branch para trabajar un ticket.** Si necesitás mirar el
  código en `T#####`, andá al worktree — no hagas `switch` en `microservicios/<ms>`.
- **Un worktree por ticket por repo.** Si el ticket toca 2 repos, repetí el ciclo en cada
  uno (cada worktree vive dentro de su propio repo git).
- **No mezclar con `.pipeline-lanes/` ni con conceptos del motor** (fases, dashboard,
  `estado.json`). Esta skill es standalone; si estás corriendo `pipeline-desarrollo`, la
  skill que corresponde es `entorno-ticket`, no esta.

## Errores comunes

- **Borrar la carpeta del worktree con `rm -rf` en vez de `git worktree remove`** → deja
  entradas fantasma en `.git/worktrees/`; corré `git worktree prune` para limpiarlas.
- **Hacer `switch`/`checkout` de `T#####` en el clon canónico "para revisar algo rápido"**
  → git lo va a rechazar si el worktree ya tiene esa branch (protección por diseño) — y si
  de casualidad no la rechaza (branch distinta), rompe la garantía de "canónico = solo
  master". Usá el worktree.
- **Copiar el código al contenedor en vez de bind-mount** → pierde el sentido: cualquier
  edición necesitaría rebuild para verse reflejada.
- **Confundir esto con `entorno-ticket`** → esa es la versión del motor (`clone --shared`,
  lanes, dashboard). Esta es la standalone para el flujo manual (`resolver-ticket`).
- **Correr esto antes de que el canónico esté en master actualizado** → el worktree partiría
  de una base vieja; siempre después de los pasos 1-3 de `preparar-repo`.
