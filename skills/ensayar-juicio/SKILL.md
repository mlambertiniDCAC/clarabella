---
name: ensayar-juicio
description: Usar para calibrar el juicio de Clarabella con un ticket YA CERRADO del workspace dcac-ia-context — corre la preparación (agentes generativos de plan y tests) y el juicio (Juez, defensa, peritos, correcciones) sobre el código y la documentación tal como estaban antes del ticket, y un auditor compara el resultado con la solución que realmente se mergeó. Mide costo, correcciones, peritajes y aciertos. Triggers — "ensayá el juicio con T#####", "probá el juicio con un ticket cerrado", "backtest de Clarabella con T#####". NO implementa, NO levanta Docker, NO commitea.
---

# Ensayar el juicio

Antes de confiar en el juicio para un ticket nuevo, hay que ver cómo se comporta con uno
cuya respuesta ya se conoce. Este ensayo corre las **fases 1 y 2** de `resolver-ticket`
sobre un ticket cerrado, con el código y la documentación **como estaban antes** de
resolverlo, y después compara lo que produjo el juicio con lo que realmente se hizo.

Responde preguntas concretas: ¿el plan sobreviviente se parece a la solución real? ¿El
Juez mató a un agente que tenía razón? ¿Los tests cubren lo que la solución real
garantiza? ¿Cuántos agentes y peritos costó?

## Datos requeridos

| Dato | De dónde | Si falta |
|------|----------|----------|
| Ticket cerrado `T#####` | El usuario | Preguntá. Conviene uno con criterios claros y 1-2 repos |
| Spec | Texto del ticket (Phabricator con `phab-ticket`, o lo que pegue el usuario) | Pedila. Usá el texto **original**, no un resumen escrito después |
| Repos que tocó | Del ticket o de los commits | Preguntá |
| Commits de la solución | `git -C microservicios/<ms> log master --grep="T#####" --format="%H %ad %s"` | Si no aparecen, pedí el `D####` o los hashes |

## Paso 1 — Reconstruir el pasado

Para cada repo:
1. **Base** = el padre del commit más viejo del ticket (`<primer-commit>^`). Es el código
   como estaba antes.
2. **Solución real** = `git -C microservicios/<ms> diff <base> <último-commit-del-ticket>`,
   guardada en `docs/_ensayos/T#####-{slug}/real/diff-<ms>.patch`.
3. **Worktree del pasado:**
   `git -C microservicios/<ms> worktree add --detach ../../.worktrees/ensayo-T#####/<ms> <base>`.

**La documentación también tiene que ser la de antes.** Si `dcac-context/` ya documenta lo
que el ticket resolvió, los agentes copian la respuesta. Tomá la versión del repo del root
a la fecha de la base:
```bash
git rev-list -1 --before="<fecha del commit base>" HEAD
git worktree add --detach .worktrees/ensayo-T#####/contexto <ese-commit>
```
Los agentes leen `dcac-context/` desde `.worktrees/ensayo-T#####/contexto/dcac-context/`.
Si `product-dcac/` existe, lo mismo con su propio repo.

**`real/` es secreto.** Solo lo lee el auditor del paso 3. Ni los agentes generativos, ni
el Juez, ni los peritos, ni el orquestador lo abren.

## Paso 2 — Correr la preparación y el juicio

Carpeta del ensayo: `docs/_ensayos/T#####-{slug}/` (no en la carpeta del proyecto, para no
mezclar un ensayo con documentación real). Adentro, la misma estructura de
`resolver-ticket`: `spec.md`, `plan.md`, `tests.md`, `juicio/`.

Seguí `resolver-ticket` fase 1 (sin 1.1 y sin la etapa B de Docker: los worktrees ya son
los del paso 1) y fase 2 completa, con dos cambios en los prompts de todos los subagentes:
- worktrees: `.worktrees/ensayo-T#####/<ms>`;
- documentación: `.worktrees/ensayo-T#####/contexto/dcac-context/` en lugar de
  `dcac-context/`.

**Las DUDAS van primero al Baqueano**, con las mismas prohibiciones que los agentes
generativos y **sin memoria persistente** (contiene decisiones tomadas en el ticket real).
Lo que el Baqueano mande `AL USUARIO`, el usuario lo responde como lo habría hecho en su
momento, sin mirar la solución.

**Fuga conocida:** los subagentes reciben el índice `MEMORY.md` **tal como se cargó al
abrir la sesión**; no lo releen. Sacar la línea del ticket a mitad de sesión no sirve. Para
un ensayo limpio, sacá esa línea del índice **antes de abrir la sesión** del ensayo y
reponela al terminar. Si no se hizo, anotá la fuga en `registro.md` y pedí a cada subagente
una declaración de contaminación.

**Registrá el costo mientras corre**, en `docs/_ensayos/T#####-{slug}/registro.md`: cada
subagente despachado (rol, modelo), y la duración y los tokens si el resultado
del Agent los informa.

## Paso 3 — Auditoría

Con la sentencia lista, despachá un **auditor** (subagente nuevo, `opus`). Es el único que
ve todo, incluida la solución real:

```
Agent(subagent_type: "general-purpose", model: "opus", description: "Auditor ensayo T#####",
      prompt: "Invocá la skill clarabella:ensayar-juicio, rol auditor, para el ensayo en
               docs/_ensayos/T#####-{slug}/. Compará el resultado del juicio con la
               solución real en real/ y escribí informe.md.")
```

**Qué compara el auditor:**

| Pregunta | Cómo |
|----------|------|
| ¿El plan sobreviviente se parece a la solución real? | Parte por parte del plan contra `real/diff-<ms>.patch`: coincide, difiere (mejor/peor/equivalente, con razón), falta en el plan, sobra en el plan |
| ¿Los tests cubren lo que la solución garantiza? | Cada criterio de la spec: ¿hay caso? Y para la solución real: ¿pasaría los tests? ¿Algún caso fallaría con la solución real porque está mal planteado? |
| ¿El Juez juzgó bien? | Cada observación sostenida o retirada contra la solución real: acierto, falso positivo (sostuvo algo que la solución real hace bien), falso negativo (retiró algo que la solución real resuelve distinto) |
| ¿Las correcciones mejoraron el resultado? | Por cada observación corregida: ¿la versión corregida está más cerca o más lejos de la solución real que la original? |
| ¿Los peritos sirvieron? | Dictámenes `FALSA` reales vs. errores de interpretación marcados de más; peritajes que no cambiaron nada |
| ¿Cuánto costó? | Del `registro.md`: subagentes por rol y modelo, peritajes, rondas de corrección, duración y tokens |

`informe.md`:

```markdown
# Ensayo del juicio — T#####

## Veredicto
<2-3 líneas: ¿el juicio habría llevado a una buena solución?>

## Plan vs. solución real
| Parte | Resultado | Detalle |

## Tests vs. solución real
| Criterio / caso | ¿Lo cubre? | ¿Pasaría la solución real? |

## Calidad del juicio
| Obs | Fallo | Según la solución real | Acierto / falso positivo / falso negativo |

## Correcciones
| Obs | Agente | ¿Mejoró? | Por qué |

## Peritos
## Costo
## Qué ajustaría
<propuestas concretas sobre las reglas del Juez, el perito o los agentes; no las aplica>
```

El auditor no cambia las skills: propone. Los ajustes los decide el usuario.

## Paso 4 — Limpiar

```bash
git -C microservicios/<ms> worktree remove ../../.worktrees/ensayo-T#####/<ms>
git worktree remove .worktrees/ensayo-T#####/contexto
```
La carpeta `docs/_ensayos/T#####-{slug}/` queda como registro de la calibración.

## Errores comunes

- **Darles a los agentes la `dcac-context/` actual** → si ya documenta la solución, el
  ensayo mide copia, no criterio.
- **Usar una spec reescrita después del ticket** → tiene que ser el texto original.
- **Que alguien que no sea el auditor lea `real/`** → contamina el ensayo.
- **Responder las DUDAS mirando la solución real** → el usuario contesta como lo habría
  hecho en su momento.
- **Aplicar los ajustes del informe directo a las skills** → son propuestas para el usuario.
- **Ensayar con un ticket enorme o sin criterios claros** → no se puede comparar nada.
  Mejor 1-2 repos y criterios explícitos.
- **Dejar los worktrees del ensayo** → `worktree remove`, nunca `rm -rf`.
