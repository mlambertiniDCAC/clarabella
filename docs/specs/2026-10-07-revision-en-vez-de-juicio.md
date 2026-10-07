# Revisión en vez de juicio — diseño

Fecha: 2026-10-07 · Versión objetivo: 0.5.0 (sobre la 0.4.0 sin commitear)

## Problema

`juicio-ticket` es el mayor gasto de tokens y tiempo de Clarabella. El costo es
estructural, no de configuración:

- **Retoma de contextos grandes.** El Juez (opus) se retoma en las rondas 1, 3 y 5, y los
  agentes generativos se retoman para defenderse y corregir, incluido el agente del plan
  (opus) con toda su exploración del código. Cada retoma re-procesa ese contexto.
- **Costo multiplicativo.** Cada observación pasa por acusación, defensa, peritaje,
  sentencia, corrección y verificación, y el juicio entero se repite para la
  implementación.
- **Verificación de honestidad, no de código.** Los peritos chequean citas y bitácoras; eso
  no encuentra bugs.

Ponerle presupuesto al juicio daría un juicio más chico con la misma forma. Se reemplaza.

## Objetivo

Mantener lo que el juicio aportaba (cobertura spec → plan → tests, reglas críticas del
workspace, convenciones, desvíos del plan) con verificación determinística donde se pueda y
una sola revisión barata donde no.

**Criterios de éxito**
- Ningún paso de calidad retoma al agente del plan ni a un agente con exploración grande.
- Una revisión por artefacto: un subagente sonnet nuevo, una pasada, sin rondas.
- Cobertura y reglas críticas verificadas por scripts (0 tokens).
- Cada fase anota sus tokens en `registro.md`, para medir contra la 0.4.0.

## Diseño

### 1. Criterios numerados

- En el paso 0 de `resolver-ticket` (después del `escribano`), los criterios de aceptación
  de `spec.md` quedan numerados `CA1…CAn`, en una sección `## Criterios de aceptación`.
- `plan.md`: cada `## Parte N — <repo>` lleva una línea `Cubre: CA1, CA3`.
- `tests.md`: la "Tabla de casos de prueba" lleva una columna `Criterio` con uno o más
  `CA#`. Los casos de regresión llevan `regresión`.

### 2. `scripts/trazabilidad.py`

Entrada: la carpeta del ticket. Lee `spec.md`, `plan.md`, `tests.md`.

Reporta:
- criterio sin Parte que lo cubra;
- criterio sin caso de test;
- caso sin criterio (salvo `regresión`);
- `CA#` citado que no existe en la spec.

Salida a `revision/trazabilidad.txt`. Código de salida 0 si está limpio, 1 si no. Sin
dependencias fuera de la stdlib.

### 3. `scripts/reglas.py`

Entrada: un worktree y la base (`master`). Corre sobre las líneas agregadas del diff.

| Regla | Heurística |
|-------|------------|
| Estado en propiedades de clase (Hyperf / apigateway) | Propiedad declarada en el diff que no se asigna solo en el constructor (DI), y se asigna en otro método |
| Tablas de otro servicio | Nombres de tabla en queries, modelos y `Db::table()` cruzados con `dcac-context/back/database-ownership.md` |
| Llamadas entre microservicios | Clientes HTTP o URLs/hosts que apuntan a otro ms del workspace |

Salida: alertas `archivo:línea · regla · fragmento` en `revision/reglas-<ms>.txt`. Son
alertas, no veredictos: los falsos positivos los descarta la revisión con una línea de
justificación.

### 4. Skill `revisar-ticket` (reemplaza a `juicio-ticket`)

Un subagente **nuevo**, `model: "sonnet"`, **una pasada**.

| Modo | Entrada (cerrada) |
|------|-------------------|
| plan-tests | `spec.md`, `plan.md`, `tests.md`, `revision/trazabilidad.txt`, `dcac-context/back/conventions.md`, `CLAUDE.md` de cada repo |
| implementación | `git diff master` del repo (o el delta desde la última revisión, en el ciclo), `plan.md`, `revision/reglas-<ms>.txt`, `revision/notas-<ms>.md`, `conventions.md`, `CLAUDE.md` del repo |

Checklist fija (lo que buscaba el Juez, sin la parte de sospechar de los agentes):
- plan-tests: cada criterio cubierto con sentido (no solo citado); reglas críticas en el
  plan; contrato de la spec respetado en plan y tests; esperados coherentes con la doc;
  verificaciones contra tablas del servicio dueño; "Esperado en RED" coherente; plan y tests
  describen el mismo comportamiento.
- implementación: cada Parte implementada; cambios fuera del plan sin nota; tests unitarios
  que el plan pedía; alertas de `reglas.py` confirmadas o descartadas; convenciones del
  servicio y del código vecino.

Salida: `revision/revision-plan-tests.md` o `revision/revision-impl-<ms>.md`, con **hasta 10
hallazgos**, cada uno:

```markdown
### H3 · bloqueante
- **Dice el artefacto:** <cita>
- **Dice la fuente:** <cita> — `<ruta>` § <sección>
- **Propuesta:** <qué cambiar>
```

Lo que no tiene fuente no se reporta. No ejecuta nada.

Contrato:
```
ARTEFACTO: revision/<archivo>
HALLAZGOS: <n> (B bloqueantes, M menores)
ALERTAS_DESCARTADAS: <n> (con justificación en el archivo)
ESTADO: completo
```

**Corrección**
- Plan y tests: un subagente sonnet **nuevo** recibe solo el artefacto y los hallazgos, y
  corrige solo eso. Si el cambio es trivial (una línea `Cubre:`, un renombre), lo hace el
  hilo principal. Si no está de acuerdo con un hallazgo, lo anota y va al usuario en una
  línea.
- Implementación: corrige quien implementó (el hilo principal o el subagente del repo).
- **Sin segunda revisión.** La verificación es volver a correr `trazabilidad.py` /
  `reglas.py`, y un GREEN nuevo si cambió código.

### 5. Flujo de `resolver-ticket`

- **Paso 0:** igual + numerar `CA#`.
- **Fase 1 — Preparación:** igual (dos agentes generativos ciegos entre sí, plan en opus,
  tests en sonnet, Baqueano), sin "reglas del oficio" ni bitácoras. Los ids se guardan solo
  para pasarles respuestas del Baqueano durante la fase 1.
- **Fase 2 — Revisión:** `trazabilidad.py` → `revisar-ticket` plan-tests → corrección →
  `trazabilidad.py` → el usuario aprueba `plan.md` y `tests.md`.
- **Fase 3 — Implementación:** RED, implementar, GREEN igual. La bitácora del implementador
  pasa a `revision/notas-<ms>.md` (solo desvíos del plan). 3.4: `reglas.py` →
  `revisar-ticket` implementación → corrección → GREEN si cambió código → `reglas.py`.
  3.5: el usuario valida el diff.
- **Fase 4 — Entrega:** igual.

### 6. Flujo de `ciclo-ticket`

- **Etapa 2:** revisión de plan y tests. "Sin bloqueantes" reemplaza la aprobación del
  usuario; los desacuerdos van al Baqueano (menor o provisoria).
- **Vuelta:** implementar → GREEN → si GREEN completo: `reglas.py` + `revisar-ticket`
  implementación → evaluar. La primera revisión ve el diff completo; las siguientes, el
  delta desde la última revisión.
- **Definición de terminado, punto 3:** `reglas.py` sin alertas abiertas y revisión sin
  bloqueantes.
- **Fallas:** hallazgo bloqueante → implementador (en el ciclo se lo sigue retomando: es
  sonnet y es quien conoce el código). `hueco-del-plan` y `test-mal-documentado` → un
  sonnet nuevo corrige, después trazabilidad y, si aplica, el RED de ese caso.
- **Faltas:** queda `sin-progreso`. Se eliminan `fabricacion` y `defensa-perdida`.
- **Firma de la vuelta:** casos que fallan + hallazgos bloqueantes.

### 7. Cronista

Sigue en sonnet: con haiku, en T23814, inventó cifras y cargó decisiones de agentes como
del usuario, y esas decisiones alimentan los precedentes del Baqueano.

Se abarata por la entrada:
- `scripts/hechos.py` arma `revision/hechos.md` con los datos duros: Economía (desde
  `registro.md`), Verificación (reportes RED/GREEN), repos y `diff --stat`, decisiones del
  usuario (`spec.md` § Decisiones de contrato, provisorias confirmadas/vetadas).
- El Cronista redacta desde `hechos.md` y `spec.md`, y abre otros archivos solo para
  chequear un dato puntual.
- Se eliminan las secciones "Tribunales" y "Prontuario". "Fe de erratas" toma los
  hallazgos de las revisiones en vez de las sentencias.

### 8. Carpeta del ticket

`juicio/` pasa a `revision/`:

```
revision/
├── trazabilidad.txt
├── reglas-<ms>.txt
├── revision-plan-tests.md
├── revision-impl-<ms>.md
├── notas-<ms>.md
├── hechos.md
├── consultas-*.md        ← Baqueano
├── provisorias.md        ← solo en el ciclo
└── testeo/               ← reportes RED/GREEN
```

## Cambios por archivo

| Archivo | Cambio |
|---------|--------|
| `skills/juicio-ticket/` | Se elimina |
| `skills/ensayar-juicio/` | Se elimina |
| `skills/revisar-ticket/SKILL.md` | Nueva |
| `scripts/trazabilidad.py`, `scripts/reglas.py`, `scripts/hechos.py` | Nuevos |
| `skills/resolver-ticket/SKILL.md` | Fases 1–3 según §5 |
| `skills/ciclo-ticket/SKILL.md` | Según §6 |
| `skills/planear-ticket/SKILL.md` | Sale "Como agente generativo de juicio-ticket"; entra `Cubre: CA#` |
| `skills/planear-tests-ticket/SKILL.md` | Ídem; entra columna `Criterio` |
| `skills/implementar-ticket/SKILL.md` | Bitácora → `revision/notas-<ms>.md` |
| `skills/baqueano/SKILL.md` | Sale "El Baqueano en el juicio" y las faltas ligadas a peritajes |
| `skills/escribano/SKILL.md` | Numerar `CA#` al cerrar la escritura; rutas `juicio/` → `revision/` |
| `skills/cronista/SKILL.md` | Según §7 |
| `skills/clarabella/SKILL.md` | Tabla de derivación: `revisar-ticket`; fuera `juicio-ticket` y `ensayar-juicio` |
| `README.md`, `.claude-plugin/plugin.json` | Tabla de skills, flujo, modelos por rol; versión 0.5.0 |

## Fuera de alcance

- `pipeline-desarrollo`, `dashboard-desarrollo` y `entorno-ticket` (skills personales, fuera
  del plugin): no referencian al juicio.
- Simplificar Baqueano, Escribano o la ceguera entre agentes generativos: se evalúa después
  con las cifras de `registro.md`.

## Verificación

- `trazabilidad.py` y `reglas.py` con fixtures mínimos (spec/plan/tests de ejemplo; un diff
  con cada regla violada y uno limpio).
- `grep -ri 'juicio\|juez\|perito\|prontuario'` en el plugin sin resultados fuera de este
  spec.
- Correr `resolver-ticket` en un ticket real y comparar los tokens de `registro.md` contra
  una corrida de la 0.4.0.
