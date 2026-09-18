---
name: resolver-ticket
description: Usar cuando el usuario quiere resolver un ticket (de desarrollo o de soporte) del workspace dcac-ia-context él mismo, en el hilo principal, invocando cada skill del flujo paso a paso con revisión suya en cada etapa — no el motor autónomo por subagentes. Triggers — "resolvamos T##### paso a paso", "arranquemos T##### de forma manual", "hagamos T##### sin el pipeline". NO confundir con pipeline-desarrollo (motor autónomo con subagentes por fase); esta es la checklist para correr el mismo flujo vos mismo, en el chat.
---

# Resolver ticket (flujo manual)

Checklist de referencia: qué skill corresponde a cada paso de un ticket (desarrollo o soporte)
cuando el usuario lo resuelve **en el hilo principal**, con revisión suya en cada etapa —
sin despachar subagentes ni pasar por el dashboard (eso es `pipeline-desarrollo`).

**Vos no reemplazás el criterio de cada skill: solo encadenás la que toca en cada paso.**
Cada una ya trae sus propias reglas (gates, formatos, errores comunes) — leelas al invocarlas,
no las repitas acá.

## Paso 0 — Fijar la carpeta del ticket

Antes del paso 1, definí con el usuario (preguntá lo que no venga en el pedido o el ticket):

- **Ticket** `T#####` y un título corto → `{slug}` en kebab-case, sin tildes ni ñ.
- **Tipo**: `desarrollo` o `soporte`. Si el ticket no lo deja claro, preguntá.
- **Proyecto**: una carpeta de `docs/`. Listá las existentes y preguntá cuál, o si hay que
  crear una nueva.

Con eso queda fijada la carpeta del ticket, siempre en la **raíz del workspace
dcac-ia-context** (el directorio donde están `dcac-context/` y `microservicios/`):

```
docs/{proyecto}/{tipo}/T#####-{slug}/
├── plan.md      ← paso 2
├── tests.md     ← paso 3
└── resumen.md   ← paso 7
```

Creala si no existe y pasales `proyecto`, `tipo`, `T#####` y `slug` a cada skill del flujo:
en modo manual no hay `estado.json`, así que estos valores reemplazan a los que el motor
guarda ahí. Si la sesión no está en la raíz del workspace, usá rutas absolutas.

## Flujo

| # | Paso | Skill | Nota |
|---|------|-------|------|
| 1 | Identificar y preparar repos | `preparar-repo` (que a su vez delega en `aislar-ticket`) | Los repos suelen venir en el ticket (`microservicios/<nombre>`); si no, inferilos por el dominio del cambio antes de preparar. El canónico queda en master (solo lectura); la branch `T#####` vive aislada en un worktree + contenedor Docker propio (ver `aislar-ticket`) — así este ticket nunca pisa a otro que toque el mismo repo. |
| 2 | Planear el desarrollo | `planear-ticket` | Con el `tipo` del paso 0: un ticket de soporte guarda su plan en `docs/{proyecto}/soporte/…`, no en `desarrollo/`. |
| 3 | Documentar el plan de tests | `planear-tests-ticket` | Sobre el plan ya escrito en el paso 2. |
| 4 | Implementar | — (código directo, o `implementar-ticket` si preferís el modo guiado) | Codeá **dentro del worktree** (`.worktrees/T#####-{slug}/<ms>`) que dejó el paso 1, nunca en `microservicios/<ms>` directo. Levantá `mostrar-diff` en modo vivo (ver abajo) **antes** de empezar a codear y dejalo abierto: así revisás cada archivo a medida que se escribe, no al final. |
| 5 | Validar contra el plan de tests | `testear-ticket` | Corré los casos documentados en el paso 3 contra la implementación real. |
| 6 | Revisar el diff completo | `mostrar-diff` | Si ya lo dejaste abierto en el paso 4, solo confirmá que el estado final te convence. |
| 7 | Resumen del desarrollo | `resumir-ticket` | Plan + tests + resultado de testear-ticket + valor de producto + desvíos del plan/tests original. |
| 8 | Enviar a review | `enviar-review` | Standalone, gateado por tu aprobación explícita en el chat — no depende de `.pipeline/envio.json` ni del dashboard. |

## Paso 4/6 — preview en vivo durante la implementación

`mostrar-diff` ahora **recalcula el diff en cada request** y se **auto-refresca**
solo (cada pocos segundos) — no sirve una foto fija tomada al arrancar. Levantalo apenas
arranca el paso 4, antes de escribir el primer archivo:

```bash
python3 -u ${CLAUDE_PLUGIN_ROOT}/skills/mostrar-diff/serve.py --repo .worktrees/T#####-{slug}/<ms> --base master \
  > /tmp/diff_preview.log 2>&1 &
disown
sleep 1 && cat /tmp/diff_preview.log
```

**Ojo con el `--repo`:** apunta al **worktree**, no a `microservicios/<ms>` — el código del
ticket vive ahí (paso 1), el canónico se queda siempre en master.

Dejalo abierto en el navegador todo el paso 4: cada archivo que edites aparece solo en el
próximo refresh, sin relanzar el servidor. Esto es lo que te deja hacer la review "a medida
que se necesita" en vez de al final (ver `mostrar-diff` para el detalle del script).

## Gate de sensibilidad (se mantiene aunque no haya subagentes)

Aunque acá no hay doubt-gate automatizado, la regla de fondo del workspace sigue aplicando:
ante cualquier ambigüedad de documentación o de negocio (sobre todo si toca el módulo
financiero, `ms-decampopagos`/DCP), **frená y preguntale al usuario** antes de asumir — no hay
subagente que lo bloquee por vos acá, así que sos vos quien tiene que frenar.

## Errores comunes

- **Confundir esto con `pipeline-desarrollo`** → esa es la corrida autónoma con subagentes,
  modelo por fase y dashboard. Esta skill es la versión manual de referencia para cuando
  el usuario quiere estar presente en cada paso, en el hilo principal.
- **Saltarse `preparar-repo`** → un repo con cambios sin commitear o en la branch
  equivocada contamina el análisis y la implementación.
- **Levantar `mostrar-diff` recién al final** → pierde el sentido de review
  incremental del paso 4; levantalo ANTES de tocar el primer archivo.
- **Usar `enviar-cambios` (la versión ligada al pipeline) en vez de `enviar-review`**
  → esta última es la standalone, sin gate de `.pipeline/envio.json`.
- **Codear directo en `microservicios/<ms>` en vez del worktree** → rompe el aislamiento
  que arma `aislar-ticket` y puede pisar a otro ticket que use el mismo repo.
