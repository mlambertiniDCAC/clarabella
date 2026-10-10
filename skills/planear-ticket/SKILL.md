---
name: planear-ticket
description: Usar cuando el usuario arranca a desarrollar una tarea o feature sobre el workspace dcac-ia-context con un ticket asignado (T#####) y quiere ordenar el trabajo antes de codear. Triggers — "arranquemos con T#####", "vamos a desarrollar X, ticket T####", "documentá y planeá esto antes de implementar", o cualquier inicio de desarrollo donde haya un problema y un número de ticket.
---

# Documentar desarrollo

Ordena un desarrollo en 3 fases: **entender → planificar → documentar**.
El plan mode nativo es el gate de aprobación: el plan se guarda en `docs/` recién **después**
de que el usuario lo aprueba. **La skill termina ahí: NO implementes.** La implementación la declara
el usuario explícitamente, en un paso aparte. Documentar el plan no es luz verde para codear.

## Datos requeridos

Si falta alguno, **preguntá antes de avanzar** (no inventes):

| Dato | Para qué | Si falta |
|------|----------|----------|
| Problema / objetivo | Entender qué se desarrolla | Pedile que lo describa |
| Ticket `T#####` | Nombre del archivo del plan | Preguntá el número |
| Proyecto destino | Carpeta dentro de `docs/` | Listá las carpetas existentes en `docs/` y preguntá cuál (o si hay que crear una nueva) |

## Convención de guardado (quick reference)

```
docs/{proyecto}/{tipo}/T<ticket>-<slug>/plan.md
```
- `{proyecto}`: carpeta de `docs/` (ej. el nombre del proyecto o del dominio del ticket).
- `{tipo}`: `desarrollo` o `soporte`. En el motor está en `estado.json`; en el flujo manual lo fija el paso 0 de `resolver-ticket` (si no te lo pasaron, preguntá).
- `<slug>`: kebab-case del título (`slugify(titulo)`), sin tildes/ñ (ej. `esquema-firmantes`).
- Crear `{proyecto}/`, `{tipo}/` y `T<ticket>-<slug>/` si no existen.
- Referencia de formato: la estructura de abajo. Si en `docs/` ya hay planes de tickets anteriores, podés mirar uno para mantener el mismo estilo.

## Workflow

### Fase 1 — Entender
Identificá el/los repo/s a tocar (`microservicios/<ms>`, `webadmin/`, etc.). **El análisis
del código se hace sobre la última master:** si el repo no está actualizado, prepararlo
primero con `preparar-repo` (switch a master + pull). En el pipeline eso ya lo hizo
la Fase 1 del motor. Consultá en este orden: `dcac-context/` → `CLAUDE.md` del repo →
código como fallback (regla del workspace).

**Exploración en paralelo por repo.** Si el ticket toca más de un repo (p. ej. un ms +
`apigateway`), o uno solo pero con un dominio amplio, despachá **un subagente `Explore` por
repo, todos en el mismo mensaje** para que corran a la vez:

```
Agent(subagent_type: "Explore", description: "Explorar <ms> para T#####",
      prompt: "Objetivo del ticket: <1-3 líneas de la spec>. Repo: microservicios/<ms>
               (en master actualizado). Consultá en orden dcac-context/ → CLAUDE.md del repo
               → graphify-out/ si existe → código. Devolvé: archivos candidatos a tocar
               (ruta:línea), patrones a espejar, tablas propias involucradas, endpoints
               relacionados y dudas. Breadth: medium.")
```

Pasales el objetivo del ticket, **no una hipótesis de solución**: si les decís "hay que
agregar X en el enum Y", buscan eso y confirman tu idea en vez de mostrarte qué hay. Para
un ticket chico en un solo repo no hace falta despachar nada: explorá directo.

Si corrés como subagente (modo orquestado) no podés despachar exploradores: el orquestador
los corre antes y te pasa sus mapas en `revision/exploracion-<ms>.md`.

Lo que devuelven es un mapa, no el análisis: orientan qué leer, pero la lectura de los
archivos a modificar la hacés vos con Read (ver abajo).

Si el repo ya tiene un grafo de conocimiento (`graphify-out/graph.json`), usá
`consultar-grafo` como primer paso del fallback de código: te orienta más rápido
sobre qué archivos/clases mirar antes de leerlos con Read. No reemplaza la lectura real del
código (ver el punto siguiente), solo la acelera. Si el repo no tiene grafo, seguí directo
a leer código sin mencionarlo.

**Leer el código real de los archivos que se van a modificar.** No alcanza con el resumen de
un agente de exploración: leé con Read los servicios, DTOs, enums, tests y controladores
relevantes antes de planificar. El objetivo es poder escribir en el plan el estado actual
exacto (qué líneas existen hoy) y el cambio propuesto (qué líneas quedan después).

Resumí el estado actual relevante: tablas, patrones a espejar, módulos cercanos.

### Fase 2 — Planificar (en plan mode)
Armá un plan pulido **respetando las decisiones del usuario**. Si ves una mejor opción por
buenas prácticas, o hay una duda/ambigüedad, **avisá y consultá** — no asumas. Presentá el
plan y llamá `ExitPlanMode` para que el usuario lo apruebe.

**No guardes el archivo todavía.** El plan se documenta recién tras la aprobación.

**Tamaño del plan.** Todo lo que viene después (revisor, implementadores, Cronista)
lee el plan entero, así que cada línea de más se paga varias veces:
- Snippets **solo de lo que cambia**, con 2-3 líneas de contexto. Nunca un archivo entero.
- Un archivo sin cambios no aparece. Un cambio mecánico repetido (por ejemplo, ajustar el
  mismo assert en varios tests) se describe una vez y se listan los lugares.
- Objetivo: que el plan entre en unas 300 líneas. Si no entra, es señal de que el ticket
  es grande y conviene decirlo.

### Fase 3 — Documentar (solo tras aprobación)
Con el plan aprobado, escribí el archivo en la ruta de la convención de arriba. Estructura:

```markdown
# Plan — <Título>

> **Ticket:** T#####

## Contexto
Por qué se hace, qué problema resuelve, resultado esperado. Incluir qué se encontró al leer
el código (ej. "el endpoint ya existe pero la transición X → Y falta en el enum").

## Parte 1 — <repo>
Cubre: CA1, CA3

Por cada archivo a modificar:
- **Archivo:** ruta relativa al repo
- **Estado actual:** snippet del código relevante hoy (copiar de Read, no inventar)
- **Cambio:** snippet del código resultante
- Si hay tests: qué casos nuevos agregar, con el cuerpo del test siguiendo el patrón del spec existente

## Parte N — <repo>
Cubre: CA2
...

## Contrato
### Expone
- `VERBO /ruta` — body → respuesta
### Consume
- `VERBO /ruta` — de T##### | existente

## Verificación
Comandos concretos para probar el cambio: docker exec, curl/PUT con body exacto, qué respuesta
esperar. Incluir cómo correr los tests unitarios dentro del contenedor.

## Fuera de alcance
Qué queda explícitamente afuera.
```

**`## Contrato`** lista lo que el cambio expone y lo que consume de otros servicios o
tickets. En `resolver-ticket` es opcional; en `resolver-proyecto`, obligatoria (formato en
"Como generador de `resolver-proyecto`").

**`Cubre:`** es obligatoria en cada Parte: la línea empieza exactamente con `Cubre: ` y
lista los criterios de `spec.md` que esa Parte implementa (`CA1, CA3`). La lee
`trazabilidad.py`; un criterio que ninguna Parte cubre frena la revisión.

### Fin de la skill — NO implementar
Con el plan documentado, la skill terminó. **No arranques a codear.** Confirmá al usuario dónde quedó
el archivo del plan y quedate esperando: la implementación es una decisión que toma él
explícitamente y por separado (ej. "dale, implementá", "arrancá con la Parte 1"). Hasta que no lo
diga, solo documentaste.

Los tests se escriben aparte, desde la spec (paso 3 de `resolver-ticket`, o el generador
de tests en `resolver-proyecto`). **No leas `tests.md`** para armar ni para ajustar el plan: plan y tests se encuentran
en la revisión (`revisar-ticket`) y al
ejecutarse (RED antes de implementar, GREEN después). Lo que necesiten en común, como una ruta o un
campo que el ticket no fijaba, lo decide el usuario y queda en `spec.md`, en
`## Decisiones de contrato`: el plan tiene que respetarlo.

## Skills especiales por tipo de cambio

Ciertos cambios recurrentes tienen su propia skill con reglas específicas. Cuando el
ticket lo pide, el plan debe **incorporar esas reglas** en la parte correspondiente:

| Tipo de cambio | Skill | Cuándo |
|----------------|-------|--------|
| Migración de DB (nasgrate) | `crear-migracion` | El ticket indica cambios de esquema/datos. La parte "migración" del plan sigue sus 8 reglas (ubicación `nasgrate/data/migrations/`, nombre `YYYYMMDDHHMMSS_...`, solo UP, solo PRIMARY KEY, esquema del ticket, autor real). |

No inventes migraciones que el ticket no pide. Si el ticket necesita una y no dice en qué
esquema, es una **DUDA**.

## Modo orquestado (subagente de `resolver-proyecto` o del motor `pipeline-desarrollo`)

Esta skill tiene **dos modos**. El default es **standalone** (todo lo de arriba: gate
humano con `ExitPlanMode`, documentar recién tras la aprobación). Pero cuando la invoca
el motor `pipeline-desarrollo` como Fase 2, corre en **modo orquestado**.

Sabés que estás en modo orquestado si el prompt del que te invoca lo dice explícitamente
(ej. "corré planear-ticket en modo orquestado para T#####"). En ese caso:

1. **NO llames `ExitPlanMode` ni esperes OK humano.** El gate humano lo maneja el motor
   vía su doubt-gate, no vos.
2. Hacé Fase 1 (entender, leyendo el código real) y Fase 2 (armar el plan) igual que
   siempre.
3. **Guardá el plan directo** en la ruta de la convención
   (`docs/{proyecto}/{tipo}/T<ticket>-<slug>/plan.md`).
4. **No decidas nada sensible por tu cuenta.** Toda ambigüedad de documentación o de
   producto es una **DUDA** (bloqueante). Toda mejora de buenas prácticas que veas es una
   **SUGERENCIA** (no bloqueante). No las resuelvas: reportalas.
5. Terminá devolviendo al motor **este contrato exacto**:

```
ARTEFACTO: <path del plan guardado>
DUDAS:
  - [D1] <pregunta concreta> · <dónde surgió> · <por qué no se puede asumir>
SUGERENCIAS:
  - [S1] <propuesta> · <beneficio> · <costo/riesgo>
ESTADO: completo | frenado-por-duda
```

- Si hay al menos una DUDA que impide un plan correcto → `ESTADO: frenado-por-duda`
  (igual guardás lo que pudiste avanzar, marcando los huecos en el plan).
- Si no hay dudas bloqueantes → `ESTADO: completo` (las SUGERENCIAS no bloquean).
- Listas vacías: escribí `DUDAS: (ninguna)` / `SUGERENCIAS: (ninguna)`.

El resto de las reglas de la skill (leer código real, plan de implementación con líneas
exactas, no escalar el scope) aplican **igual** en modo orquestado.

**Latido de actividad (para el feed en vivo del dashboard):** appendeá una línea al
`docs/{proyecto}/{tipo}/T<ticket>-<slug>/.pipeline/actividad.jsonl` en cada paso clave (arranco, leo tal
archivo/servicio, armo el plan, termino) para que el usuario vea que estás trabajando y no crea
que está colgado:
```bash
echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"fase\":\"2\",\"actor\":\"subagente\",\"tipo\":\"lectura\",\"texto\":\"leyendo <archivo>\",\"meta\":{}}" >> docs/{proyecto}/{tipo}/T<ticket>-<slug>/.pipeline/actividad.jsonl
```

## Como generador de `resolver-proyecto`

Si el prompt dice que sos el agente generativo del plan:

1. Tu única fuente de lo pedido es `spec.md`. **Nunca leas `tests.md`.**
2. Cada Parte lleva su línea `Cubre:`. Un criterio que no sabés cómo cubrir es una DUDA, no
   una Parte sin `Cubre:`.
3. Las DUDAS van en el contrato; te las contesta el Baqueano o el usuario. Si una decisión
   sale de una respuesta del Baqueano, citá la consulta (`C3`) en el plan, al lado de la
   decisión.
4. Después de entregar, no te van a retomar: la revisión la hace un revisor nuevo y las
   correcciones, otro agente. Lo que dejes escrito es lo que cuenta.
5. **`## Contrato`**, al final del plan, siempre:

       ## Contrato
       ### Expone
       - `POST /internal/permisos/usuarios` — body `{usuarioId, sujetoId}` → 201 `{id}`
       ### Consume
       - `GET /compliance/:id/permisos-psp` — de T23821
       - `POST /internal/cuentas/:id/usuarios/sync-compliance` — existente

   Cada endpoint entre backticks como `VERBO /ruta`. Un Consume dice de qué ticket del lote
   sale (`de T#####`) o que ya existe (`existente`). Si no expone o no consume nada, la
   subsección lleva `- (nada)`. Lo lee `contratos.py`.

## Errores comunes

- **Plan de objetivos en lugar de plan de implementación** → el plan debe decir exactamente qué
  líneas cambian, en qué archivo, con qué código. Si solo dice "extender las transiciones" sin
  mostrar el enum actual y el enum resultante, el plan es insuficiente.
- **Confiar en el resumen del agente sin leer el código** → los agentes de exploración dan una
  vista de alto nivel que puede estar incompleta o desactualizada. Siempre leé con Read los
  archivos clave antes de escribir el plan.
- **Escalar el scope más allá del ticket** → planificá solo lo que pide el ticket. Si encontrás
  algo relacionado pero fuera de scope, mencionalo en "Fuera de alcance", no lo incluyas en el plan.
- **Guardar el plan antes de que lo aprueben** → no. El gate es `ExitPlanMode`; documentás después.
- **Arrancar a implementar apenas se documenta el plan** → no. La skill termina al guardar el plan;
  la implementación la declara el usuario en un paso aparte.
- **Asumir el proyecto o el ticket** → si no te lo dieron, preguntá (listá las carpetas de `docs/`).
- **Pisar decisiones del usuario con "buenas prácticas"** → proponé y consultá, no impongas.
