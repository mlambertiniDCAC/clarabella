# resolver-proyecto y resolver-ticket de 8 pasos — diseño

Fecha: 2026-10-09 · Base: 0.5.0 (branch `revision-en-vez-de-juicio`) · Versión objetivo: 0.6.0

## Problema

Los tickets de un mismo proyecto dependen entre sí (permisos-psp: E4, E5, E7, E8 y E9 se
consumen unos a otros), pero hoy cada ticket se planea, se revisa y se implementa por
separado. Los contratos entre tickets se cruzan tarde: T23822 terminó dependiendo de
contratos todavía no implementados. Y el juicio, además de caro, llegaba cuando ya se había
pagado el desarrollo.

## Objetivo

Dos modos, bien separados:

| Modo | Skill | Para qué |
|------|-------|----------|
| **Manual** | `resolver-ticket` | Un ticket, el usuario con el control, los 8 pasos de la 0.3.0 en la sesión principal, sin subagentes. Es el default |
| **Autónomo** | `resolver-proyecto` | Uno o más tickets relacionados (el **lote**), con subagentes, alineación y juicio antes de implementar. Absorbe a `ciclo-ticket` |

`resolver-proyecto` resuelve un **lote de tickets relacionados**: se planea y se testea cada uno,
se alinea el lote entero, se corrige con evidencia, se decide si la solución sirve **antes
de implementar**, y recién después se implementa y se testea en el orden de las
dependencias.

Un lote de un solo ticket es el modo autónomo de un ticket (lo que hacía `ciclo-ticket`):
`contratos.py` corre igual, el Alineador se saltea, y el juicio es opcional (lo decide el
usuario al armar el lote).

**Criterios de éxito**
- Los choques de contrato entre tickets aparecen antes de implementar (paso 3), no en GREEN.
- El juicio dictamina si la solución sirve, no si está bien hecha, y llega antes de
  implementar.
- RED y GREEN no gastan tokens: corren scripts.
- Nunca se retoma a un generador para corregir.
- Cada rol registra tokens y tiempo, para calibrar modelos y esfuerzo con datos.

## resolver-ticket: los 8 pasos de la 0.3.0

Vuelve el `resolver-ticket` de la 0.3.0 (commit `70055e7`): checklist en la sesión
principal, sin subagentes, con aprobación del usuario en cada paso. Usa las skills de hoy;
solo se ajustan las notas de los pasos que chocan con ellas.

| # | Paso | Skill | Ajuste respecto de la 0.3.0 |
|---|------|-------|-----------------------------|
| 0 | Fijar la carpeta del ticket | — | Igual. Los criterios de la spec se numeran `CA#` |
| 1 | Preparar repos | `preparar-repo` → `aislar-ticket` | Igual |
| 2 | Planear | `planear-ticket` | Cada Parte lleva `Cubre:` |
| 3 | Plan de tests | `planear-tests-ticket` | **Desde la spec, sin mirar el plan** (antes: "sobre el plan del paso 2"). Columna `Criterio` |
| 4 | Implementar | directo o `implementar-ticket` | Igual, con `mostrar-diff` en vivo |
| 5 | Validar | `testear-ticket` | Lo corre la sesión principal en modo GREEN (RED opcional antes del paso 4) |
| 6 | Revisar el diff | `mostrar-diff` | Igual |
| 7 | Resumen | `resumir-ticket` (restaurada de la 0.3.0) | Igual |
| 8 | Enviar a review | `enviar-review` | Igual |

Los scripts de la 0.5.0 no entran al flujo: el usuario los puede pedir cuando quiera
(`trazabilidad.py` después del paso 3, `reglas.py` antes del paso 6).

`planear-ticket`, `planear-tests-ticket`, `implementar-ticket` y `testear-ticket` mantienen
su modo de sesión principal (el de la 0.3.0) además del modo orquestado que usa
`resolver-proyecto`.

## resolver-proyecto

## La plataforma (verificado en la doc de Claude Code)

1. **Los subagentes pueden despachar subagentes**, hasta 3 capas debajo de la sesión
   principal (default desde v2.1.219; `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`). Este diseño
   usa 2: Coordinador → Implementador → Obrero.
2. **El Coordinador es un tipo de agente que corre como sesión principal:**
   `claude --agent clarabella:coordinador`. Modelo y esfuerzo quedan en su archivo.
3. **Cada rol es un tipo de agente del plugin** (`agents/*.md`) con `model` y `effort` en el
   frontmatter, `skills` para precargar su skill y `tools: Agent(tipo, …)` para limitar a
   quién puede despachar. Quien despacha lo hace por nombre de tipo y nunca elige modelo.

## Roles

| Rol | Tipo de agente | Modelo · esfuerzo | Lee | Escribe |
|-----|----------------|-------------------|-----|---------|
| Coordinador | `coordinador` (sesión principal, `--agent`), precarga `resolver-proyecto` | Haiku · medio | `estado.json`, contratos de salida | `estado.json`, `registro.md` |
| Escribano | `clarabella-escribano` | Sonnet · alto | spec del ticket | `escritura.md` |
| Generador de plan | `clarabella-generador-plan` | Sonnet · alto | spec, doc, código | `plan.md` con `## Contrato` |
| Generador de tests | `clarabella-generador-tests` | Sonnet · alto | spec, doc, DB (lectura) | `tests.md` |
| Alineador | `clarabella-alineador` | Opus · alto | contratos de todos los tickets, salidas de scripts, decisiones | `lote/alineacion.md` |
| Verificador | `clarabella-verificador` | Sonnet · medio | spec y plan de un ticket (no al generador) | `revision/verificacion.md` |
| Corrector | `clarabella-corrector` | Sonnet · medio | un artefacto + sus hallazgos | el artefacto corregido |
| Juez | sesión aparte | Opus · alto | `lote/fichas/`, `alineacion.md`, contratos | `lote/dictamen.md` |
| QA | `clarabella-qa` | Sonnet · alto | `tests.md`, entorno del ticket | `casos/<ms>/T##.sh` |
| Implementador | `clarabella-implementador` (despacha Obreros y Correctores) | Sonnet · medio | plan, `alineacion.md`, salida de `correr-casos.sh` | `revision/implementacion.md` (vueltas, clasificación de fallas) |
| Obrero | `clarabella-obrero` / `clarabella-obrero-alto` | Sonnet · medio (alto al escalar) | plan, Parte de su ms | código en su worktree, `revision/notas-<ms>.md` |
| Revisor | `revisar-ticket` (0.5.0) | Sonnet · medio | diff, plan, `reglas.py` | `revision/revision-impl-<ms>.md` |
| Cronista | `cronista` (0.5.0) | Sonnet | `hechos.md` | `cronica.md`, borradores |

**Quién despacha a quién:** el Coordinador despacha a todos los roles de los pasos 0 a 4 y,
en el paso 6, al QA y a un Implementador por ticket. El Implementador despacha a sus Obreros
y, para `hueco-del-plan` o `test-mal-documentado`, a un Corrector. Nadie más despacha.

**El Coordinador es mecánico.** Lee `estado.json`, despacha con prompts de plantilla y
reenvía rutas. No resume, no decide, no le cuenta nada al usuario con sus palabras: copia o
señala archivos. Lo que pide criterio lo hace un rol con modelo para eso.

## Carpetas

```
docs/{proyecto}/lotes/L-<AAAA-MM-DD>-<slug>/
├── estado.json        ← Coordinador: paso actual, estado por ticket, ids de agentes
├── registro.md        ← una fila por subagente (rol, modelo, esfuerzo, duración, tokens)
├── alineacion.md      ← Alineador
├── fichas/T#####.md   ← script fichas.py, para el juicio
├── dictamen.md        ← Juez (sesión aparte) + decisión del usuario
└── cierre.md          ← integración, deriva, medición
docs/{proyecto}/{tipo}/T#####-{slug}/   ← cada ticket, como en 0.5.0
└── casos/<ms>/T##.sh  ← QA
```

## El flujo

### Paso 0 — Armar el lote
El usuario da la lista de tickets. Por cada uno: carpeta, `spec.md`, Escribano (en
paralelo). Las escrituras de **todos** los tickets se le presentan al usuario en **una sola
ronda**. Después, numeración `CA#` (0.5.0).

### Pasos 1 y 2 — Generadores (en paralelo, ciegos entre sí)
Por ticket, un generador de plan y uno de tests, como en 0.5.0, con un agregado: el plan
lleva una sección `## Contrato`:

```markdown
## Contrato
### Expone
- `POST /internal/permisos/usuarios` — body `{usuarioId, sujetoId, …}` → 201
### Consume
- `GET /compliance/:id/permisos-psp` — de T23821
- `POST /internal/cuentas/:id/usuarios/sync-compliance` — existente
```

Contrato de salida de cada generador: `ARTEFACTO` (ruta), `DUDAS`, `ESTADO`. Las dudas van
al Baqueano (0.5.0).

### Paso 3 — Alineación
1. Scripts, 0 tokens: `trazabilidad.py` por ticket y **`contratos.py`** sobre el lote.
   `contratos.py` cruza cada `Consume` con un `Expone` de otro ticket del lote (por verbo y
   ruta), o lo acepta si dice `existente`; reporta consumos sin dueño, firmas que no
   coinciden y ciclos de dependencia; y calcula el **orden del lote** (orden topológico).
2. Alineador (Opus, alto), una pasada: lee las secciones `## Contrato`, las salidas de los
   scripts y las decisiones de cada spec. Abre un plan entero solo cuando un choque lo
   requiere. Escribe `alineacion.md`: choques (con fuente), orden del lote, y lo que el
   hilado no resuelve.

### Paso 4 — Corrección (CRITIC + Chain-of-Verification)
1. **Verificador** por ticket (Sonnet, medio), sin ver al generador ni su razonamiento:
   arma preguntas de verificación desde la spec ("¿qué devuelve si el permiso está
   revocado?") y las contesta leyendo solo el plan y los tests. Las respuestas que no salen
   del artefacto, o que contradicen la spec, son hallazgos.
2. **Corrector** nuevo por artefacto (Sonnet, medio), con los choques del Alineador y los
   hallazgos del verificador que le tocan, nada más. Desacuerdos: una línea al usuario.
3. **Verificación con scripts**: `trazabilidad.py` y `contratos.py` otra vez.
4. **Una vuelta.** Lo que siga abierto va al juicio como riesgo, no a otra ronda.

Nunca se retoma a un generador.

### Paso 5 — Juicio de valor (sesión aparte)
- `fichas.py` arma una ficha por ticket: qué pide, repos tocados, migraciones, contratos
  nuevos, decisiones tomadas sin el usuario (provisorias, menores), costo hasta acá.
- El usuario abre una **sesión aparte** con Opus, esfuerzo alto, y la skill `juzgar-proyecto`.
  El Juez no participó del lote: lee `fichas/`, `alineacion.md` y las secciones
  `## Contrato`, y escribe `dictamen.md`.
- **Dictamina si la solución sirve, no si está bien hecha:**
  1. ¿Resuelve el problema que originó los tickets?
  2. ¿El costo y la complejidad están a la altura del beneficio?
  3. ¿Hay una alternativa más simple que nadie consideró?
  4. ¿Qué riesgo deja (datos, permisos, módulo financiero, deuda técnica)?
- **Decide el usuario:** aprobar, recortar alcance (qué tickets salen o cambian) o frenar.
  La decisión queda en `dictamen.md`. El Coordinador espera en `esperando-juicio` y retoma
  con lo que diga el archivo.

### Paso 6 — Implementación y tests (en el orden del lote)
Por ticket, en orden topológico:
1. **Entorno por script** (`aislar-ticket` / `entorno-ticket`), sin modelo.
2. **QA** (Sonnet, alto), una vez por ticket: convierte cada caso de `tests.md` en
   `casos/<ms>/T##.sh` (curl, query, aserción; exit 0 pasa, 1 falla; imprime la evidencia
   cruda). Variables de entorno del ticket, sin valores fijos.
3. **RED = `correr-casos.sh`** (0 tokens). Los casos nuevos tienen que fallar y los de
   regresión pasar: eso valida también los scripts del QA. Un caso que no discrimina vuelve
   al QA.
4. **Implementador** (Sonnet, medio), uno por ticket, despachado por el Coordinador. Él:
   - despacha **un Obrero por microservicio**, en paralelo entre repos del ticket (nunca
     dos en el mismo repo);
   - corre **GREEN = `correr-casos.sh`** (0 tokens);
   - clasifica los casos que fallan con su salida cruda: `bug-implementacion` → el Obrero de
     ese repo; `hueco-del-plan`, `test-mal-documentado` → un Corrector nuevo;
     `ambiguedad-negocio` → lo devuelve al Coordinador para el usuario;
   - **escala:** el mismo caso falla en dos GREEN seguidos → el siguiente intento va a
     `clarabella-obrero-alto` con el diagnóstico;
   - lleva la firma de cada vuelta (estancamiento, `sin-progreso`) y vuelve al Coordinador
     con un resumen corto y la ruta de `revision/implementacion.md`.
5. Con GREEN completo: `revisar-ticket` modo implementación (0.5.0).

El siguiente ticket del orden arranca cuando el anterior está en GREEN.

### Lo que se hereda de `ciclo-ticket`
- **Presupuesto** (vueltas de GREEN, tokens, tiempo) al armar el lote, en `estado.json`.
- **Provisorias:** las dudas mayores que surgen después del juicio se toman con la opción
  más conservadora y el usuario las confirma o veta al final; nunca en terreno sensible
  (financiero, permisos, datos), que pausa.
- **Estancamiento:** misma firma (casos que fallan + hallazgos bloqueantes) tres GREEN
  seguidos → pausa con diagnóstico.
- **`sin-progreso`:** dos vueltas sin que bajen los `bug-implementacion` de un repo →
  diagnóstico, y si el enfoque estaba mal, `git stash push -u` y reescritura.
- **Pausas:** terreno sensible, corrección fallida dos veces, regresión preexistente,
  entorno caído, estancamiento, presupuesto.

### Paso 7 — Cierre del lote
1. **Integración:** `correr-casos.sh` con los casos de todos los tickets juntos.
2. **Deriva:** `contratos.py --deriva` verifica que cada `Expone` aprobado aparezca en el
   diff de su ms (ruta registrada), y `reglas.py` sobre cada diff.
3. **Medición:** `hechos.py` por ticket y agregado del lote, por rol y esfuerzo, en
   `cierre.md`. Es la base para calibrar Opus medio/alto y Sonnet medio/alto.
4. **Crónica** por ticket (0.5.0).
5. **Envío en orden:** `enviar-review` por ticket, apilados según el orden del lote, con
   aprobación explícita del usuario.
6. **Opcional — mutación de muestra:** romper una línea por ticket y verificar que algún
   caso falle.

## Piezas nuevas

| Pieza | Tipo |
|-------|------|
| `skills/resolver-proyecto/SKILL.md` | Skill del Coordinador: pasos, plantillas de prompts, `estado.json` |
| `skills/juzgar-proyecto/SKILL.md` | Skill del Juez para la sesión aparte |
| `agents/*.md` | Tipos de agente con modelo, esfuerzo, skill precargada y a quién despachan (tabla de roles) |
| `scripts/contratos.py` | Cruce Expone/Consume, orden topológico, `--deriva` |
| `scripts/fichas.py` | Fichas por ticket para el juicio |
| `scripts/correr-casos.sh` | Corre `casos/<ms>/T##.sh`, resume pasa/falla con salida cruda |
| `planear-ticket` | Sección `## Contrato` obligatoria |
| `skills/resolver-ticket/SKILL.md` | Vuelve el de la 0.3.0, con los ajustes de la tabla |
| `skills/resumir-ticket/SKILL.md` | Restaurada de la 0.3.0 |
| `skills/ciclo-ticket/` | Se elimina (absorbida por `resolver-proyecto`) |
| `skills/clarabella/SKILL.md` | "Ayudame con T#####" → `resolver-ticket`; "resolvé estos tickets", "resolvelo solo" → `resolver-proyecto` |
| `README.md`, `plugin.json` | Los dos modos; 0.6.0 |

Se reusan de 0.5.0: `trazabilidad.py`, `reglas.py`, `hechos.py`, `revisar-ticket`,
`escribano`, `baqueano`, `cronista`, `enviar-review`, `aislar-ticket`.

## Riesgos

- **Haiku como Coordinador:** si interpreta en vez de rutear, se equivoca. Mitigación:
  plantillas cerradas, estado en archivo, prohibido resumir. Si falla, la sesión se corre con
  Sonnet sin cambiar nada más.
- **Scripts de QA mal escritos:** el RED los valida (lo nuevo tiene que fallar), y lo que no
  discrimina vuelve al QA.
- **`contratos.py` depende del formato de `## Contrato`:** si el generador no lo respeta,
  el script sale con error de formato (como `trazabilidad.py`) y lo arregla el corrector.
- **La 0.5.0 todavía no se probó en un ticket real.** El primer lote es también esa prueba.

## Fuera de alcance

- `pipeline-desarrollo` y el dashboard.

## Verificación

- Tests de `contratos.py` (consumo sin dueño, firma distinta, ciclo, orden topológico,
  deriva), `fichas.py` y `correr-casos.sh`.
- `resolver-ticket`: un ticket chico de punta a punta en modo manual, verificando que
  ningún paso despache subagentes y que el paso 7 use `resumir-ticket`.
- Un lote real chico (2-3 tickets con una dependencia entre ellos) y comparar `cierre.md`
  contra la corrida de T23815: tokens por rol, contexto retomado (debería ser ~0), choques
  detectados antes de implementar.
