---
name: revisar-ticket
description: Usar para revisar el plan y los tests de un ticket del workspace dcac-ia-context antes de implementar, o la implementación de un repo después de GREEN — primero corren los chequeos determinísticos (trazabilidad de los criterios CA#, reglas críticas sobre el diff) y después un revisor sonnet nuevo, de una sola pasada y con checklist fija, devuelve hasta 10 hallazgos con cita a una fuente. El modo implementación es el paso 6 de resolver-proyecto; el modo plan-tests se usa a pedido. Triggers — "revisá el plan y los tests de T#####", "revisá la implementación de T#####", "chequeá la trazabilidad de T#####". NO escribe plan ni tests, NO ejecuta tests, NO corrige.
---

# Revisar ticket

Lo que se puede verificar con un script no se le pregunta a un modelo. La revisión tiene
dos capas:

1. **Chequeos** (scripts, 0 tokens): trazabilidad de criterios y reglas críticas.
2. **Un revisor** (sonnet, nuevo, una pasada) para lo que no se puede mecanizar:
   convenciones, desvíos del plan, coherencia entre plan y tests, y confirmar o descartar
   las alertas de los scripts.

No hay rondas. No se retoma a quien escribió el artefacto para que se defienda: retomar
un agente arrastra todo su contexto (en T23815, 1,7M tokens de contexto retomado contra
1,5M de subagentes nuevos). La verificación de una corrección es volver a correr los
scripts (y GREEN, si cambió código).

Todo va a `docs/{proyecto}/{tipo}/T#####-{slug}/revision/` (abajo, `{ticket}`).

## Modo plan-tests (a pedido)

### 1. Trazabilidad

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/trazabilidad.py {ticket} > {ticket}/revision/trazabilidad.txt
```

- Exit 2 (formato): la spec no tiene `CA#`, falta un archivo, o la tabla de casos no empieza
  con `| ID | Criterio |`. Arreglalo vos (es formato, no contenido) y volvé a correr.
- Exit 1 (huecos): una línea `Cubre:` faltante la agregás vos. Un criterio sin caso o sin
  Parte es contenido: entra como hallazgo `bloqueante` para la corrección, sin pasar por el
  revisor.

### 2. Revisor

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Revisión plan-tests T#####",
      prompt: "Invocá la skill clarabella:revisar-ticket, rol revisor, modo plan-tests, para
               T##### (proyecto {proyecto}, tipo {tipo}, slug {slug}). Leé solo: spec.md,
               plan.md, tests.md, revision/trazabilidad.txt,
               dcac-context/back/conventions.md y el CLAUDE.md de cada repo del plan.
               Escribí revision/revision-plan-tests.md y devolvé el contrato.")
```

**Checklist del revisor (plan-tests):**
- Cada criterio está cubierto con sentido: la Parte que lo cita lo implementa y el caso que
  lo cita lo prueba (no alcanza con citarlo).
- El plan respeta las reglas críticas: los ms no se llaman entre sí, cada ms toca solo sus
  tablas, sin estado en propiedades de clase en Hyperf/apigateway.
- Plan y tests usan el contrato de `spec.md` (rutas, campos, códigos) y describen el mismo
  comportamiento.
- Los esperados de los tests son coherentes con las reglas documentadas, y cada
  verificación consulta una tabla del servicio dueño.
- El "Esperado en RED" es coherente: `falla` para comportamiento nuevo, `pasa` para
  regresión.
- El plan sigue las convenciones del servicio.

## Modo implementación (paso 6 de `resolver-proyecto`)

Por cada repo tocado (`<ms>`, worktree `.worktrees/T#####-{slug}/<ms>`):

### 1. Diff y reglas

```bash
wt=.worktrees/T#####-{slug}/<ms>
base=master   # en una segunda revisión del mismo repo: base=$(cat {ticket}/revision/ultima-revision-<ms>.txt)
tree=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reglas.py --snapshot --worktree $wt)
git -C $wt diff $base $tree > {ticket}/revision/diff-<ms>.patch
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reglas.py --worktree $wt --base $base \
  --ownership dcac-context/back/database-ownership.md > {ticket}/revision/reglas-<ms>.txt
echo $tree > {ticket}/revision/ultima-revision-<ms>.txt
```

El snapshot incluye los archivos nuevos sin trackear y no toca el index del repo.
`ultima-revision-<ms>.txt` es la base del delta en la próxima revisión del mismo repo: el
revisor ve solo lo que cambió desde la última vez.

`reglas.py` no mira tests, comentarios ni hosts de infraestructura (Graylog, Redis, DB…),
y no marca estado en clases de carpetas `Model/`/`Models/`. Las alertas siguen siendo
heurísticas: las confirma o descarta el revisor.

### 2. Revisor

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Revisión <ms> T#####",
      prompt: "Invocá la skill clarabella:revisar-ticket, rol revisor, modo implementación,
               para T##### (proyecto {proyecto}, tipo {tipo}, slug {slug}), repo <ms>. Leé
               solo: revision/diff-<ms>.patch, plan.md, revision/reglas-<ms>.txt,
               revision/notas-<ms>.md (si existe), dcac-context/back/conventions.md y el
               CLAUDE.md del repo. Podés abrir un archivo del worktree solo para ver el
               contexto de una línea del diff. Escribí revision/revision-impl-<ms>.md y
               devolvé el contrato.")
```

Los repos van en paralelo, un revisor por repo.

**Checklist del revisor (implementación):**
- Cada Parte del plan para este repo está implementada; los tests unitarios que el plan
  pedía existen.
- Lo que no sale del plan está en `notas-<ms>.md`. Un cambio fuera del plan y sin nota es
  hallazgo.
- Cada alerta de `reglas-<ms>.txt` se confirma (hallazgo `bloqueante`) o se descarta con
  una línea de por qué (falso positivo).
- Convenciones: `conventions.md`, el `CLAUDE.md` del repo, el código vecino; sin
  comentarios salvo que el archivo ya los use.

## El oficio del revisor

- **Una pasada.** Leés lo que dice el prompt, escribís el archivo, devolvés el contrato. No
  ejecutás nada: ni tests, ni lint, ni la app.
- **Hasta 10 hallazgos**, los más importantes primero. Si hay más, quedate con los
  bloqueantes.
- **Cada hallazgo, contra una fuente.** Lo que no tiene fuente no se reporta.
- **Severidad:** `bloqueante` (contradice la spec, una regla crítica o una regla de negocio
  documentada, o deja un criterio sin cubrir) o `menor` (se aparta de una convención sin
  cambiar el comportamiento).

```markdown
# Revisión — {plan-tests | impl <ms>} · T#####

### H1 · bloqueante
- **Dice el artefacto:** <cita, con sección, caso o archivo:línea>
- **Dice la fuente:** <cita> — `<ruta>` § <sección>
- **Propuesta:** <qué cambiar>

## Alertas descartadas
- `<archivo:línea · regla>` — <por qué es falso positivo>
```

Contrato:
```
ARTEFACTO: revision/<archivo>
HALLAZGOS: <n> (<b> bloqueantes, <m> menores)
ALERTAS_DESCARTADAS: <n>
ESTADO: completo
```

## La corrección

| Artefacto | Quién corrige |
|-----------|---------------|
| `plan.md` / `tests.md` | Un subagente **nuevo** (`sonnet`) con el artefacto y los hallazgos que le tocan, nada más. Si el cambio es trivial (una línea `Cubre:`, un renombre), el hilo principal |
| Código de un repo | Quien implementó ese repo (el hilo principal o su subagente) |

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Corregir {plan|tests} T#####",
      prompt: "Corregí {plan.md|tests.md} de T##### (carpeta {ticket}) según los hallazgos
               H<n>, H<m> de revision/revision-plan-tests.md. Cambiá solo lo que marcan. Si
               un hallazgo no corresponde, no lo apliques: devolvé DESACUERDO: H<n> — <por
               qué, con fuente>. Devolvé ARTEFACTO/CORREGIDOS/DESACUERDOS/ESTADO.")
```

- **No se retoma al agente del plan** (opus, con toda su exploración).
- Los `DESACUERDOS` van al usuario en una línea cada uno (en `resolver-proyecto`, a `riesgos.md` del lote; o al Baqueano: menor o
  provisoria).
- **No hay segunda revisión.** Después de corregir: `trazabilidad.py` de nuevo
  (plan-tests), o `reglas.py` y un GREEN nuevo si cambió código (implementación).

## Registro

Cada revisor y cada corrector es una fila en `registro.md` (rol, modelo, resultado,
`<n> s · <n>k tokens`), como cualquier subagente. Si alguna vez se retoma un agente, la
fila dice `<n> s · <n>k acumulados`: `hechos.py` lo cuenta como contexto retomado.

## Errores comunes

- **Mandarle al revisor lo que un script ya verificó** → la trazabilidad y las reglas no se
  revisan a mano; el revisor solo confirma o descarta alertas.
- **Retomar al autor para que corrija o se defienda** → corrige un sonnet nuevo con el
  artefacto y los hallazgos.
- **Una segunda pasada del revisor sobre la corrección** → se verifica con scripts y GREEN.
- **Revisar el diff completo en una segunda revisión del mismo repo** → desde la segunda, solo el delta
  (`ultima-revision-<ms>.txt`).
- **Usar `git diff master` a secas** → no ve los archivos nuevos sin trackear; usá el
  snapshot.
- **Reportar un hallazgo sin fuente** → no se reporta.
