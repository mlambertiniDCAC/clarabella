---
name: resolver-ticket
description: Usar cuando el usuario quiere resolver un ticket (de desarrollo o de soporte) del workspace dcac-ia-context desde el chat, con revisión suya en cada fase — preparación (repos, plan y tests por agentes generativos separados), juicio (Juez, defensa y peritos), implementación (RED, código, GREEN, diff) y entrega (resumen, review, bajar entorno). Triggers — "resolvamos T##### paso a paso", "arranquemos T##### de forma manual", "hagamos T##### sin el pipeline". NO confundir con pipeline-desarrollo (motor autónomo con dashboard); acá el usuario decide en el chat.
---

# Resolver ticket

Checklist de las cuatro fases de un ticket (desarrollo o soporte), resuelto desde el chat
con el usuario presente — sin dashboard (eso es `pipeline-desarrollo`).

| Fase | Qué pasa | Termina cuando |
|------|----------|----------------|
| **1. Preparación** | Repos listos; un agente generativo escribe el plan y otro los tests, sin verse | Los dos entregaron y sus DUDAS están respondidas |
| **2. El juicio** | Un Juez juzga plan y tests contra la doc y entre sí; los agentes se defienden; peritos verifican; lo que el Juez sostiene lo corrige el mismo agente, solo en lo marcado | El usuario aprueba la sentencia y los dos artefactos |
| **3. La implementación** | RED, implementación (en paralelo por repo si conviene), GREEN, juicio de la implementación, diff para validar | El usuario valida el diff y la sentencia |
| **4. La entrega** | Resumen, review, bajar el entorno | La review salió y el entorno está abajo |

**Modo ciclo, el default.** El objetivo es que el ticket se desarrolle solo, sin
intervención humana: salvo que el usuario pida explícitamente ir paso a paso, usá
`ciclo-ticket`. Mismas piezas, pero cada falla vuelve a quien la causó en vez de al
usuario, las decisiones se toman como provisorias y el usuario ve el resultado al final.
Lo que sigue (aprobaciones por fase) es el modo manual, solo cuando el usuario lo pide.

**El hilo principal es el orquestador.** Despacha subagentes, rutea mensajes y le lleva
al usuario las decisiones. En las fases 1 y 2 no genera ni defiende nada; en la fase 3
implementa. No reemplaza el criterio de cada skill: cada una trae sus reglas, leelas al
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

En la **raíz del workspace dcac-ia-context**:

```
docs/{proyecto}/{tipo}/T#####-{slug}/
├── spec.md      ← paso 0 (texto del ticket, sin editar; después, decisiones de contrato)
├── escritura.md ← paso 0 (escribano)
├── plan.md      ← fase 1, agente generativo del plan
├── tests.md     ← fase 1, agente generativo de los tests
├── registro.md  ← todo el proceso: cada subagente despachado, modelo, duración, tokens
├── juicio/      ← fases 1-3 (bitácoras, consultas, acusaciones, defensas, peritajes,
│                  sentencias, correcciones, testeo/ con los reportes de RED y GREEN)
├── cronica.md   ← fase 4 (cronista)
└── borradores/  ← fase 4 (arc diff, comentario del ticket, decisiones nuevas)
```

Creala, guardá la spec y pasales `proyecto`, `tipo`, `T#####` y `slug` a cada skill y
subagente. Si la sesión no está en la raíz del workspace, usá rutas absolutas.

**Llevá el registro desde el primer subagente.** Por cada uno que despaches, una fila en
`registro.md` (rol, modelo, resultado) y, cuando termina, la duración y los
tokens que informe su notificación. Guardá también cada reporte de RED y GREEN en
`juicio/testeo/` (`red.md`, `green-1.md`, …). El Cronista solo cuenta lo que quedó
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
Los dos reciben las reglas del oficio de `juicio-ticket` (§ El oficio de un agente
generativo): copialas en su prompt. **Guardá el id de cada uno**: en el juicio se los
retoma con `SendMessage` para que se defiendan y corrijan.

Despachá los dos en el mismo mensaje. Cada uno explora por su cuenta lo que necesita.

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Agente de tests T#####",
      prompt: "<reglas del oficio: tests>
               Invocá la skill clarabella:planear-tests-ticket en modo orquestado, como
               agente generativo de juicio-ticket, para T##### (proyecto {proyecto}, tipo
               {tipo}, slug {slug}). Única fuente: spec.md. No leas plan.md. Escribí tests.md
               y juicio/bitacora-tests.md. Devolvé ARTEFACTO/DUDAS/SUGERENCIAS/ESTADO.")

Agent(subagent_type: "general-purpose", model: "opus", description: "Agente del plan T#####",
      prompt: "<reglas del oficio: plan>
               Invocá la skill clarabella:planear-ticket en modo orquestado, como agente
               generativo de juicio-ticket, para T##### (proyecto {proyecto}, tipo {tipo},
               slug {slug}). Fuente: spec.md. Worktrees en .worktrees/T#####-{slug}/. No leas
               tests.md. Escribí plan.md y juicio/bitacora-plan.md. Devolvé
               ARTEFACTO/DUDAS/SUGERENCIAS/ESTADO.")
```

**Exploradores, solo con tres repos o más.** Con uno o dos, el agente del plan lee el
código igual, y los exploradores son gasto doble. Con tres o más, despachá primero un
`Explore` por repo (`model: "haiku"`), en paralelo, con el objetivo del ticket (no una
hipótesis de solución); guardá cada mapa en `juicio/exploracion-<ms>.md` y pasáselos al
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

La fase 1 termina cuando los dos entregaron su artefacto y su bitácora.

## Fase 2 — El juicio

Invocá `juicio-ticket` y seguí su procedimiento. Lo que te toca como orquestador:

1. Despachar al Juez (ronda 1) y guardar su id.
2. Retomar a los dos agentes para su defensa, en paralelo (ronda 2), cada uno con su
   acusación y nada más.
3. Retomar al Juez para la orden de peritaje (ronda 3).
4. Despachar los peritos en paralelo (ronda 4) y rutear sus interrogatorios al agente
   correspondiente, textuales. **No leas los peritajes.**
5. Retomar al Juez para la sentencia (ronda 5).
6. Corrección (ronda 6): retomar a cada agente con observaciones sostenidas para que
   corrija **solo esas**, y al Juez para que verifique **solo los cambios**. Si una falta es
   del Baqueano, primero corrige él la respuesta y después el agente actualiza lo que
   dependía de ella.
7. Llevarle al usuario la sentencia, copiando las posiciones textuales de
   `juicio/sentencia.md`, incluidas las correcciones que fallaron dos veces. Si el ticket se
   frena ahí, igual despachá al `cronista`: la crónica cuenta hasta dónde se llegó y por
   qué.

La fase 2 termina cuando el usuario aprueba la sentencia y la versión final de `plan.md` y
`tests.md`.

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
implementa anota en `juicio/implementacion/bitacora-<ms>.md` lo que no sale literal del
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
               contenedor T#####-<ms>. Escribí juicio/implementacion/bitacora-<ms>.md.
               Devolvé el contrato de la skill.")
```

**Guardá el id de cada implementador:** en el juicio de la implementación se los retoma
para que se defiendan, y para corregir lo que el Juez sostenga. Sus DUDAS van al usuario.

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
- `test-mal-documentado` → decide el usuario. Después de un juicio es raro: anotalo para
  el resumen, porque el juicio no lo detectó.
- `ambiguedad-negocio` → DUDA para el usuario.

Si no estás de acuerdo con una clasificación, presentá las dos lecturas al usuario. Más de
2-3 vueltas con el mismo caso → frená y escalá.

### 3.4 Juicio de la implementación
Con GREEN completo, la implementación va a juicio (`juicio-ticket` § Juicio de la
implementación): el Juez revisa el diff de cada repo contra el plan aprobado, las reglas
críticas del workspace y las convenciones, que es lo que GREEN no ve. Los implementadores
se defienden, los peritos verifican para el Juez y el Juez sentencia. Lo sostenido lo
corrige el implementador y corre un GREEN nuevo. Si implementaste vos, al presentar la
sentencia copiá las posiciones textuales.

### 3.5 Exponer los cambios
El usuario valida el diff en `mostrar-diff` junto con la sentencia de la implementación.
La fase 3 termina con su OK.

## Fase 4 — La entrega

| Paso | Skill | Nota |
|------|-------|------|
| 4.1 Crónica | `cronista` (subagente nuevo) | Escribe `cronica.md` y los `borradores/`. El usuario la lee y la valida; con su OK, agregás `borradores/decisiones-nuevas.md` al final de `docs/{proyecto}/decisiones.md` |
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
  orquestador no genera ni defiende.
- **Pasarle a un agente generativo el artefacto del otro, o tu análisis** → se rompe la
  independencia. El único canal entre ellos es `## Decisiones de contrato` en `spec.md`.
- **Responder vos las DUDAS de un agente** → van al usuario.
- **Empezar el juicio con un solo agente presentado** → el juicio arranca con los dos.
- **Leer, resumir o mencionar un peritaje** → son del Juez.
- **Resumir la sentencia o tomar partido** → al usuario se le copian las posiciones
  textuales.
- **Rehacer un artefacto entero por lo que marcó el Juez** → se corrige solo lo marcado.
- **Despachar exploradores en un ticket de uno o dos repos** → gasto doble: el agente del
  plan lee el código igual.
- **Esperar a que el entorno Docker esté arriba para empezar la fase 1** → la etapa B va en
  background.
- **Saltarse el RED** → sin él no sabés si un test en verde prueba algo.
- **Implementar en paralelo por módulo dentro del mismo repo** → se pisan; el paralelo es
  por repo.
- **Paralelizar sin contrato fijado** → cada implementador adivina lo que hace el otro.
- **Saltarse el juicio de la implementación porque GREEN pasó** → GREEN no ve estado en
  propiedades de clase, tablas ajenas ni desvíos del plan.
- **Correr el GREEN en el hilo principal** → quien escribió el código no es quien mejor lo
  juzga.
- **Reescribir un test para que pase con lo implementado** → solo si el usuario lo decide.
- **Levantar `mostrar-diff` recién al final** → levantalo antes del primer archivo.
- **Codear en `microservicios/<ms>` en vez del worktree** → rompe el aislamiento.
- **Usar `enviar-cambios` en vez de `enviar-review`** → `enviar-cambios` es la del pipeline.
- **Dejar el entorno prendido después de la review** → la VM de Docker es chica; ese es el
  paso 4.3.
