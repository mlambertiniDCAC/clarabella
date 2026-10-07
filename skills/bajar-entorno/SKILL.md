---
name: bajar-entorno
description: Usar como último paso de un ticket del workspace dcac-ia-context para APAGAR lo que el ticket dejó prendido — contenedores T#####-*, sus volúmenes, la DB del ticket, el preview de mostrar-diff y los datos de prueba (DB/Keycloak/Redis) — cuando el trabajo ya se envió a review y el entorno solo está consumiendo memoria. Triggers — "bajá el contenedor y cerramos", "apagá todo lo del ticket", "limpiá el entorno de T#####", "no quiero que consuma recursos al dope". Solo toca recursos del propio ticket: NO baja ni recrea infra compartida (Keycloak, Redis, ms-*, db-* de desarrollo) ni el worktree/branch mientras la Differential esté en review.
---

# Bajar el entorno del ticket

Cierra el ciclo que abrió `aislar-ticket`: apaga **lo que es del ticket y nada más**, para
que un ticket ya enviado a review no siga ocupando memoria de la VM de Docker (que es
chica: varios servicios juntos se tumban entre sí por OOM).

Es el paso 9 de `resolver-ticket`, después de `enviar-review`. También sirve standalone
cuando un ticket queda abandonado o pausado por mucho tiempo.

## Gate — el usuario lo pide o lo aprueba

Bajar el entorno **destruye el estado de prueba** (DB del ticket, datos sembrados en
Keycloak/Redis): si después hace falta re-verificar algo, hay que volver a armarlo.
Corré esta skill solo cuando el usuario lo pidió explícitamente ("bajá todo", "cerramos")
o aprobó la propuesta. No la encadenes sola después de `enviar-review`.

## Paso 1 — Verificar que no se pierde trabajo

Antes de apagar nada:

1. **Código commiteado:** `git -C .worktrees/T#####-{slug}/<ms> status --porcelain` vacío y
   la branch `T#####` con el commit del ticket (`git log --oneline -1`). Bajar el
   contenedor no borra el worktree, pero si hay cambios sin commitear conviene saberlo
   antes de perder el entorno donde se probaban.
2. **Review enviada:** existe la Differential (`D####`) o el PR del ticket. Si no se envió
   todavía, **preguntá** — quizá falta re-testear algo.
3. **Resultados documentados:** el `resultados-test.md` del ticket ya tiene la evidencia.
   Una vez bajado el entorno no se puede volver a sacar.

Si algo de esto no cierra → **frená y avisá**, no sigas.

## Paso 2 — Limpiar los datos de prueba (con el entorno todavía arriba)

Esto va **antes** de bajar los contenedores, porque necesita acceso a las bases y APIs.
Seguí el bloque "Teardown" del `tests.md` del ticket, que ya dice qué filas se crearon y
en qué orden borrarlas.

- **DB del ticket** (`T#####-db`, copia descartable): si se va a borrar entera en el paso 4,
  no hace falta limpiarla fila por fila.
- **DB compartida y persistente** (la de otro servicio que el ticket usó): solo `DELETE`
  puntuales de las filas del ticket, filtrando por su prefijo de datos de prueba, en orden
  de dependencia (hijas → padres). **Nunca** `down -v` ni recrear el contenedor.
- **Keycloak / otros servicios de identidad:** borrar por API los usuarios de prueba
  (`t#####-*`). Ojo con los `DELETE` de colecciones: un body vacío puede interpretarse como
  "todos" en vez de "ninguno".
- **Redis:** borrar solo las claves del prefijo del ticket
  (`--scan --pattern '<PREFIJO_DEL_TICKET>*'`), nunca `FLUSHDB`.

Verificá con un `SELECT count(*)` / `--scan | wc -l` que quedó en cero, y anotá en
`resultados-test.md` lo que se borró (cuenta por tabla). Si un `DELETE` falla por un nombre
de columna, la transacción entera puede abortar: releé el error y corregí antes de dar por
limpio el teardown.

## Paso 3 — Bajar el preview de `mostrar-diff`

El servidor del paso 4/6 de `resolver-ticket` queda corriendo en background y suele
haber uno por ticket. Bajá **solo el de este ticket**:

```bash
pkill -f "serve.py --repo .worktrees/T#####" || true
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:<puerto>   # 000 = está abajo
```

**Ojo con `pkill`:** un patrón amplio también matchea el propio shell que lo ejecuta (y te
corta el comando con un exit raro, tipo 144). Incluí el `T#####` en el patrón, mandalo
solo (no encadenado con lo que venga después) y confirmá con el `curl`. Si hay previews de
otros tickets corriendo, **tienen que seguir vivos**: verificá con
`ps -ef | grep serve.py` que solo desapareció el tuyo.

## Paso 4 — Bajar contenedores, volúmenes y DB del ticket

```bash
docker rm -f T#####-<ms> T#####-db
docker volume rm T#####-<volumen>          # p.ej. el de node_modules
```

Reglas:

- Solo nombres que empiecen con `T#####-`. Si un `docker rm` te devuelve un nombre que no
  tiene el prefijo del ticket, **algo está mal**: frená.
- El volumen se borra solo si es del ticket (lo creó `aislar-ticket`). Un volumen compartido
  no se toca.
- Si el ticket levantó algo más (un ms de dependencia propio del ticket, un Mongo, etc.),
  entra en la misma lista; lo que **no** levantó el ticket, no.

## Paso 5 — Qué NO se baja

| Recurso | Por qué queda |
|---|---|
| Infra compartida: Keycloak, Redis, `ms-*` y `db-*` de desarrollo | Son de todo el equipo; bajarlas o recrearlas puede borrar datos ajenos |
| Contenedores y previews de **otros** tickets | Trabajo en curso de otra tarea |
| El worktree `.worktrees/T#####-{slug}/<ms>` | La review puede pedir cambios; se remueve cuando la Differential aterriza |
| La branch `T#####` | Idem: vive hasta el land |
| El clon canónico `microservicios/<ms>` | Siempre en `master`, nunca se toca |

Si un contenedor compartido está caído (OOM, por ejemplo), la única acción válida es
`docker start` — no `docker compose down`/`up`.

## Paso 6 — Cerrar el worktree (recién cuando la review aterriza)

Esto **no** es parte del cierre del día: es un paso posterior, cuando el usuario avisa que
la Differential/PR ya está mergeado.

```bash
git -C microservicios/<ms> worktree remove .worktrees/T#####-{slug}/<ms>
git -C microservicios/<ms> branch -d T#####     # -D si el ticket se descartó
```

**Nunca** `rm -rf` de la carpeta del worktree: deja metadata huérfana en `.git/worktrees/`
(si ya pasó, `git worktree prune`).

## Paso 7 — Reportar

Un cierre corto, en texto, sin adornos: qué se bajó (contenedores, volúmenes, preview),
qué datos de prueba se limpiaron y dónde, qué quedó arriba **y por qué** (infra compartida,
previews de otros tickets), y qué se conserva a propósito (worktree + branch + la
Differential en review). Si quedó algún pendiente (un ticket nuevo sugerido, un dato que no
se pudo borrar), nombralo.

Si el ticket tiene `cronica.md`, agregá en su Tapa que el entorno ya está bajado, para que
el que retome el ticket lo sepa.

## Errores comunes

- **Bajar el entorno antes de enviar la review** → si el reviewer pide una verificación, hay
  que rearmar todo. Enviá primero.
- **`docker compose down` en vez de `docker rm -f` del contenedor del ticket** → el compose
  puede arrastrar servicios compartidos del mismo proyecto.
- **Recrear una DB ajena para "arreglar" un error del teardown** → prohibido; un error en un
  `DELETE` se corrige leyendo el error, no recreando el contenedor.
- **`FLUSHDB` o borrar usuarios "de prueba" sin filtrar por el prefijo del ticket** → se
  lleva datos de otros tickets que comparten el mismo Redis/realm.
- **`pkill -f serve.py` sin el `T#####`** → mata los previews de los demás tickets (y el
  propio shell).
- **Borrar el worktree/branch el mismo día que se envía la review** → todavía puede haber
  cambios pedidos; eso es el paso 6, después del land.
- **Dar por limpio un teardown sin verificar** → siempre un conteo final en cero.
