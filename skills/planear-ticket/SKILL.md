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

### Fase 3 — Documentar (solo tras aprobación)
Con el plan aprobado, escribí el archivo en la ruta de la convención de arriba. Estructura:

```markdown
# Plan — <Título>

> **Ticket:** T#####

## Contexto
Por qué se hace, qué problema resuelve, resultado esperado. Incluir qué se encontró al leer
el código (ej. "el endpoint ya existe pero la transición X → Y falta en el enum").

## Parte 1 — <repo>
Por cada archivo a modificar:
- **Archivo:** ruta relativa al repo
- **Estado actual:** snippet del código relevante hoy (copiar de Read, no inventar)
- **Cambio:** snippet del código resultante
- Si hay tests: qué casos nuevos agregar, con el cuerpo del test siguiendo el patrón del spec existente

## Parte N — <repo>
...

## Verificación
Comandos concretos para probar el cambio: docker exec, curl/PUT con body exacto, qué respuesta
esperar. Incluir cómo correr los tests unitarios dentro del contenedor.

## Fuera de alcance
Qué queda explícitamente afuera.
```

### Fin de la skill — NO implementar
Con el plan documentado, la skill terminó. **No arranques a codear.** Confirmá al usuario dónde quedó
el archivo del plan y quedate esperando: la implementación es una decisión que toma él
explícitamente y por separado (ej. "dale, implementá", "arrancá con la Parte 1"). Hasta que no lo
diga, solo documentaste.

## Skills especiales por tipo de cambio

Ciertos cambios recurrentes tienen su propia skill con reglas específicas. Cuando el
ticket lo pide, el plan debe **incorporar esas reglas** en la parte correspondiente:

| Tipo de cambio | Skill | Cuándo |
|----------------|-------|--------|
| Migración de DB (nasgrate) | `crear-migracion` | El ticket indica cambios de esquema/datos. La parte "migración" del plan sigue sus 8 reglas (ubicación `nasgrate/data/migrations/`, nombre `YYYYMMDDHHMMSS_...`, solo UP, solo PRIMARY KEY, esquema del ticket, autor real). |

No inventes migraciones que el ticket no pide. Si el ticket necesita una y no dice en qué
esquema, es una **DUDA**.

## Modo orquestado (invocada por el motor `pipeline-desarrollo`)

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
