---
name: enviar-review
description: Usar cuando el usuario ya aprobó explícitamente, en el chat, el envío de un ticket a review con Arcanist, resuelto de forma manual (no vía dashboard/pipeline-desarrollo) — hay que commitear y correr arc diff --create. Triggers — "dale, mandalo vos", "arc diff de esto", "enviá los cambios de T##### ahora", como cierre de resolver-ticket. NO usar si el flujo viene del dashboard (ahí es enviar-cambios, gateada por .pipeline/envio.json).
---

# Enviar cambios (Arcanist) — standalone

Versión de `enviar-cambios` sin dependencia del motor `pipeline-desarrollo`: sin
`.pipeline/envio.json`, sin dashboard, sin fases numeradas. El gate es la palabra directa
del usuario en el chat, no un archivo de estado.

**Esta es la ÚNICA acción de este flujo manual que commitea.** El resto del trabajo
(`resolver-ticket`) queda sin commitear hasta acá.

## Gate — aprobación explícita del usuario en el chat

**No corras esta skill por tu cuenta.** Necesitás que el usuario, en el mensaje, haya aprobado
el envío en un turno anterior o en el mismo (ej. tras ver el resumen de `resumir-ticket`
o el diff de `mostrar-diff`) — no infieras la aprobación de que "el código está
listo". Si no hubo un "dale, mandalo" / "aprobado, enviá" explícito, preguntá antes de
commitear.

## Regla de oro ante errores

**Si algo falla —conflicto de merge, error de `arc`, lint/unit que traba, prompt
interactivo inesperado— FRENÁ y devolvé el control al usuario** para que lo arregle a mano.
No fuerces, no adivines, no resuelvas conflictos automáticamente.

## Reglas duras

- **Autor = usuario real, nunca Claude.** Firmá con `git config user.name` y `git config user.email` del repo (si están vacíos, pedíselos al usuario). **No**
  agregar `Co-Authored-By: Claude` ni atribución a la IA.
- **Master no se toca.** El diff sale de la branch `T#####`; el land ocurre recién cuando el
  review aprueba (fuera de esta skill).
- **Un diff por repo.** Si el ticket tocó varios repos, repetí el ciclo en cada uno — **en
  paralelo, no secuencial**: cada repo es independiente a la hora de enviar (commit propio,
  `.git` propio, Differential propia), no hay ninguna dependencia entre ellos. Lanzá los pasos
  1-4 de cada repo como tool calls paralelos en el mismo turno (varios `Bash` en un solo
  mensaje) en vez de terminar el ciclo completo de un repo antes de arrancar el siguiente.
  Si un repo falla (conflicto, error de `arc`), frená **ese repo** y avisá — no bloquea a los
  demás, que pueden seguir/haber terminado igual.
- **No commitear/enviar nada fuera de la branch del ticket.**
- **NUNCA `git push` de la branch del ticket al remoto real de Phabricator** después de
  `arc diff --create`. `arc diff` ya sube el contenido a su propia área de staging; un push
  posterior al remoto real puede hacer que Phabricator auto-cierre la Revision (matchea el
  trailer `Differential Revision:`) generando un commit "landed" sin review — viola "Master
  no se toca". El paso 4 de abajo es el final: no hay `git push` después de `arc diff --create`.

## Workflow (por cada repo tocado — en paralelo entre repos)

### 1. Armar el commit message (formato Arcanist — orden exacto)

```
<Título de la revisión — una línea, sin punto final, con el T##### y qué hace>

Summary:
<qué hace el cambio y por qué — para microservicio/apigateway, el bloque completo de
gestion/equipo/template-pr.md: ¿Qué hace?, Ticket: T#####, tipo de cambio marcado,
Evidencia de funcionamiento (curl + response + tests del paso de validación), Checklist
de arquitectura, Notas para el reviewer>

Test Plan:
<cómo verificaste que funciona>

Reviewers:
<usuario1, usuario2 o #equipo>

Subscribers:
<opcional>

Tags:
<opcional>

Depends on:
<D##### — opcional>

Maniphest Tasks:
<T##### — el ticket>
```

**No incluir `Differential Revision:`** al crear el diff — lo agrega Phabricator solo tras
`arc diff --create`. Orden fijo, un bloque por campo, campo opcional sin aplicar se omite
entero (no se deja vacío). Summary en Remarkup (no Markdown): `**bold**`, `---`, sin `##`.

Si te falta el reviewer, preguntale al usuario — no lo inventes ni lo dejes en `<completar>`.

### 2. Commitear en la branch del ticket

Si el repo se preparó con `aislar-ticket`, el código vive en el **worktree**
(`.worktrees/T#####-{slug}/<ms>`), no en `microservicios/<ms>` — commiteá ahí. Como el
worktree comparte `.git` con el canónico, **no hace falta ningún sync-out/push**: la branch
`T#####` ya es visible desde el canónico apenas commiteás. `arc diff` puede correr
directo desde el worktree siempre que tenga `.arcconfig` disponible (`aislar-ticket`
lo copia si estaba gitignoreado).

`git -C <repo> commit` con ese mensaje, en la branch `T#####`. Autor real, sin atribución
a Claude.

### 3. Traer master a la branch

**Si venís de un worktree, no hagas `switch master` ahí adentro:** git no te deja checkear
`master` en el worktree mientras el canónico ya lo tiene checkeado (es la misma protección
que evita colisiones). En su lugar, actualizá `master` en el **canónico** y mergealo por
nombre de rama desde el worktree, sin cambiar de branch:

```
git -C microservicios/<ms> pull                          # actualiza master en el canónico
git -C .worktrees/T#####-{slug}/<ms> merge master         # mergea esa ref en el worktree
```

(En modo `entorno-ticket`/clon, o si estás en la branch directo sin worktree, seguís
pudiendo hacer el `switch master && pull && switch T##### && merge master` de siempre.)

**Conflicto → FRENÁ y avisá al usuario** (qué repo, qué archivos). No lo resuelvas vos.

### 4. Crear el diff

`arc diff --create --verbatim` desde la branch `T#####`, no interactivo (sin abrir editor).
**No le pases un rango explícito tipo `HEAD^`**: tras un merge, `HEAD^` es el primer padre
(la branch antes del merge), y pasarlo a mano produce un diff con el contenido de master, no
los cambios reales del ticket — sin error visible que lo delate. Dejá que `arc` detecte la
base solo con `arc diff --create --verbatim` (sin argumento de revisión).

**Si `arc` frena pidiendo "Select a Default Commit Range"** (no hay
`arc.feature.start.default` configurado en este working copy, y como corre no-interactivo no
puede preguntar) → hacé `git fetch origin master` y corré
`arc diff origin/master --create --verbatim`. Esto **no** es el mismo caso que `HEAD^`: es
el merge-base contra el remoto real (lo que Arcanist mismo sugiere como default), no una
referencia frágil de padre de commit — captura bien todos los commits del ticket aunque haya
habido un merge de master en el medio.

Si el parser tira `Field "X" occurs twice`, sospechá de un alias de campo (ej. `Tests:`
dentro del Summary matcheando `Test Plan`) — usá un label distinto (ej. `Evidencia de
tests:`).

Si `arc` abre un editor, pide input, o falla por lint/unit → **FRENÁ**.

### 5. Reportar

Devolvé al usuario la Differential creada (`D####` / URL) por cada repo. **No hay ningún
paso de git después de esto** — en particular, no se pushea la branch a ningún remoto real.

## Errores comunes

- **Asumir aprobación por "el código está listo"** → no; necesitás la palabra explícita del
  usuario en el chat.
- **Firmar como Claude / Co-Authored-By** → jamás.
- **Resolver un conflicto de merge solo** → frená y que lo haga el usuario.
- **Inventar un reviewer** → jamás; preguntale al usuario.
- **Pasarle a `arc diff` un rango tipo `HEAD^`** → diff con contenido de master, no del
  ticket, sin error visible. Dejá que Arcanist detecte la base solo.
- **`git push` de la branch del ticket al remoto real tras `arc diff`** → prohibido, puede
  auto-cerrar la Revision.
