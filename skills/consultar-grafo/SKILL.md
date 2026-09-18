---
name: consultar-grafo
description: Usar durante el análisis de código de cualquier skill de discovery del workspace dcac-ia-context (planear-ticket, investigación de un bug/soporte, entender comportamiento de un servicio) cuando el repo involucrado ya tiene un grafo de conocimiento generado (`graphify-out/graph.json`, hoy en ms-decampopagos, ms-compliance y apigateway). Triggers — "cómo funciona X en <ms>", "qué llama a Y", "trazá el flujo de Z", "encontrá dónde está el bug de...", cualquier pregunta de arquitectura/comportamiento sobre un repo con grafo. NO instala ni genera un grafo nuevo (eso es /graphify, decisión del usuario); si el repo no tiene graphify-out, seguí con exploración normal sin bloquear.
---

# Consultar grafo de conocimiento (por servicio)

Acelera el paso de "entender el código" de cualquier skill de discovery, consultando el
grafo de conocimiento ya generado por `graphify` para el repo en cuestión, en vez de (o
antes de) explorar a mano con grep/Explore. **No reemplaza leer el código real** — lo que
esta skill hace es decirte dónde mirar y cómo se conecta, más rápido que tanteando.

## Cuándo usar

- `planear-ticket`, Fase 1 (Entender): antes de leer archivo por archivo, si el repo
  tiene grafo, formulá 1-2 preguntas sobre el área a tocar.
- Investigar un bug o soporte: "¿qué llama a `ServicioLiquidacion`?", "¿cómo llega un
  request desde el controller hasta la tabla X?" — el grafo traza la conexión real en vez
  de que la infieras leyendo archivo por archivo.
- Cualquier pregunta de arquitectura/comportamiento sobre un repo que ya tiene
  `graphify-out/` — hoy: `ms-decampopagos`, `ms-compliance`, `apigateway`.

**No usar** para reglas de negocio o de producto — esas siguen viniendo de `dcac-context/`
y `product-dcac/` (regla del workspace: doc primero). El grafo es estructura de **código**,
no documentación de dominio.

## Chequeo previo (no bloqueante)

Por cada repo involucrado, verificá si existe `microservicios/<ms>/graphify-out/graph.json`
(o `webadmin/webadmin/graphify-out/graph.json`, etc.). **Si no existe, no es un error**: no
lo menciones como problema, no sugieras instalar `graphify`, no le preguntes al usuario —
simplemente seguí con la exploración normal (Explore/grep) para ese repo. Esta skill solo
aplica donde ya hay un grafo construido.

## Chequeo de frescura (best-effort, no bloqueante)

El grafo puede estar desactualizado si el repo tuvo commits después de generarlo. Antes de
confiar en la respuesta:

```bash
GRAPH_MTIME=$(stat -c %Y microservicios/<ms>/graphify-out/graph.json)
LAST_COMMIT=$(git -C microservicios/<ms> log -1 --format=%ct)
```

Si `LAST_COMMIT` > `GRAPH_MTIME`, el grafo es más viejo que el último commit — avisá con
una línea ("grafo de `<ms>` es de antes del último commit, puede no reflejar cambios
recientes") **y seguí igual**: el grafo sigue siendo útil como mapa aproximado, y regenerarlo
(`/graphify microservicios/<ms> --update`) es decisión del usuario, no algo que dispares solo.

## Cómo consultar

Corré los comandos con el **cwd en la raíz del repo** (`graphify-out/` es relativo al
directorio actual):

```bash
cd microservicios/<ms>
graphify query "¿Qué servicios llaman a ServicioLiquidacion?"        # BFS, contexto amplio
graphify query "¿Cómo se calcula el saldo combinado?" --dfs          # DFS, un camino puntual
graphify path "ControllerX" "TablaY"                                  # camino más corto entre dos nodos
graphify explain "ServicioLiquidacion"                                # explicación en lenguaje llano de un nodo
```

- `query` (BFS) para preguntas abiertas de "cómo funciona X" — da contexto amplio.
- `query --dfs` o `path` cuando ya sabés el punto de partida y el de llegada (típico en
  debugging: "el bug está en algún lado entre el endpoint y la tabla, trazá el camino").
- `explain` para entender un nodo puntual (una clase, un servicio) sin rastrear todo el flujo.

## Reglas duras (heredadas de `graphify`)

- **Nunca afirmes una relación que el grafo no tenga.** Citá `source_location` de la
  respuesta cuando uses algo del grafo para justificar una decisión de plan o diagnóstico.
- **El grafo es atajo de exploración de código, no reemplaza `dcac-context/`.** La
  prioridad documental del workspace sigue siendo: doc (`dcac-context/`/`product-dcac/`) →
  `CLAUDE.md` del repo → código (grafo incluido acá) como fallback.
- **No generes ni regeneres un grafo por tu cuenta.** Consumís los que ya existen; crear uno
  nuevo (`/graphify <repo>`) o actualizarlo (`--update`) es una decisión del usuario.

## Errores comunes

- **Tratar "no hay grafo" como bloqueante** → no, seguí con exploración normal sin comentarlo.
- **Confiar en el grafo para reglas de negocio** → no; eso viene de `dcac-context/`/`product-dcac/`.
- **Correr `graphify query` desde el directorio equivocado** → el cwd tiene que ser la raíz
  del repo (`microservicios/<ms>`), no el root del workspace ni otro subdirectorio.
- **Instalar/regenerar un grafo sin que el usuario lo pida** → solo avisar si está desactualizado
  y seguir; regenerar es decisión del usuario.
- **Usar esto en vez de leer el código real** → `planear-ticket` sigue exigiendo leer
  con Read los archivos que se van a modificar; el grafo acelera encontrar cuáles son, no
  reemplaza esa lectura.
