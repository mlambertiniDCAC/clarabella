---
name: leer-db
description: Usar cuando hay que explorar o validar datos reales en una base MariaDB o PostgreSQL del ecosistema dcac en modo estrictamente de solo lectura — buscar sociedades/usuarios/operaciones candidatas para un caso de prueba, o verificar qué quedó insertado tras disparar un curl contra un endpoint. Triggers — "conectate a la DB en modo lectura", "buscame una sociedad que tenga...", "qué se insertó en <tabla>", "validá los datos de esta evaluación/reserva", "/leer-db". NO ejecuta ninguna escritura (INSERT/UPDATE/DELETE/DDL/OPTIMIZE/REPAIR) bajo ninguna circunstancia.
---

# leer-db

Explorar y validar datos reales en una MariaDB o PostgreSQL del ecosistema dcac, siempre en modo
de solo lectura, para armar casos de prueba (sociedades/usuarios/operaciones
candidatas) o confirmar qué efectivamente insertó/modificó un endpoint que el usuario
acaba de probar con un curl.

## Entornos: un archivo por entorno

Cada entorno es un archivo en
`${CLAUDE_PLUGIN_DATA}/leer-db/credenciales/<entorno>.cnf`: el directorio de datos
del plugin, fuera del repo. Cada dev tiene los suyos, sobreviven a las
actualizaciones del plugin y nunca se publican. El nombre del archivo es el nombre del entorno: agregar un
entorno nuevo es solo crear otro `.cnf`, sin tocar esta skill.

Se soportan dos motores, indicados en la metadata con `# motor:`:

| Motor | Formato del archivo | Plantilla |
|---|---|---|
| `mariadb` (default si falta el campo) | option file de MariaDB, sección `[client]` | `${CLAUDE_PLUGIN_ROOT}/skills/leer-db/plantillas/mariadb.cnf` |
| `postgres` | service file de libpq (`pg_service.conf`), sección `[lectura]` | `${CLAUDE_PLUGIN_ROOT}/skills/leer-db/plantillas/postgres.cnf` |

Las primeras líneas de cada archivo son comentarios con la metadata del entorno:

```ini
# motor: postgres
# descripcion: base de ms-psp en stage
# vpn: si
# datos-reales: si
[lectura]
host=...
```

Para leer esa metadata usar **solo** `grep '^#'` sobre el archivo. Nunca hacer
`cat`/`Read` del `.cnf` ni pasar la password por línea de comandos: el cliente la
toma directo del archivo (`--defaults-extra-file` en MariaDB, `PGSERVICEFILE` en
Postgres).

## Primer paso siempre: elegir el entorno

Antes de la primera query de la sesión:

1. Listar los entornos disponibles:
   ```bash
   for f in ${CLAUDE_PLUGIN_DATA}/leer-db/credenciales/*.cnf; do
     [ -e "$f" ] || continue
     echo "== $(basename "$f" .cnf)"; grep '^#' "$f"
   done
   ```
2. Si no hay ninguno, pedirle al usuario los datos para crear uno (ver "Agregar
   un entorno").
3. Preguntar con `AskUserQuestion` a cuál conectarse, una opción por entorno
   con su `descripcion`, y **siempre** como última opción "Agregar entorno
   nuevo" — nunca asumir uno por default, aunque haya uno solo. Si hay más de 3
   entornos, mostrar los 3 primeros + "Agregar entorno nuevo" y aclarar en la
   pregunta que los demás se eligen escribiendo su nombre.
   Si elige "Agregar entorno nuevo", o nombra un entorno que no tiene `.cnf`,
   pedirle los datos y crearlo (ver "Agregar un entorno"); una vez creado, usar
   ese entorno.
   Si algún entorno no tiene `descripcion`, ofrecerle al usuario completarla
   después de elegir (se agrega la línea `# descripcion:` sin tocar el resto
   del archivo).
4. Usar ese entorno en todas las queries de la sesión; no volver a preguntar
   salvo que el usuario pida cambiar.

Según la metadata del elegido:
- `vpn: si` → si la query falla con timeout/conexión rechazada, recordarle al
  usuario confirmar que la VPN esté conectada antes de asumir que las
  credenciales están mal.
- `datos-reales: si` (o si falta el campo) → tratarlo como datos reales: extremar
  el cuidado de la regla de solo lectura y no copiar datos personales a docs.

## Agregar un entorno

El agente crea el archivo. Pedirle al usuario los datos que falten, en un solo
mensaje:

- nombre del entorno (será el nombre del archivo: minúsculas, sin espacios)
- motor: `mariadb` o `postgres` (si no lo dice, inferirlo del puerto —
  3306 → mariadb, 5432 → postgres — y confirmarlo en la misma respuesta, sin
  frenar el flujo)
- descripción corta
- si requiere VPN (si/no)
- si tiene datos reales (si/no)
- `host`, `port`, `user`, `password`, y para postgres también la base (`dbname`)

Si el usuario ya pasó parte de los datos, pedir solo lo que falte. Si falta
solo la metadata (descripción, VPN, datos reales), crear el archivo igual con
lo que haya — `datos-reales: si` por default — y ofrecer completarla después.

Recomendarle que use un usuario de DB con permisos solo de `SELECT` si lo tiene.

Con los datos, crear el directorio si no existe (`mkdir -p ${CLAUDE_PLUGIN_DATA}/leer-db/credenciales && chmod 700 ${CLAUDE_PLUGIN_DATA}/leer-db/credenciales`),
escribir `${CLAUDE_PLUGIN_DATA}/leer-db/credenciales/<entorno>.cnf` con
el formato de la plantilla de su motor y dejarlo con `chmod 600`. Si ya existe
un archivo con ese nombre, preguntar antes de pisarlo.

Después de escribirlo:
- No repetir la password en ninguna respuesta, resumen ni doc.
- No volver a leer el archivo (solo `grep '^#'` para la metadata).
- Probar la conexión con `SELECT 1` (ver "Regla dura") y confirmarle al usuario
  que el entorno quedó listo, o mostrarle el error si falla.

Para modificar un entorno (cambió la password, el host, etc.), el usuario pasa
los datos nuevos y el agente reescribe el archivo completo con la misma
plantilla.

## De una pregunta de negocio a la query

Cuando el usuario pide algo en términos de negocio ("quiero ver la última compra
inmediata de tal sociedad", "buscá la reserva de este CUIT") en vez de nombrar
tablas/columnas, encadenar así antes de escribir SQL:

1. **Identificar el dominio o proyecto** del término (ver
   `dcac-context/context/business/glossary.md` para vocabulario de negocio; si el
   término suena a una iniciativa conocida (ver `relations/proyectos/README.md`), es
   más específico ir directo a `relations/proyectos/<proyecto>.md`).
2. **Ubicar las tablas candidatas** en `relations/<dominio>.md` o
   `relations/proyectos/<proyecto>.md` (ver sección siguiente) — ya traen
   ownership y relaciones armadas, no hace falta re-descubrirlas a ciegas.
3. **Confirmar la estructura real** de esas tablas con `DESCRIBE`/
   `information_schema` (el doc puede haber quedado desactualizado respecto a la
   DB viva).
4. **Armar el filtro** solo con datos concretos que el usuario haya dado (ID,
   sociedad, CUIT, fecha) — nunca completar un WHERE con un valor supuesto.
5. Si el término no mapea a ningún dominio/proyecto documentado, seguir con
   `SHOW TABLES`/`information_schema` como fallback (sección siguiente) y avisar
   que es zona no mapeada — no lo pases por alto en silencio.

## Regla dura: solo lectura, sin excepciones

Solo se permiten sentencias que empiecen con `SELECT`, `SHOW`, `DESCRIBE`/`DESC`
o `EXPLAIN`, una por ejecución (sin `;` encadenados). Antes de correr cualquier
query, revisarla: si contiene `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`,
`ALTER`, `TRUNCATE`, `REPLACE`, `GRANT`, `REVOKE`, `LOCK`, `OPTIMIZE`, `REPAIR`,
`SET`, `CALL`, `LOAD`, `INTO OUTFILE`/`INTO DUMPFILE` o `LOAD_FILE`, no se
ejecuta. `SHOW CREATE TABLE` es lectura y está permitido.

En `postgres` se permiten `SELECT`, `WITH ... SELECT`, `EXPLAIN` (sin `ANALYZE`)
y `SHOW`; no existen `DESCRIBE` ni `SHOW TABLES`: la estructura se consulta en
`information_schema.tables`/`information_schema.columns`.

Para `postgres` también están prohibidos `COPY`, `DO`, `BEGIN`/`START
TRANSACTION`, `RESET`, `VACUUM`, `CLUSTER`, `REINDEX`, `REFRESH`, `NOTIFY`,
`LISTEN`, `nextval`/`setval`, `pg_read_file`/`pg_read_binary_file`/`pg_ls_dir`,
`lo_import`/`lo_export`, `dblink` y los meta-comandos de `psql` (`\...`).

Ejecutar según el `motor` del entorno. En ambos
casos la barrera de solo lectura a nivel de motor es obligatoria: nunca sacarla,
aunque la query parezca inofensiva.

### MariaDB

```bash
mariadb --defaults-extra-file=${CLAUDE_PLUGIN_DATA}/leer-db/credenciales/<entorno>.cnf \
  --init-command="SET SESSION TRANSACTION READ ONLY" \
  --table -e "<query aquí>"
```

- `--defaults-extra-file` tiene que ser la primera opción (si no, el cliente la ignora).
- Si no está `mariadb`, usar `mysql` con las mismas opciones.

### Postgres

Si `psql` está instalado en el host:

```bash
PGSERVICEFILE=${CLAUDE_PLUGIN_DATA}/leer-db/credenciales/<entorno>.cnf PGSERVICE=lectura \
PGOPTIONS='-c default_transaction_read_only=on' \
psql -X -v ON_ERROR_STOP=1 -c "<query aquí>"
```

Si no, correrlo en un contenedor efímero (no instalar nada en el host):

```bash
docker run --rm \
  -v "${CLAUDE_PLUGIN_DATA}/leer-db/credenciales/<entorno>.cnf:/svc.conf:ro" \
  -e PGSERVICEFILE=/svc.conf -e PGSERVICE=lectura \
  -e PGOPTIONS='-c default_transaction_read_only=on' \
  postgres:16-alpine psql -X -v ON_ERROR_STOP=1 -c "<query aquí>"
```

- Usar una imagen `postgres` que ya esté descargada (`docker image ls postgres`);
  si no hay ninguna, avisar al usuario antes de hacer `pull`.
- Dentro del contenedor, `127.0.0.1`/`localhost` es el contenedor, no el host:
  para una base local usar `host=host.docker.internal` en el archivo.
- Hosts remotos (cluster por VPN) salen por la red del host sin configuración extra.

### En ambos motores

- Si no hay ningún cliente disponible (ni en el host ni vía Docker), avisar al
  usuario en vez de instalar nada.
- El `<entorno>` del path tiene que coincidir siempre con el entorno que
  eligió el usuario; no hay default.
- Si la conexión falla con un error de acceso (`Access denied`,
  `password authentication failed`), avisar al usuario que revise las
  credenciales; no intentar otras.

`OPTIMIZE`/`REPAIR` "suenan" a mantenimiento inofensivo pero reescriben la tabla
físicamente — son escritura igual que cualquier otra.

| Excusa | Realidad |
|---|---|
| "Es solo para ver el schema" | Usá `DESCRIBE`/`information_schema`, nunca necesitás escribir para ver estructura |
| "El caso de prueba necesita que la fila exista" | Eso lo crea el endpoint bajo prueba, no vos — si falta, avisá y esperá a que se dispare el curl correspondiente |
| "OPTIMIZE no cambia los datos" | Reescribe la tabla en disco — no es solo-lectura |
| "Total, es un ambiente de prueba" | La regla la puso el usuario explícitamente; no se negocia por el ambiente |

## Método: nunca asumas un nombre de tabla o columna

Antes de escribir la query real, confirmá que existe:
```sql
SHOW TABLES FROM <db> LIKE '%palabra%';
SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS
WHERE COLUMN_NAME LIKE '%palabra%' AND TABLE_SCHEMA IN ('dcac','negocios','financiero');
```
Un término de negocio ("tag habilitado X", "operación pendiente") casi nunca mapea
1:1 a una columna con ese nombre exacto. Si tras explorar sigue sin haber una
columna clara, **parar y preguntarle al usuario con AskUserQuestion** en vez de
inventar un criterio de filtro solo para tener algo que mostrar.

Antes de explorar a ciegas una tabla de `dcac`/`negocios`/`mobile`/`estadisticas`,
revisar si ya está documentada en `dcac-context/context/data/database/README.md`
(ahorra los pasos de descubrimiento). Las tablas de `financiero` (módulo dCP,
acceso restringido) **no** tienen ni deben tener esa documentación en
`dcac-context/` — explorarlas siempre con `DESCRIBE`/`information_schema` en el
momento, sin persistir su schema en ningún doc de este repo.

Si el trabajo es sobre un ticket puntual (ej. T#####), revisar primero su
`resumen.md`/`plan.md` en `docs/{proyecto}/desarrollo/T#####-.../` si existe — da
el contrato real (paths, campos esperados) antes de tocar la DB.

## Antes de escribir un JOIN: consultar el índice de relaciones

`microservicios/db/schemas/relations/` documenta cómo se relacionan las tablas de los
3 schemas (`dcac`, `negocios`, `financiero`) — no hay FKs declaradas en las migraciones
(convención del equipo), así que estas relaciones están inferidas y, en su mayoría,
**verificadas contra el código real** de cada microservicio (no son solo suposición por
nombre de columna). Dos vistas complementarias, empezar siempre por el `README.md` de
cada una para ubicarse:

- `relations/<dominio>.md` (14 archivos, ver `relations/README.md`) — vista por dominio
  técnico (`usuarios-sociedades`, `financiero-dcp`, `compliance-kyc`, `liquidaciones`,
  etc.). Usar cuando la pregunta es "¿cómo se relaciona la tabla X con la Y?" en
  general, sin importar de qué iniciativa vino el dato.
- `relations/proyectos/<proyecto>.md` (ver `relations/proyectos/README.md`) — vista por
  proyecto/iniciativa real (la lista está en ese README).
  Usar cuando la pregunta es "¿qué tablas toca el proyecto X?" o para entender un
  "truco" propio de una iniciativa (ej. una tabla que un proyecto reutiliza de otro).

Cada archivo indica explícitamente qué microservicio es dueño real de cada tabla
(confirmado por repositorio/entity en código, no por convención de nombre) y marca
como "sin owner confirmado" las tablas legacy huérfanas — no asumir que una tabla
pertenece al microservicio "obvio" por el nombre sin chequear ahí primero: varias
veces el dueño real resultó ser otro servicio, o directamente legacy (`webadmin`).

**Si la relación que necesitás no está en el índice, o está marcada como
ambigua/"sin verificar"/"no confirmada" (ej. `revisacion` vs `negocio` en tablas de
cierre, claves polimórficas tipo `lote_nro`+`lote_tipo`), no la completes por tu
cuenta con el join que "parece" correcto.** Mostrale al usuario las opciones
candidatas (con `AskUserQuestion` si hay 2-3 caminos posibles, o directamente
preguntando si es una sola duda puntual) y esperá su confirmación antes de correr
la query — un JOIN mal inferido en modo lectura no rompe nada, pero sí puede hacer
que reportes un dato incorrecto como si fuera un hecho verificado.

## Patrón: sociedad → usuario activo

```sql
SELECT r.sociedad, u.usuario AS usuario_id, us.nombre, us.apellido, us.mail,
       us.deshabilitado, r.cargo_id, r.nivel
FROM dcac.rel_usuarios_sociedades r
LEFT JOIN dcac.uuid u ON u.uuid = r.usuario_uuid
LEFT JOIN dcac.usuarios us ON us.usuario = u.usuario
WHERE r.sociedad = <id> AND r.estado = 0;
```
`estado=0` en `rel_usuarios_sociedades` = vínculo activo; `deshabilitado=0` en
`usuarios` = usuario habilitado. Para loguearte con ese usuario, pedile al usuario
las credenciales de prueba del ambiente: no las infieras ni las guardes en ningún doc.

## Validar qué generó un endpoint

- Buscar la fila por su **ID público** devuelto en la response (`evaluacion_publica_id`,
  `reserva_publica_id`, `external_order_id`, etc.), nunca por ventana de tiempo ni
  por `MAX(id)` — en un ambiente compartido eso puede atribuir al usuario una fila de
  otro proceso. Si no tenés el ID, pedíselo antes de reportar "sí/no se insertó".
- Si el endpoint devuelve un cálculo/simulación (ej. un JSON de planificación),
  contrastar cada campo relevante contra el estado **real** de las tablas que dice
  haber consumido — la simulación puede divergir del estado real (una evaluación
  puede simular un consumo sin descontar saldo real todavía).
- Marcar como **hallazgo/bug** (no como duda a resolver después) cuando: (a) el
  JSON dice que algo quedó consumido pero la tabla real sigue en su estado previo
  sin motivo esperado, (b) una fuente de saldo real y activa aparece como no
  disponible sin justificación, (c) los totales no cierran contra la suma de las
  partes.
- Si piden comparar contra evaluaciones anteriores, armar tabla comparativa; si
  piden una sola, **no compares con otras sin que lo pidan**.

## Errores comunes

- Asumir un entorno sin preguntar al arrancar la sesión.
- Leer el `.cnf` con algo que no sea `grep '^#'`, o repetir la password en una respuesta.
- Correr el cliente sin `--init-command="SET SESSION TRANSACTION READ ONLY"`.
- Adivinar nombre de tabla/columna antes de `DESCRIBE`/`information_schema`.
- Asumir de qué microservicio es dueña una tabla por el nombre, sin chequear
  `microservicios/db/schemas/relations/` — varias veces el dueño real no es el
  esperado (ej. `ofertas` no es de `ms-invernada` sino de `ms-ofertas`; tablas de
  `mensajeria-notificaciones`/`creditos-scoring` resultaron legacy huérfanas sin
  microservicio moderno detrás).
- Tratar `OPTIMIZE`/`REPAIR TABLE` como "no es escritura porque no cambia datos".
- Confirmar un insert por cercanía temporal en vez de por el ID público exacto.
- Inventar un criterio de filtro cuando el término de negocio no tiene columna clara,
  en vez de preguntar.
- Completar un JOIN "a ojo" cuando la relación está marcada ambigua/no verificada en
  `relations/` (o no aparece ahí), en vez de mostrarle las opciones al usuario y
  esperar confirmación.
- Documentar schema de `financiero.*` en `dcac-context/` (prohibido — dato sensible
  del módulo financiero).
