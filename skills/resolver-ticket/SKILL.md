---
name: resolver-ticket
description: Usar cuando el usuario quiere resolver un ticket (de desarrollo o de soporte) del workspace dcac-ia-context desde el chat, con revisión suya en cada fase — preparación (repos, plan y tests por agentes generativos separados), revisión (trazabilidad, reglas y un revisor de una pasada), implementación (RED, código, GREEN, revisión, diff) y entrega (crónica, review, bajar entorno). Triggers — "resolvamos T##### paso a paso", "arranquemos T##### de forma manual", "hagamos T##### sin el pipeline". NO confundir con pipeline-desarrollo (motor autónomo con dashboard); acá el usuario decide en el chat.
---

# Resolver ticket

Checklist de las cuatro fases de un ticket (desarrollo o soporte), resuelto desde el chat
con el usuario presente — sin dashboard (eso es `pipeline-desarrollo`).

| Fase | Qué pasa | Termina cuando |
|------|----------|----------------|
| **1. Preparación** | Repos listos; un agente generativo escribe el plan y otro los tests, sin verse | Los dos entregaron y sus DUDAS están respondidas |
| **2. Revisión** | Trazabilidad de criterios (script), un revisor sonnet de una pasada, corrección por un agente nuevo | El usuario aprueba plan y tests |
| **3. La implementación** | RED, implementación (en paralelo por repo si conviene), GREEN, reglas críticas (script) y revisión del diff | El usuario valida el diff |
| **4. La entrega** | Crónica, review, bajar el entorno | La review salió y el entorno está abajo |

**Modo ciclo, el default.** El objetivo es que el ticket se desarrolle solo, sin
intervención humana: salvo que el usuario pida explícitamente ir paso a paso, usá
`ciclo-ticket`. Mismas piezas, pero cada falla vuelve a quien la causó en vez de al
usuario, las decisiones se toman como provisorias y el usuario ve el resultado al final.
Lo que sigue (aprobaciones por fase) es el modo manual, solo cuando el usuario lo pide.

**El hilo principal es el orquestador.** Despacha subagentes, rutea mensajes y le lleva
al usuario las decisiones. En las fases 1 y 2 no genera nada (salvo arreglos de formato que
pidan los scripts); en la fase 3 implementa. No reemplaza el criterio de cada skill: cada una trae sus reglas, leelas al
invocarlas.

## Paso 0 — Fijar la carpeta del ticket

Definí con el usuario (preguntá lo que no venga en el pedido o el ticket):

- **Ticket** `T#####` y un título corto → `{slug}` en kebab-case, sin tildes ni ñ.
- **Tipo**: `desarrollo` o `soporte`.
- **Proyecto**: una carpeta de `docs/`. Listá las existentes y preguntá cuál, o si hay que
  crear una nueva.
- **Texto del ticket**: la descripción y los criterios de aceptación tal cual vienen. Es la
  **spec**, la fuente de los dos agentes generativos. Si no trae criterios claros,
  preguntá antes de seguir.

**Escritura.** Con la spec guardada, despachá al `escribano` antes que a nadie. Lo que liste
(puntos abiertos, contradicciones, huecos de contrato, precedentes para vetar) se lo
presentás al usuario en una sola ronda; sus respuestas van a `spec.md` § Decisiones de
contrato. Los agentes arrancan con la spec escriturada, y las dudas que les queden van al
Baqueano.

Con la escritura cerrada, el Escribano numera los criterios de `spec.md` (`CA1…CAn`): la
trazabilidad de la fase 2 cruza esos números.

En la **raíz del workspace dcac-ia-context**:

```
docs/{proyecto}/{tipo}/T#####-{slug}/
├── spec.md      ← paso 0 (texto del ticket, sin editar; después, decisiones de contrato)
├── escritura.md ← paso 0 (escribano)
├── plan.md      ← fase 1, agente generativo del plan
├── tests.md     ← fase 1, agente generativo de los tests
├── registro.md  ← todo el proceso: cada subagente despachado, modelo, duración, tokens
├── revision/    ← fases 1-3 (consultas del Baqueano, trazabilidad, reglas, revisiones,
│                  notas de los implementadores, testeo/ con RED y GREEN, hechos.md)
├── cronica.md   ← fase 4 (cronista)
└── borradores/  ← fase 4 (arc diff, comentario del ticket, decisiones nuevas)
```

Creala, guardá la spec y pasales `proyecto`, `tipo`, `T#####` y `slug` a cada skill y
subagente. Si la sesión no está en la raíz del workspace, usá rutas absolutas.

**Llevá el registro desde el primer subagente.** Por cada uno que despaches, una fila en
`registro.md` (rol, modelo, resultado) y, cuando termina, la duración y los
tokens que informe su notificación. Guardá también cada reporte de RED y GREEN en
`revision/testeo/` (`red.md`, `green-1.md`, …). El Cronista solo cuenta lo que quedó
registrado.

## Fase 1 — Preparación

### 1.1 Repos (hilo principal)
`preparar-repo` (todos los repos en paralelo) → `aislar-ticket` **etapa A** (worktrees).
Rápido: no levanta Docker.

### 1.2 Entorno Docker (subagente en background)
Apenas termina el 1.1, despachá la etapa B y no la esperes. Tiene que estar lista para el
RED (fase 3).

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Entorno Docker T#####",
      prompt: "Invocá la skill clarabella:aislar-ticket y ejecutá SOLO la etapa B para T#####
               (slug {slug}), repos: <ms1>, <ms2>. Los worktrees ya existen en
               .worktrees/T#####-{slug}/<ms>. Levantá los contenedores de a uno. No toques
               infra compartida: ante cualquier problema, frená y devolvé DUDAS.
               Devolvé ARTEFACTO/DUDAS/SUGERENCIAS/ESTADO.")
```

### 1.3 Los agentes generativos (subagentes en paralelo)
Cada uno trabaja solo desde `spec.md` y no ve el artefacto del otro. **Guardá el id de cada
uno** solo para pasarle las respuestas a sus DUDAS durante esta fase: después no se los
retoma (la revisión y las correcciones las hacen agentes nuevos).

Despachá los dos en el mismo mensaje. Cada uno explora por su cuenta lo que necesita.

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Agente de tests T#####",
      prompt: "Invocá la skill clarabella:planear-tests-ticket en modo orquestado, como
               agente generativo, para T##### (proyecto {proyecto}, tipo {tipo}, slug
               {slug}). Única fuente: spec.md. No leas plan.md. Escribí tests.md (columna
               Criterio con los CA# de spec.md). Devolvé ARTEFACTO/DUDAS/SUGERENCIAS/ESTADO.")

Agent(subagent_type: "general-purpose", model: "opus", description: "Agente del plan T#####",
      prompt: "Invocá la skill clarabella:planear-ticket en modo orquestado, como agente
               generativo, para T##### (proyecto {proyecto}, tipo {tipo}, slug {slug}).
               Fuente: spec.md. Worktrees en .worktrees/T#####-{slug}/. No leas tests.md.
               Escribí plan.md (línea Cubre: en cada Parte). Devolvé
               ARTEFACTO/DUDAS/SUGERENCIAS/ESTADO.")
```

**Exploradores, solo con tres repos o más.** Con uno o dos, el agente del plan lee el
código igual, y los exploradores son gasto doble. Con tres o más, despachá primero un
`Explore` por repo (`model: "haiku"`), en paralelo, con el objetivo del ticket (no una
hipótesis de solución); guardá cada mapa en `revision/exploracion-<ms>.md` y pasáselos al
agente del plan en su prompt.

**Las DUDAS** de los agentes: primero filtrás vos lo que ya está contestado en la
escritura o en `spec.md` (se lo respondés al agente citando el punto). Lo que requiere
buscar en las fuentes va al **Baqueano** (`baqueano`, `model: "sonnet"`), uno por agente,
en paralelo, que clasifica cada duda:
- `RESPONDIDA` → se la pasás al agente con `SendMessage` y sigue.
- `PRECEDENTE` (el usuario ya lo decidió antes) → se la pasás al agente y se la mostrás al
  usuario en una lista corta, con derecho a veto.
- `AL USUARIO` → la juntás con las del otro Baqueano y se la presentás al usuario con el
  caso armado. Lo que decida va a `spec.md`, en `## Decisiones de contrato`, y se lo pasás
  **a los dos** agentes. Ese es el único canal entre ellos.

Vos no respondés dudas: ni las de los agentes ni las que el Baqueano manda al usuario.

La fase 1 termina cuando los dos entregaron su artefacto.

## Fase 2 — Revisión

Invocá `revisar-ticket` en modo plan-tests y seguí su procedimiento:

1. `trazabilidad.py` → `revision/trazabilidad.txt`. Los errores de formato y las líneas
   `Cubre:` faltantes los arreglás vos; un criterio sin Parte o sin caso es hallazgo
   bloqueante.
2. Un revisor sonnet nuevo, una pasada → `revision/revision-plan-tests.md`.
3. Si hay hallazgos: un sonnet nuevo corrige `plan.md` y otro `tests.md` (en paralelo),
   cada uno con sus hallazgos y nada más. Los triviales los corregís vos. **No retomes a los
   agentes generativos.**
4. `trazabilidad.py` otra vez.
5. Le presentás al usuario los hallazgos (copiados, sin resumir), qué se corrigió y los
   DESACUERDOS, uno por línea. Lo que decida va a `spec.md` § Decisiones de contrato y, si
   cambia un artefacto, lo aplica un sonnet nuevo.

La fase 2 termina cuando el usuario aprueba `plan.md` y `tests.md`.

## Fase 3 — La implementación

### 3.1 RED (subagente nuevo)
Con el entorno de la etapa B arriba, sobre el código de master (worktree sin cambios):

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "RED T#####",
      prompt: "Invocá la skill clarabella:testear-ticket en modo orquestado, modo RED, para
               T##### (proyecto {proyecto}, tipo {tipo}, slug {slug}). Worktrees:
               .worktrees/T#####-{slug}/<ms> (todavía sin cambios). Contenedores:
               T#####-<ms>, DB: T#####-db. No leas plan.md. No modifiques código ni
               tests.md. Devolvé el contrato de la skill.")
```

Los casos nuevos tienen que fallar y los de regresión pasar. Lo que no dé así
(`test-no-discrimina`, `regresion-preexistente`, `test-mal-documentado`) se lo mostrás al
usuario antes de implementar.

### 3.2 Implementar
**En el worktree** (`.worktrees/T#####-{slug}/<ms>`), nunca en `microservicios/<ms>`. El
objetivo es pasar a GREEN los casos que fallaron en RED, siguiendo el plan aprobado. Quien
implementa anota en `revision/notas-<ms>.md` lo que no sale literal del
plan (ver `implementar-ticket`).

Dos modos:

| Modo | Cuándo | Quién |
|------|--------|-------|
| **Hilo principal** (default) | Un repo, o varios con cambios chicos | Vos, directo o con `implementar-ticket` |
| **En paralelo por repo** | Dos o más repos con trabajo real, contrato fijado en `spec.md`, plan partido en una Parte por repo. Preguntale al usuario antes | Un subagente por repo, despachados en el mismo mensaje |

En paralelo:

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Implementar <ms> T#####",
      prompt: "Invocá la skill clarabella:implementar-ticket en modo orquestado, en paralelo
               por repo, para T##### (proyecto {proyecto}, tipo {tipo}, slug {slug}). Tu repo:
               <ms>, worktree .worktrees/T#####-{slug}/<ms>. Implementá solo la Parte <N>
               del plan. Contrato: spec.md § Decisiones de contrato. Reiniciá solo tu
               contenedor T#####-<ms>. Anotá los desvíos del plan en revision/notas-<ms>.md.
               Devolvé el contrato de la skill.")
```

**Guardá el id de cada implementador:** se los retoma para corregir los bugs de GREEN y los
hallazgos de la revisión. Sus DUDAS van al usuario.

**Por repo, no por módulo:** dos agentes en el mismo worktree se pisan en los archivos de
registro (rutas, DI, módulos) y en los reinicios del contenedor.

Antes del primer archivo, levantá un `mostrar-diff` en vivo **por worktree** (cada uno toma
el primer puerto libre):

```bash
python3 -u ${CLAUDE_PLUGIN_ROOT}/skills/mostrar-diff/serve.py --repo .worktrees/T#####-{slug}/<ms> --base master \
  > /tmp/diff_preview_<ms>.log 2>&1 &
disown
sleep 1 && cat /tmp/diff_preview_<ms>.log
```

El `--repo` apunta al worktree. Cada archivo que se edite aparece solo en el próximo
refresh.

### 3.3 GREEN (subagente nuevo en cada corrida)

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "GREEN T#####",
      prompt: "Invocá la skill clarabella:testear-ticket en modo orquestado, modo GREEN, para T#####
               (proyecto {proyecto}, tipo {tipo}, slug {slug}). Worktrees:
               .worktrees/T#####-{slug}/<ms>. Contenedores: T#####-<ms>, DB: T#####-db.
               No modifiques código ni tests.md. Devolvé el contrato de la skill.")
```

No le expliques qué implementaste. Con el reporte:
- `bug-implementacion` → corrige quien implementó ese repo (vos o su subagente, con
  `SendMessage`) y despachás **otro** subagente de GREEN.
- `hueco-del-plan` → decide el usuario si se amplía el plan o el criterio queda fuera.
- `test-mal-documentado` → decide el usuario. Anotalo: la revisión no lo detectó. Lo
  corrige un sonnet nuevo y se repite el RED de ese caso.
- `ambiguedad-negocio` → DUDA para el usuario.

Si no estás de acuerdo con una clasificación, presentá las dos lecturas al usuario. Más de
2-3 vueltas con el mismo caso → frená y escalá.

### 3.4 Revisión de la implementación
Con GREEN completo, `revisar-ticket` en modo implementación, un revisor por repo en
paralelo: `reglas.py` sobre el snapshot del worktree (incluye archivos nuevos) y un revisor
sonnet con el diff, el plan, las alertas y las notas. Los bloqueantes los corrige quien
implementó ese repo; si cambió código, otro GREEN y otra vez `reglas.py`. No hay segunda
revisión.

### 3.5 Exponer los cambios
El usuario valida el diff en `mostrar-diff` junto con las revisiones de la implementación.
La fase 3 termina con su OK.

## Fase 4 — La entrega

| Paso | Skill | Nota |
|------|-------|------|
| 4.1 Crónica | `cronista` (subagente nuevo) | Antes, armá los hechos: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hechos.py {ticket} --worktree .worktrees/T#####-{slug}/<ms> … > {ticket}/revision/hechos.md`. Escribe `cronica.md` y los `borradores/`. El usuario la lee y la valida; con su OK, agregás `borradores/decisiones-nuevas.md` al final de `docs/{proyecto}/decisiones.md` |
| 4.2 Review | `enviar-review` | Con los `borradores/arc-diff-<ms>.md` como base del mensaje, y solo con la aprobación explícita del usuario en el chat |
| 4.3 Bajar el entorno | `bajar-entorno` | Cuando el usuario dice que cerramos. Worktree y branch quedan hasta que la review aterrice |

## Gate de sensibilidad

Ante cualquier ambigüedad de documentación o de negocio (sobre todo si toca el módulo
financiero, `ms-decampopagos`/DCP), **frená y preguntale al usuario**. Los subagentes no
pueden preguntar: devuelven DUDAS. Vos se las llevás al usuario sin responderlas por él.

## Errores comunes

- **Confundir esto con `pipeline-desarrollo`** → esa es la corrida con dashboard. Acá el
  usuario decide en el chat.
- **Escribir el plan en el hilo principal** → el plan lo escribe un agente generativo; el
  orquestador no genera.
- **Pasarle a un agente generativo el artefacto del otro, o tu análisis** → se rompe la
  independencia. El único canal entre ellos es `## Decisiones de contrato` en `spec.md`.
- **Responder vos las DUDAS de un agente** → van al usuario.
- **Retomar a un agente generativo para corregir** → corrige un sonnet nuevo con el
  artefacto y los hallazgos.
- **Pedirle al revisor que verifique cobertura o reglas a mano** → eso lo hacen
  `trazabilidad.py` y `reglas.py`.
- **Resumir los hallazgos o tomar partido** → al usuario se le copian textuales.
- **Rehacer un artefacto entero por un hallazgo** → se corrige solo lo marcado.
- **Despachar exploradores en un ticket de uno o dos repos** → gasto doble: el agente del
  plan lee el código igual.
- **Esperar a que el entorno Docker esté arriba para empezar la fase 1** → la etapa B va en
  background.
- **Saltarse el RED** → sin él no sabés si un test en verde prueba algo.
- **Implementar en paralelo por módulo dentro del mismo repo** → se pisan; el paralelo es
  por repo.
- **Paralelizar sin contrato fijado** → cada implementador adivina lo que hace el otro.
- **Saltarse la revisión de la implementación porque GREEN pasó** → GREEN no ve estado en
  propiedades de clase, tablas ajenas ni desvíos del plan.
- **Revisar con `git diff master`** → no ve los archivos nuevos; `revisar-ticket` usa el
  snapshot.
- **Correr el GREEN en el hilo principal** → quien escribió el código no es quien mejor lo
  juzga.
- **Reescribir un test para que pase con lo implementado** → solo si el usuario lo decide.
- **Levantar `mostrar-diff` recién al final** → levantalo antes del primer archivo.
- **Codear en `microservicios/<ms>` en vez del worktree** → rompe el aislamiento.
- **Usar `enviar-cambios` en vez de `enviar-review`** → `enviar-cambios` es la del pipeline.
- **Dejar el entorno prendido después de la review** → la VM de Docker es chica; ese es el
  paso 4.3.
