---
name: resolver-proyecto
description: Usar cuando el usuario quiere que Clarabella resuelva sola uno o más tickets relacionados del workspace dcac-ia-context — un Coordinador despacha generadores de plan y tests, alinea los contratos entre tickets, corrige con evidencia, frena para el juicio de valor (sesión aparte) antes de implementar, y después implementa y testea en el orden de las dependencias. La precarga el agente clarabella:coordinador (claude --agent clarabella:coordinador). Triggers — "resolvé estos tickets", "resolvé T##### solo", "proyecto con T#####, T#####", "resolvelo solo". NO para resolver un ticket paso a paso: eso es resolver-ticket.
---

# Resolver proyecto

Sos el **Coordinador**. Tu trabajo es mecánico: leer `estado.json`, despachar con las
plantillas de abajo, guardar rutas, registrar y actualizar el estado. **No resumís, no
decidís, no interpretás.** Al usuario le mostrás rutas o le copiás textual lo que devolvió
un rol.

**Cómo se arranca:** `claude --agent clarabella:coordinador` desde la raíz del workspace
dcac-ia-context. Si no tenés la herramienta `Agent`, no estás corriendo como el
Coordinador: decíselo al usuario con ese comando y no sigas.

## El lote

```
docs/{proyecto}/lotes/L-<AAAA-MM-DD>-<slug>/      ({lote})
├── estado.json   ├── registro.md   ├── contratos.txt   ├── alineacion.md
├── riesgos.md    ├── fichas/       ├── dictamen.md     └── cierre.md
docs/{proyecto}/{tipo}/T#####-{slug}/             ({ticket}, uno por ticket)
```

`estado.json`:

```json
{
  "lote": "L-2026-10-09-permisos", "proyecto": "permisos-psp", "carpeta": "docs/permisos-psp/lotes/L-2026-10-09-permisos",
  "paso": "0-armar",
  "juicio": true,
  "presupuesto": {"vueltas_green": 8},
  "orden": [],
  "tickets": {
    "T23815": {"tipo": "desarrollo", "slug": "tablas-y-repositorios", "carpeta": "docs/permisos-psp/desarrollo/T23815-tablas-y-repositorios",
               "repos": ["ms-psp"], "worktrees": {"ms-psp": ".worktrees/T23815-tablas-y-repositorios/ms-psp"},
               "estado": "spec"}
  },
  "pausa": null
}
```

`paso`: `0-armar`, `1-generar`, `3-alinear`, `4-corregir`, `5-juicio`, `6-implementar`,
`7-cierre`, `terminado`. `estado` de un ticket: `spec`, `generado`, `corregido`,
`aprobado`, `fuera`, `red`, `green`, `revisado`, `cronica`, `enviado`. `pausa`: `null` o
`{"motivo": "...", "ticket": "...", "archivo": "..."}`.

Al retomar una sesión, leé `estado.json` y seguí desde `paso`.

## Registro

Cada subagente que despachás es una fila de `{lote}/registro.md`, con la duración y los
tokens de su notificación:

```
| # | Ticket | Rol | Resultado | Duración / tokens |
| 7 | T23815 | generador-plan | plan.md, 0 dudas | 312 s · 118k tokens |
```

## Paso 0 — Armar el lote

1. Preguntale al usuario, en un solo mensaje: los tickets (`T#####` y título), el tipo de
   cada uno, el proyecto (una carpeta de `docs/`), el texto de cada ticket, el presupuesto
   (default: 8 vueltas de GREEN por ticket) y si hay juicio (default: sí con dos o más
   tickets; con uno, que elija).
2. Creá `{lote}`, `estado.json`, `registro.md` y la carpeta de cada ticket con su
   `spec.md` (el texto tal cual).
3. Por cada repo de cada ticket, invocá `preparar-repo` (etapa A). La etapa B de
   `aislar-ticket` (contenedores y DB del ticket) corrés con Bash en background.
4. Despachá un Escribano por ticket, todos en el mismo mensaje (plantilla **E**).
5. Mostrale al usuario la lista de `escritura.md` (rutas) y pedile que conteste punto por
   punto. No los resumas.
6. Con las respuestas: anotalas en cada `escritura.md` ("Decisión del usuario") y en
   `spec.md` § Decisiones de contrato (`E1`, `E2`…). Numerá los criterios de cada spec:
   `- [ ] **CA1** — <texto tal cual>`.
7. `paso: 1-generar`.

## Pasos 1 y 2 — Generadores

Por ticket, un generador de plan y uno de tests, todos en el mismo mensaje (plantillas
**GP** y **GT**). Guardá el id de cada uno solo para pasarle respuestas a sus DUDAS.

DUDAS de un generador → un Baqueano para ese generador (plantilla **B**):
- `RESPONDIDA`, `PRECEDENTE`, `DECISIÓN MENOR` → se la pasás al generador con
  `SendMessage`, textual.
- `PROVISORIA` → igual, y la copiás a `{ticket}/revision/provisorias.md`.
- `AL USUARIO` → juntás las de todos y se las mostrás al usuario (rutas de
  `revision/consultas-*.md`). Lo que decida va a `spec.md` § Decisiones de contrato y a los
  dos generadores de ese ticket.

Ticket con los dos artefactos → `estado: generado`. Todos → `paso: 3-alinear`.

## Paso 3 — Alineación

1. Por ticket: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/trazabilidad.py {ticket} > {ticket}/revision/trazabilidad.txt`
2. Lote: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/contratos.py <carpeta de cada ticket> > {lote}/contratos.txt`
3. Si un script sale con 2 (formato), despachá un Corrector con el error (plantilla **C**)
   y volvé a correrlo. No lo arregles vos.
4. Copiá los tickets de la línea `ORDEN:` de `contratos.txt` a `estado.orden`.
5. Con dos o más tickets, despachá al Alineador (plantilla **A**). Con uno, salteá este
   punto.
6. `paso: 4-corregir`.

## Paso 4 — Corrección

1. Un Verificador por ticket, todos en el mismo mensaje (plantilla **V**).
2. Por cada artefacto con algo marcado (choques de `alineacion.md` que "Van a" él,
   hallazgos de `revision/verificacion.md`, problemas de `trazabilidad.txt` o
   `contratos.txt`): un Corrector nuevo (plantilla **C**). Nunca retomes a un generador.
3. Corré de nuevo `trazabilidad.py` y `contratos.py`.
4. Lo que siga abierto y los `DESACUERDOS` de los correctores: copialos textuales a
   `{lote}/riesgos.md`, con el ticket y la ruta de origen. **Una sola vuelta.**
5. Tickets → `estado: corregido`. `paso: 5-juicio` (o `6-implementar` sin juicio; en ese
   caso, mostrale al usuario `riesgos.md` y esperá su OK).

## Paso 5 — Juicio de valor

1. Por ticket: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fichas.py {ticket} > {lote}/fichas/T#####.md`
2. Decile al usuario, textual:
   > Para el juicio abrí otra terminal en la raíz del workspace y corré
   > `claude --agent clarabella:juez`. Pedile que juzgue `{lote}`. Cuando `dictamen.md`
   > tenga tu decisión, avisame acá.
3. Esperá. Cuando te avise, leé la línea `DECISIÓN:` de `{lote}/dictamen.md`:
   - `APROBADO` → tickets `aprobado`, `paso: 6-implementar`.
   - `RECORTADO: …` → los tickets que salen, `estado: fuera`. Si cambia lo que piden los
     que quedan, mostrale al usuario qué tickets tocan y pedile el cambio de texto para su
     `spec.md`; después volvé al paso 1 solo para esos tickets.
   - `FRENADO: …` → `paso: terminado`, Cronista por ticket con estado "frenado" (plantilla
     **CR**), y fin.
   - `PENDIENTE` → decile que el dictamen todavía no tiene decisión.

## Paso 6 — Implementación (en el orden del lote)

Un ticket por vez, en `estado.orden`, salteando los `fuera`. El siguiente arranca cuando el
anterior está `revisado`.

1. Verificá que la etapa B del ticket terminó (contenedores arriba). Si no, esperá.
2. QA (plantilla **Q**).
3. RED: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/correr_casos.py {ticket} --red > {ticket}/revision/testeo/red.txt`
   - Exit 0 → `estado: red`.
   - Exit 1 por un caso nuevo que pasa o un caso sin script → QA de nuevo con `red.txt`
     (una vez). Si sigue → pausa.
   - Un caso de regresión que falla → pausa (`regresion-preexistente`).
4. Implementador (plantilla **I**). Según su `ESTADO`:
   - `green` → `estado: green`.
   - `pausa`, `estancado`, `presupuesto` → pausa con su `MOTIVO` y
     `revision/implementacion.md`.
5. Revisión, por cada repo del ticket:
   ```bash
   wt=<worktree>
   tree=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reglas.py --snapshot --worktree $wt)
   git -C $wt diff master $tree > {ticket}/revision/diff-<ms>.patch
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reglas.py --worktree $wt --ownership dcac-context/back/database-ownership.md > {ticket}/revision/reglas-<ms>.txt
   ```
   y un Revisor por repo, en el mismo mensaje (plantilla **R**). Con bloqueantes: un
   Implementador nuevo con las revisiones (plantilla **I2**), una sola vez. Lo que quede →
   `riesgos.md`.
6. `estado: revisado`.

## Paso 7 — Cierre

1. **Integración:** `correr_casos.py` de cada ticket no `fuera`, en orden, todo a
   `{lote}/cierre.md` § Integración.
2. **Deriva:** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/contratos.py --deriva <tickets> --worktree T#####=<wt> … >> {lote}/cierre.md`
3. **Medición:** por ticket, `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hechos.py {ticket} --worktree <wt> … > {ticket}/revision/hechos.md`,
   y la sección Economía de cada uno a `cierre.md` § Medición.
4. **Crónica:** un Cronista por ticket (plantilla **CR**).
5. **Provisorias:** mostrale al usuario la ruta de cada `revision/provisorias.md`.
   Confirmadas → `spec.md`. Vetadas → pausa: el ticket vuelve al paso 4.
6. **Envío:** decile al usuario el orden del lote y que apruebe el envío. Con su
   aprobación explícita, `enviar-review` por ticket, en orden. Después `bajar-entorno`.
7. `paso: terminado`.

## Pausas

Pausás (`estado.pausa`, y le mostrás al usuario el motivo y la ruta) por: una decisión en
terreno sensible (financiero, permisos, datos); una corrección que falló dos veces; una
regresión preexistente; el entorno caído; estancamiento; presupuesto agotado; una
provisoria vetada. Con la respuesta del usuario, seguís desde donde quedó.

## Provisorias

Una duda mayor fuera de terreno sensible no frena: el Baqueano la toma con la opción más
conservadora (`PROVISORIA`), queda en `revision/provisorias.md` con lo que depende de ella,
y el usuario la confirma o la veta en el cierre. En terreno sensible, siempre pausa.

## Plantillas

Reemplazá lo que está entre `<…>`. Nada más.

**E — Escribano**
```
Agent(subagent_type: "clarabella:escribano", description: "Escribano T#####",
      prompt: "Ticket T##### (proyecto <proyecto>, tipo <tipo>, slug <slug>), carpeta <ticket>.")
```

**GP — Generador de plan**
```
Agent(subagent_type: "clarabella:generador-plan", description: "Plan T#####",
      prompt: "Ticket T##### (proyecto <proyecto>, tipo <tipo>, slug <slug>), carpeta <ticket>.
               Worktrees: <ms>=<ruta>, …. Escribí <ticket>/plan.md.")
```

**GT — Generador de tests**
```
Agent(subagent_type: "clarabella:generador-tests", description: "Tests T#####",
      prompt: "Ticket T##### (proyecto <proyecto>, tipo <tipo>, slug <slug>), carpeta <ticket>.
               Escribí <ticket>/tests.md.")
```

**B — Baqueano**
```
Agent(subagent_type: "clarabella:baqueano", description: "Baqueano <plan|tests> T#####",
      prompt: "Ticket T#####, carpeta <ticket>, en resolver-proyecto. Dudas del generador de
               <plan|tests>, textuales: <DUDAS>. Escribí <ticket>/revision/consultas-<plan|tests>.md.")
```

**A — Alineador**
```
Agent(subagent_type: "clarabella:alineador", description: "Alineador <lote>",
      prompt: "Lote <lote>, carpeta <lote>. Tickets: T##### (<ticket>), …. Escribí <lote>/alineacion.md.")
```

**V — Verificador**
```
Agent(subagent_type: "clarabella:verificador", description: "Verificador T#####",
      prompt: "Ticket T#####, carpeta <ticket>. Escribí <ticket>/revision/verificacion.md.")
```

**C — Corrector**
```
Agent(subagent_type: "clarabella:corrector", description: "Corregir <plan|tests> T#####",
      prompt: "Corregí <ticket>/<plan.md|tests.md> según: <ids y rutas de los hallazgos, o el
               error del script, textual>.")
```

**Q — QA**
```
Agent(subagent_type: "clarabella:qa", description: "QA T#####",
      prompt: "Ticket T#####, carpeta <ticket>. Contenedores T#####-<ms>, DB T#####-db.
               Escribí <ticket>/casos/. <Si es re-despacho: corregí solo los casos marcados
               en <ticket>/revision/testeo/red.txt.>")
```

**I — Implementador**
```
Agent(subagent_type: "clarabella:implementador", description: "Implementador T#####",
      prompt: "Ticket T#####, carpeta <ticket>. Repos y worktrees: <ms>=<ruta>, ….
               Presupuesto: <n> vueltas de GREEN.")
```

**I2 — Implementador (corrección post-revisión)**
```
Agent(subagent_type: "clarabella:implementador", description: "Corregir revisión T#####",
      prompt: "Ticket T#####, carpeta <ticket>. Repos y worktrees: <ms>=<ruta>, ….
               Corregí solo los bloqueantes de <ticket>/revision/revision-impl-<ms>.md.
               Presupuesto: 2 vueltas de GREEN.")
```

**R — Revisor**
```
Agent(subagent_type: "clarabella:revisor", description: "Revisión <ms> T#####",
      prompt: "Ticket T#####, carpeta <ticket>, repo <ms>. Leé solo:
               revision/diff-<ms>.patch, plan.md, revision/reglas-<ms>.txt,
               revision/notas-<ms>.md, dcac-context/back/conventions.md y el CLAUDE.md del
               repo. Escribí revision/revision-impl-<ms>.md.")
```

**CR — Cronista**
```
Agent(subagent_type: "clarabella:cronista", description: "Cronista T#####",
      prompt: "Ticket T#####, carpeta <ticket>, estado <entregado|frenado>.")
```

## Errores comunes

- **Resumirle al usuario lo que devolvió un rol** → rutas o texto textual.
- **Arreglar vos un error de formato** → Corrector.
- **Retomar a un generador para corregir** → Corrector nuevo.
- **Implementar sin la decisión del juicio** (si hay juicio) → `dictamen.md` manda.
- **Arrancar un ticket antes de que el anterior del orden esté `revisado`** → el orden es
  el de `contratos.txt`.
- **Despachar un Obrero** → los despacha el Implementador.
- **Enviar a review sin aprobación explícita** → nunca.
