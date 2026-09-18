---
name: planear-tests-ticket
description: Usar cuando el usuario quiere documentar cómo testear un ticket ya planificado sobre el workspace dcac-ia-context — existe (o se está armando) un plan de desarrollo y hay que definir el plan de testeo de comportamiento E2E. Triggers — "documentá los tests de T#####", "armá el plan de testeo", "cómo testeamos T#####", "definí cómo probar esto". NO ejecuta tests, solo los documenta.
---

# Documentar tests

Toma el **plan de desarrollo** de un ticket y produce el **plan de testeo de comportamiento**:
qué probar, los curls, cómo verificar éxito contra la DB, cómo dejar la DB como estaba, y qué
queda fuera de alcance. Ordena el trabajo en 3 fases: **entender → diseñar el test → documentar**.

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
| Plan de desarrollo | Base de qué se testea | Buscá `docs/{proyecto}/{tipo}/T<ticket>-<slug>/plan.md`; si no está, pedilo |
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

### Fase 1 — Entender
Leé el plan de desarrollo del ticket. Extraé: endpoints (verbo + ruta ms y ruta gateway `/v1/...`),
reglas de negocio, tablas tocadas (cruzar con `database-ownership.md`), auth requerida, y los
servicios que recorre el flujo E2E. Consultá `dcac-context/` → `CLAUDE.md` del repo → código.

### Fase 2 — Diseñar el plan de test (en plan mode)
Armá: comportamiento esperado (reglas), tabla de casos (ID, precondición, request, esperado,
código), **lista de curls** (ms directo + por gateway), verificaciones por verbo (tabla de arriba),
preparación de datos, teardown (DB de pruebas), y fuera de alcance.
Para los **candidatos a fuera de alcance** (inputs de usuario o ideas tuyas), **consultá al usuario**
si entran o no. Presentá el plan y llamá `ExitPlanMode`.

**No guardes el archivo todavía.** Se documenta recién tras la aprobación.

### Fase 3 — Documentar (solo tras aprobación)
Escribí el archivo en la ruta de la convención, con esta estructura:

```markdown
# Cómo testear — <Título> (T#####)

> **Ticket:** T#####
> **Implementación:** <qué se entregó: migración, módulo, endpoints>.
> Este doc define cómo verificar el **comportamiento** de la entrega.

## Comportamiento esperado
Reglas que deben cumplirse + rutas (ms interno y gateway `/v1/...`).

## Escenarios BDD (Gherkin)
Un `Feature` por comportamiento, con escenarios `Given / When / Then` legibles por
negocio. Cada escenario mapea 1:1 a un caso de la tabla de prueba y a un curl. Ejemplo
(bloque Gherkin, indentado):

    Feature: <comportamiento observable del ticket>

      Scenario: <caso feliz>
        Given <precondición de datos / estado en la DB de pruebas>
        When <request: verbo + ruta (ms directo o gateway /v1/...)>
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
Por cada endpoint, la query de DB que confirma el resultado (según verbo).

## Tabla de casos de prueba
| ID | Precondición | Acción / request | Esperado | Código |

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

## Modo orquestado (invocada por el motor `pipeline-desarrollo`)

Esta skill tiene **dos modos**. El default es **standalone** (gate humano con
`ExitPlanMode`, documentar recién tras la aprobación). Cuando la invoca el motor
`pipeline-desarrollo` como Fase 3, corre en **modo orquestado**.

Sabés que estás en modo orquestado si el prompt que te invoca lo dice explícitamente
(ej. "corré planear-tests-ticket en modo orquestado para T#####"). En ese caso:

1. **NO llames `ExitPlanMode` ni esperes OK humano.** El gate humano lo maneja el motor.
2. Hacé Fase 1 (entender el plan de desarrollo) y Fase 2 (diseñar el plan de test, con
   la capa **Gherkin**) igual que siempre.
3. **Guardá el doc directo** en la ruta de la convención
   (`docs/{proyecto}/{tipo}/T<ticket>-<slug>/tests.md`), incluyendo la sección
   `## Escenarios BDD (Gherkin)`.
4. **No decidas solo el fuera de alcance ni inventes credenciales/endpoints.** Cada uno
   de esos es una **DUDA** (bloqueante). Toda mejora que veas es una **SUGERENCIA**.
5. Terminá devolviendo al motor **este contrato exacto**:

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

## Errores comunes

- **Ejecutar los tests apenas se documenta** → no. La skill termina al guardar el doc.
- **Verificar solo el código HTTP** → no alcanza; siempre confirmar contra la DB.
- **Testear contra la DB de desarrollo (:3306)** → no; usar la DB de pruebas (:3307).
- **Proponer sqlite/hsql** → no aplica acá; usar la DB de pruebas dedicada.
- **Inventar credenciales de DB o un endpoint** → si falta acceso o scaffolding, preguntá al usuario.
- **Decidir solo qué queda fuera de alcance** → los candidatos se consultan con el usuario.
- **Guardar el doc antes de la aprobación** → el gate es `ExitPlanMode`; documentás después.
- **`docker compose down`/recrear un contenedor de DB ajeno al ticket para "arreglar" un
  error** → NUNCA. Ver "Infra compartida — reglas duras al ejecutar". Sin volumen nombrado
  confirmado, cualquier down/recreate puede borrar datos de todo el equipo.
- **Resolver por cuenta propia una dependencia caída (otro ms, su DB)** → es un bloqueo,
  consultá al usuario antes de tocar infraestructura que no es la DB de pruebas del ticket.
