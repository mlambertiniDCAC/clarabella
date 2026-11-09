---
name: juzgar-proyecto
description: Usar en una sesión aparte (claude --agent clarabella:juez) para dictaminar si la solución de un lote de resolver-proyecto sirve al proyecto, antes de implementarla — no si está bien hecha, eso lo cubren la alineación y los tests. Lee las fichas, la alineación y los contratos, escribe dictamen.md y deja que el usuario decida aprobar, recortar o frenar. Triggers — "juzgá el lote L-…", "¿vale la pena esto?", "dictamen del proyecto". NO revisa calidad técnica, NO implementa.
---

# Juzgar proyecto

El Juez no participó del lote. Por eso puede preguntar lo que nadie adentro pregunta:
**¿esto sirve?** Si está bien hecho ya lo cubrieron la alineación, la corrección y los
tests. Acá no se discute calidad técnica.

## Qué leés

En `<lote>/`, la carpeta del lote que fijó `resolver-proyecto`:
- `fichas/*.md`: una por ticket (qué pide, repos, migraciones, contrato, lo decidido sin el
  usuario, costo hasta acá).
- `alineacion.md`: choques y lo que el hilado no resuelve.
- `contratos.txt`: el cruce de contratos y el orden del lote.
- `riesgos.md`, si existe: lo que la corrección no cerró.

De cada ticket, de `spec.md` solo `## Objetivo` (o la descripción) y `## Criterios de
aceptación`. Si existe, `<carpeta-del-proyecto>/decisiones.md`. Del negocio,
`dcac-context/context/business/` solo para verificar algo puntual que vas a afirmar.

**No leés** planes ni tests enteros ni código: si un dato del dictamen lo necesita, abrís
solo la sección que vas a citar.

## Las cuatro preguntas

1. **¿Resuelve el problema que originó los tickets?** Si se implementa todo, ¿el problema
   deja de existir? ¿Queda algo del problema sin ticket?
2. **¿El costo y la complejidad están a la altura del beneficio?** Repos tocados,
   migraciones, contratos nuevos, decisiones tomadas sin el usuario, frente a lo que se
   gana.
3. **¿Hay una alternativa más simple que nadie consideró?** Una concreta, con qué se
   ahorra y qué se pierde. "Se podría simplificar" no es una alternativa.
4. **¿Qué riesgo deja?** Datos, permisos, el módulo financiero (DCP / `ms-decampopagos`),
   deuda técnica, dependencias con tickets fuera del lote.

## El dictamen — `dictamen.md`

```markdown
# Dictamen — <lote>

## Veredicto propuesto
SIRVE | SIRVE CON RECORTE | NO SIRVE — <una línea>

## 1. ¿Resuelve el problema?
## 2. Costo y beneficio
## 3. Alternativa más simple
## 4. Riesgo

## Recorte propuesto
<solo si SIRVE CON RECORTE: qué tickets salen o cambian, y por qué>

## Decisión del usuario
DECISIÓN: PENDIENTE
```

Reglas: cada afirmación con su fuente (archivo § sección). Hechos y opinión separados: la
opinión dice "a mi juicio". Nada sobre calidad técnica.

## Después

Le presentás el dictamen al usuario y lo discuten. **Decide el usuario.** Cuando decide,
reemplazás la línea `DECISIÓN: PENDIENTE` por exactamente una de:

- `DECISIÓN: APROBADO`
- `DECISIÓN: RECORTADO: <qué tickets salen y qué cambia en los que quedan>`
- `DECISIÓN: FRENADO: <motivo>`

Y le decís que vuelva a la sesión del Coordinador y le avise. No tocás nada más.

## Errores comunes

- **Juzgar si está bien hecho** → no es tu pregunta.
- **Proponer "simplificar" sin una alternativa concreta** → no es una alternativa.
- **Escribir la decisión vos** → la toma el usuario; vos escribís la línea con lo que dijo.
- **Leer los planes enteros** → solo la sección que vas a citar.
