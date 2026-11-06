---
name: consultar-portfolio
description: Usar al arrancar cualquier trabajo sobre un proyecto del workspace dcac-ia-context — antes de planear o implementar un ticket, y cuando el usuario pregunta en qué quedó algo. Trae del cerebro de contexto el estado del proyecto, sus pendientes y con qué otros proyectos se relaciona. Triggers — "en qué quedé con X", "qué está bloqueado en Pagos", "cómo se relaciona este proyecto con el otro", "resumime la semana", y el paso de entender de planear-ticket. NO carga información (eso es cargar-portfolio) ni reemplaza a dcac-context/.
---

# Consultar el cerebro de contexto

Contesta **en qué quedó un proyecto**, que es anterior a cómo funciona un servicio. El
código sigue viniendo de `dcac-context/` y del repo; esto da el contexto del proyecto.

## Chequeo previo (no bloqueante)

El cerebro vive en un repo aparte. Resolvé su raíz en este orden: `$CEREBRO_RAIZ`, o
`~/projects/portfolio`.

Si no existe, **no es un error**: no lo menciones como problema, no sugieras crearlo, no
le preguntes al usuario — seguí con la exploración normal (`dcac-context/`, el `CLAUDE.md`
del repo, el código). Esta skill solo aplica donde ya hay un cerebro cargado.

El CLI es `<raiz>/bin/cerebro` y devuelve JSON por stdout. Resuelve el almacén desde su
propia ubicación, así que **invocalo por su ruta completa**
(`~/projects/portfolio/bin/cerebro ...`), nunca como un `cerebro` suelto.

## Cómo consultar

```bash
cerebro resolver-nombre "<lo que nombró el usuario>"   # del nombre al slug
cerebro contexto <slug>                                 # estado, pendientes, relaciones, anotaciones
cerebro vecinos <slug>                                  # solo las relaciones
cerebro resumen --squad pagos                           # una fila por proyecto del squad
cerebro resumen --desde 2026-11-01                      # lo que se movió desde esa fecha
cerebro artifacts-ultimos                               # los artifacts más nuevos, con su proyecto
cerebro bandeja-listar                                  # lo que quedó sin clasificar
cerebro frescura                                        # de cuándo es el espejo del catálogo
cerebro validar                                         # relaciones colgadas y archivos ilegibles
```

Empezá siempre por `resolver-nombre`: el usuario nombra los proyectos como se le ocurre y
los slugs no coinciden con los nombres del tablero ni con las carpetas de `docs/`.

Para una pregunta de un solo proyecto, `contexto` alcanza. Para "qué está bloqueado" o
"qué se movió", `resumen`. Para seguir una relación, `vecinos` y después `contexto` del
vecino.

## En `planear-ticket`

Es el primer paso de la Fase 1, antes de `dcac-context/`: traé el contexto del proyecto al
que pertenece el ticket. Lo que aparezca ahí — un bloqueo, una decisión, un pendiente
abierto, un proyecto del que este es la v2 — cambia el plan antes de que leas una línea de
código.

Si el ticket no se mapea a ningún proyecto del catálogo, seguí sin el cerebro.

## Reglas duras

- **Nunca afirmes algo que el cerebro no tenga.** Lo que devuelve es lo que el usuario
  cargó, con su fecha y su origen; citá esa fecha cuando uses una novedad para justificar
  una decisión. Una anotación de hace tres meses no es el estado de hoy.
- **El cerebro no es `dcac-context/`.** Reglas de negocio, contratos de servicios y
  ownership de tablas siguen viniendo de ahí, y de `product-dcac/` si está. La prioridad
  documental del workspace no cambia: el cerebro se suma arriba, no reemplaza nada.
- **No escribas desde acá.** Cargar es `cargar-portfolio`.
- **El catálogo puede estar incompleto o viejo.** `cerebro resolver-nombre` devolviendo
  `desconocida` puede significar que falta poblar un squad, no que el proyecto no exista.
  Mirá `cerebro frescura` antes de concluir que algo no está.
- **`resumen` y `validar` informan los archivos ilegibles** en la clave `ilegibles`. Si
  aparece alguno, decilo: ese proyecto quedó afuera de la respuesta.

## Errores comunes

- **Tratar "no hay cerebro" como bloqueante** → seguí con la exploración normal, sin
  comentarlo.
- **Pedirle al cerebro cómo funciona el código** → eso es `dcac-context/`, el repo, o
  `consultar-grafo` si el repo tiene grafo.
- **Usar el slug que te pareció** → siempre `resolver-nombre` primero.
- **Dar por actual una anotación vieja** → mirá su fecha y decila.
