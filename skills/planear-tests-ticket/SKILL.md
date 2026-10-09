---
name: planear-tests-ticket
description: Usar cuando el usuario quiere documentar cómo testear un ticket del workspace dcac-ia-context — definir el plan de testeo de comportamiento E2E a partir de la spec del ticket, independiente del plan de desarrollo, para correrlo en RED antes de implementar y en GREEN después. Triggers — "documentá los tests de T#####", "armá el plan de testeo", "cómo testeamos T#####", "definí cómo probar esto". NO ejecuta tests, solo los documenta.
---

# Documentar tests

Toma la **spec del ticket** (descripción + criterios de aceptación) y produce el **plan de
testeo de comportamiento**: qué probar, los curls, cómo verificar éxito contra la DB, cómo
dejar la DB como estaba, y qué queda fuera de alcance. Ordena el trabajo en 3 fases:
**entender la spec → diseñar el test → documentar**.

**Los tests salen de la spec y nunca del plan de desarrollo.** Testean la solución del
ticket, no lo que el plan decidió implementar. Plan y tests se hacen por separado (pueden
correr en paralelo) y no se cruzan en ningún momento: el punto de encuentro es la
ejecución, al estilo RED/GREEN.

- **RED:** `testear-ticket` corre los tests antes de implementar. Los casos del
  comportamiento nuevo tienen que fallar; si alguno pasa, el test no discrimina o el
  comportamiento ya existía.
- **GREEN:** después de implementar, todos tienen que pasar. Si el plan se olvidó un
  criterio, ese test sigue en rojo: así aparece el hueco, sin revisar plan contra tests.

**La skill termina al documentar: NO ejecuta los tests.** La ejecución la declara el usuario
explícitamente, en un paso aparte. Documentar el plan de test no es luz verde para correrlos.

## Principio: tests de comportamiento, no de implementación

Se prueba el **comportamiento observable** end-to-end, a mano, recorriendo cada microservicio del
flujo (ms directo + atravesando apigateway). No alcanza con el código HTTP: **el éxito se confirma
contra la base de datos** (ver tabla por verbo).

## Datos requeridos

Si falta alguno, **preguntá antes de avanzar** (no inventes):

| Dato | Para qué | Si falta |
|------|----------|----------|
| Spec del ticket | Única base de qué se testea | Buscá `docs/{proyecto}/{tipo}/T<ticket>-<slug>/spec.md`; si no está, pedí el texto del ticket y guardalo ahí sin editarlo. **No leas `plan.md` aunque exista** |
| Contrato de la interfaz | Rutas, campos y códigos para escribir los curls | Sale de la spec. Si la spec no lo fija (ruta nueva, campo nuevo, código de error), **preguntá al usuario**: él lo fija y vale igual para el plan |
| Ticket `T#####` | Nombre del archivo | Preguntá el número |
| Proyecto destino | Carpeta dentro de `docs/` | Listá las carpetas de `docs/` y preguntá |
| Acceso a la DB de pruebas | Verificaciones del doc | Confirmá contenedor/credenciales (ver Acceso a la DB); si no los tenés, **pedíselos al usuario** |

## Convención de guardado (quick reference)

```
docs/{proyecto}/{tipo}/T<ticket>-<slug>/tests.md
```
- `{tipo}`: `desarrollo` o `soporte`, el mismo del plan de desarrollo. En el motor está en `estado.json`; en el flujo manual lo fija el paso 0 de `resolver-ticket`.
- `<slug>`: mismo tema que el plan de desarrollo, kebab-case (ej. `esquema-firmantes`).
- Crear `{proyecto}/`, `{tipo}/` y `T<ticket>-<slug>/` si no existen.
- Referencia de formato: la estructura de abajo. Si en `docs/` ya hay `tests.md` de tickets anteriores, podés mirar uno para mantener el mismo estilo.

## Acceso a la DB (para definir las verificaciones)

Los tests corren contra una **DB de pruebas dedicada**, NO contra la de desarrollo. Así la base de
desarrollo nunca se toca y el reset es recrear la de pruebas.

- DB de pruebas: contenedor `db-test-mariadb-1`, puerto host **3307** (idéntica a la de desarrollo).
  Credenciales y cómo conectarse: `microservicios/db-test/README.md`. Levantarla: `cd microservicios/db-test && docker compose up -d` (ver `microservicios/db-test/README.md`).
- Para que un servicio apunte a la DB de pruebas: en su `.env` cambiar **solo** `DB_PORT=3306` →
  `DB_PORT=3307` (`DB_HOST=host.address` queda igual) y reiniciar el contenedor (obligatorio en
  Hyperf/Swoole; ver `dcac-context/back/docker.md`). Revertir a 3306 al terminar.
- MongoDB por servicio (`ms-notificaciones-mongodb`, etc.) — ver `dcac-context/back/docker.md`.
- Tablas por servicio: `dcac-context/back/database-ownership.md` (cada ms solo accede a sus tablas).

Si no conocés el usuario/credencial o el flujo de repunte, **pedíselo al usuario**; no lo inventes.

## Infra compartida — reglas duras al ejecutar (no solo al documentar)

Esto aplica tanto si el propio ticket usa `db-test`/:3307 como si usa una DB compartida y
persistente (ej. la DB de otro servicio que el ticket necesita), y también a
**cualquier servicio de dependencia** que haga falta levantar para correr el flujo E2E
(otro microservicio, su propia DB, etc.). Se agregó esta sección tras un incidente real: al
ejecutar tests de un ticket, un contenedor de dependencia (`ms-permisos`) estaba caído y
necesitaba su propia MariaDB (`db-mariadb-1`, infra compartida de desarrollo — **no** la DB
de pruebas del ticket). Al toparse con un error de red al levantarla, se resolvió con
`docker compose down && docker compose up -d` sobre ese proyecto — el compose no declaraba
un volumen nombrado para el datadir, así que recrear el contenedor **borró la base `dcac`**
completa. Para que no vuelva a pasar:

1. **Nunca `docker compose down` (con o sin `-v`), `docker rm`, ni recrear un contenedor de
   base de datos que no sea la DB de pruebas descartable del propio ticket.** Esto incluye
   cualquier servicio de **dependencia** necesario para el flujo E2E (otro microservicio, su
   DB, Redis, Mongo, etc.) — son infra compartida entre todo el equipo, no propiedad de esta
   tarea.
2. Si un contenedor que necesitás está caído: primero `docker start <container>` (no
   destructivo). **Nunca** "arreglar" un error (de red, de conexión, lo que sea) bajando y
   levantando el compose de un servicio que no es tuyo — un error al iniciar no es licencia
   para recrear el contenedor.
3. Antes de tocar (start/restart/recreate) cualquier contenedor de DB que no creaste vos en
   esta sesión, **verificá que los datos viven en un volumen nombrado persistente**:
   `docker inspect <container> --format '{{json .Mounts}}'` o revisá el `docker-compose.yml`
   en busca de un volumen mapeado al datadir (`/var/lib/mysql`, `/var/lib/postgresql/data`,
   etc.). **Si no hay volumen nombrado, asumí que los datos son efímeros ligados a ese
   contenedor puntual — no lo toques.** Pará y consultá al usuario.
4. Si para levantar el flujo E2E hace falta un servicio de dependencia que está caído o con
   un problema de infra (red, DB, lo que sea) que no es trivial de resolver de forma segura
   (paso 2), **eso es un bloqueo para consultar al usuario**, no algo para resolver por cuenta
   propia tocando infraestructura ajena al ticket.
5. Mismo criterio ya vale para la propia DB de pruebas del ticket cuando es compartida (no
   `db-test`): `db-psp` y similares se tratan con `DELETE`/`UPDATE` puntuales en el teardown
   del ticket, **nunca** `down -v` ni recrear el contenedor entero.

## Cómo verificar éxito por tipo de operación

Además del código HTTP esperado, **siempre** una verificación contra la DB:

| Operación | Verificación de éxito |
|-----------|-----------------------|
| `POST` | Query a la tabla destino: la fila se insertó con los datos enviados (y los defaults/overrides que aplica el back). |
| `GET` | Comparar el **output del endpoint** contra lo que hay en la DB (query directa): coinciden filas, campos y derivados calculados al leer. |
| `PUT` / `PATCH` | Query a la fila modificada: los campos se actualizaron a los valores enviados. |
| `DELETE` | Query a la fila: eliminada — **física** (ya no existe) o **lógica** (flag/fecha de baja seteada). Identificá cuál aplica en el dominio. |
| Algoritmo / sin endpoint | Buscá una forma de ejercerlo: endpoint temporal, test puente, o invocación directa. Si hace falta crear scaffolding temporal, **consultá al usuario**. |

## Workflow

### Fase 1 — Entender la spec
Leé `spec.md`. Extraé: criterios de aceptación, reglas de negocio, actores y permisos,
casos borde que el ticket menciona o implica, y qué estado observable tiene que cambiar
(qué entidad se crea, modifica o da de baja).

Para traducir eso a verificaciones concretas podés consultar `dcac-context/` (reglas,
glosario, `database-ownership.md`, esquemas) y la DB de pruebas: el estado de la DB es
comportamiento observable. Si el ticket modifica algo que ya existe, podés leer el código
actual **solo para saber cómo se comporta hoy**, nunca para deducir cómo se va a
implementar el cambio. **No leas `plan.md`** en esta fase aunque exista.

**Tamaño.** Lo que se escribe acá lo leen el revisor, el RED, cada GREEN y el
Cronista, así que cada caso de más se paga muchas veces:
- **Un escenario por criterio de aceptación**, más los bordes que definió la escritura o la
  spec. No sumes casos "por las dudas": cada caso tiene que poder señalar el criterio o la
  decisión que lo justifica.
- Los curls usan variables para host, token y headers, definidas una vez arriba, no
  repetidas en cada caso.
- Objetivo: unos 15 casos para un ticket de uno o dos repos. Si hacen falta muchos más, es
  señal de que el ticket es grande y conviene decirlo.

### Fase 2 — Diseñar el plan de test (en plan mode)
Armá: comportamiento esperado (reglas), escenarios Gherkin, tabla de casos (ID,
criterio, precondición, request, esperado, código, esperado en RED), **lista de curls** (ms directo +
por gateway), verificaciones por verbo (tabla de arriba), preparación de datos, teardown
(DB de pruebas), y fuera de alcance. Cada criterio de aceptación de la spec tiene que tener
al menos un escenario; si uno no se puede testear, va a fuera de alcance con el motivo.

**Esperado en RED**, por caso:
- `falla` → el caso ejercita comportamiento nuevo del ticket.
- `pasa` → el caso es de regresión: comportamiento que ya existe y no se tiene que romper.

**Criterio**, por caso, en la segunda columna de la tabla, siempre: uno o más `CA#` de
`spec.md` (`CA1, CA2`); si el caso sale de una decisión y no de un criterio (por ejemplo, el
formato de un campo), el número de esa decisión de `spec.md` (`E1`, `P2`, `C3`); o
`regresión` para un caso de comportamiento existente. La lee `trazabilidad.py`; un caso sin
criterio, una decisión que no está en la spec, o un criterio sin caso, frena la revisión.

**Los curls y las queries usan el contrato de la spec.** Lo que la spec no fija (la ruta de
un endpoint nuevo, el nombre de un campo, el código de un error) no lo deducís ni lo
inventás: preguntale al usuario. Lo que él fije es el contrato que también tiene que
cumplir el plan.

Para los **candidatos a fuera de alcance** (inputs de usuario o ideas tuyas), **consultá al usuario**
si entran o no. Presentá el plan y llamá `ExitPlanMode`.

**No guardes el archivo todavía.** Se documenta recién tras la aprobación.

### Fase 3 — Documentar (solo tras aprobación)
Escribí el archivo en la ruta de la convención, con esta estructura:

```markdown
# Cómo testear — <Título> (T#####)

> **Ticket:** T#####
> **Fuente:** spec.md (nunca plan.md)
> Este doc define cómo verificar el **comportamiento** pedido por el ticket.

## Contrato
Rutas (ms interno y gateway `/v1/...`), campos y códigos que usan los curls, y de dónde
sale cada uno (spec o decisión del usuario).

## Comportamiento esperado
Reglas que deben cumplirse, tal como las pide la spec.

## Escenarios BDD (Gherkin)
Un `Feature` por comportamiento, con escenarios `Given / When / Then` legibles por
negocio. Cada escenario mapea 1:1 a un caso de la tabla de prueba y a un curl. Ejemplo
(bloque Gherkin, indentado):

    Feature: <comportamiento observable del ticket>

      Scenario: <caso feliz>
        Given <precondición de datos / estado en la DB de pruebas>
        When <request: verbo + ruta del contrato (ms directo o gateway /v1/...)>
        Then <código HTTP esperado>
        And <fila esperada en la tabla destino / campo derivado>

      Scenario: <caso borde o error>
        Given <precondición>
        When <request>
        Then <código de error esperado>
        And <la DB no cambió / cambió como corresponde>

El `Given` se materializa en "Preparación de datos", el `When` en la "Lista de curls", y
el `Then` en "Cómo verificar éxito" (query a la DB). El Gherkin es la capa legible; los
curls + la verificación DB son la prueba real.

## Lista de curls
Cada request a probar (ms directo con headers internos + E2E por gateway con auth real).

## Cómo verificar éxito
Por cada caso, la query de DB que confirma el resultado (según verbo).

## Tabla de casos de prueba
| ID | Criterio | Precondición | Acción / request | Esperado | Código | Esperado en RED |

## Preparación de datos de prueba
Cómo dejar la DB lista para cada caso (precondiciones).

## Teardown — dejar la DB como estaba
Se testea contra la DB de pruebas (`db-test`, :3307). Reset prístino:
`cd microservicios/db-test && docker compose down -v && docker compose up -d`.
La DB de desarrollo (:3306) nunca se toca.

## Fuera de alcance
Qué NO se testea (y por qué); problemas críticos detectados.
```

### Fin de la skill — NO ejecutar
Con el plan de test documentado, la skill terminó. **No corras los tests.** Confirmá al usuario
dónde quedó el archivo y esperá: la ejecución la declara él aparte ("dale, corré los tests").

## Por qué DB de pruebas y no sqlite

No usar sqlite/hsql: los microservicios están casados con MariaDB/MongoDB reales (prefijos
`dcac.`/`negocios.`, cross-DB, features MySQL). El reset se logra con la **DB de pruebas dedicada**
idéntica a la de desarrollo: se testea contra `db-test` (:3307) y para volver al estado original se
recrea (`down -v && up`), sin tocar la base de desarrollo.

## Modo orquestado (subagente de `resolver-ticket` o del motor `pipeline-desarrollo`)

Esta skill tiene **dos modos**. El default es **standalone** (gate humano con
`ExitPlanMode`, documentar recién tras la aprobación). Cuando la despacha un orquestador
como subagente (`resolver-ticket` en su fase 1, como agente generativo, o el motor en su Fase 3), corre en
**modo orquestado**, normalmente en paralelo con `planear-ticket`.

Sabés que estás en modo orquestado si el prompt que te invoca lo dice explícitamente
(ej. "corré planear-tests-ticket en modo orquestado para T#####"). En ese caso:

1. **NO llames `ExitPlanMode` ni esperes OK humano.** El gate humano lo maneja quien te
   despachó.
2. Hacé Fase 1 (entender la spec) y Fase 2 (diseñar el plan de test, con los escenarios
   **Gherkin** y el esperado en RED) igual que siempre.
3. Tu única fuente es `spec.md` (más `dcac-context/` y la DB para las verificaciones). Si
   el prompt trae análisis, hipótesis de solución o partes del plan, ignoralas y no leas
   `plan.md`.
4. **Guardá el doc directo** en la ruta de la convención
   (`docs/{proyecto}/{tipo}/T<ticket>-<slug>/tests.md`), incluyendo la sección
   `## Escenarios BDD (Gherkin)`.
5. **No decidas solo el fuera de alcance ni inventes credenciales, endpoints ni partes del
   contrato que la spec no fija.** Cada uno de esos es una **DUDA** (bloqueante). Un
   criterio de la spec ambiguo también. Toda mejora que veas es una **SUGERENCIA**.
6. Terminá devolviendo **este contrato exacto**:

```
ARTEFACTO: <path del plan de test guardado>
DUDAS:
  - [D1] <pregunta concreta> · <dónde surgió> · <por qué no se puede asumir>
SUGERENCIAS:
  - [S1] <propuesta> · <beneficio> · <costo/riesgo>
ESTADO: completo | frenado-por-duda
```

- `ESTADO: frenado-por-duda` si falta acceso a DB, hay ambigüedad de comportamiento, o
  el fuera de alcance no se puede decidir sin el usuario. Si no, `ESTADO: completo`.
- Listas vacías: `DUDAS: (ninguna)` / `SUGERENCIAS: (ninguna)`.

El resto de las reglas (tests de comportamiento, verificación contra DB de pruebas,
teardown) aplican **igual** en modo orquestado.

## Como agente generativo de `resolver-ticket` o `ciclo-ticket`

Si el prompt dice que sos el agente generativo de los tests:

1. Tu única fuente de lo pedido es `spec.md`. **Nunca leas `plan.md`.**
2. Cada caso lleva su `Criterio`. Un criterio que no se puede testear va a "Fuera de
   alcance" con el motivo, y es una DUDA.
3. Las DUDAS van en el contrato; te las contesta el Baqueano o el usuario. Si un esperado
   sale de una respuesta del Baqueano, citá la consulta (`C3`) en el caso.
4. Después de entregar, no te van a retomar: la revisión la hace un revisor nuevo y las
   correcciones, otro agente.

## Errores comunes

- **Ejecutar los tests apenas se documenta** → no. La skill termina al guardar el doc.
- **Verificar solo el código HTTP** → no alcanza; siempre confirmar contra la DB.
- **Testear contra la DB de desarrollo (:3306)** → no; usar la DB de pruebas (:3307).
- **Proponer sqlite/hsql** → no aplica acá; usar la DB de pruebas dedicada.
- **Inventar credenciales de DB o un endpoint** → si falta acceso o scaffolding, preguntá al usuario.
- **Decidir solo qué queda fuera de alcance** → los candidatos se consultan con el usuario.
- **Guardar el doc antes de la aprobación** → el gate es `ExitPlanMode`; documentás después.
- **Leer `plan.md`, antes o después de escribir los tests** → los tests heredan las
  decisiones y los olvidos del plan. Plan y tests no se cruzan; se encuentran al ejecutar.
- **Deducir la ruta o la columna que "seguro" va a crear el plan** → si la spec no fija
  el contrato, lo fija el usuario.
- **No marcar el esperado en RED** → sin eso, la corrida RED no puede distinguir un test
  que no discrimina de uno de regresión.
- **Reescribir un test para que pase con lo implementado** → un test que sale de la spec
  solo cambia si el usuario lo decide.
- **`docker compose down`/recrear un contenedor de DB ajeno al ticket para "arreglar" un
  error** → NUNCA. Ver "Infra compartida — reglas duras al ejecutar". Sin volumen nombrado
  confirmado, cualquier down/recreate puede borrar datos de todo el equipo.
- **Resolver por cuenta propia una dependencia caída (otro ms, su DB)** → es un bloqueo,
  consultá al usuario antes de tocar infraestructura que no es la DB de pruebas del ticket.
