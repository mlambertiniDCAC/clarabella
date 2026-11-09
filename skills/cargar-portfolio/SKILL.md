---
name: cargar-portfolio
description: Usar cuando el usuario trae un bloque crudo de novedades sobre sus proyectos y hay que cargarlo al cerebro de contexto — notas de una reunión, texto pegado, lo que le dictó otra herramienta. El bloque no viene etiquetado y puede hablar de un proyecto o de diez. Triggers — "cargá esto al portfolio", "tomá estas notas de la reunión", "actualizá los proyectos con esto", "procesá esto". NO consulta el contexto (eso es consultar-portfolio) ni escribe en el tablero de producto.
---

# Cargar al cerebro de contexto

Entra material crudo sin destino declarado, sale archivado en el proyecto que le
corresponde. **Vos clasificás; los scripts no opinan.**

## Chequeo previo (no bloqueante)

El cerebro vive en un repo aparte. Resolvé su raíz en este orden: `$CEREBRO_RAIZ`, o
`~/projects/portfolio`.

Si no existe, **no es un error**: decile al usuario en una línea que el repo del cerebro
no está y que sin él no hay dónde archivar. No lo crees por tu cuenta.

El CLI es `<raiz>/bin/cerebro` y resuelve el almacén desde su propia ubicación, así que
**invocalo siempre por su ruta completa** (`~/projects/portfolio/bin/cerebro ...`) y no
desde un `cerebro` suelto que dependa del directorio en que estés parado. Si lo corrés mal,
archiva en el repo equivocado sin avisar.

Todo lo que sigue pasa por el CLI. Editar los `.md` del almacén a mano no rompe nada —
`escribir` conserva los campos y las secciones que agregues — pero el CLI es el camino
normal.

## Cómo está organizado un proyecto

```
proyectos/<slug>/
  proyecto.md            el índice: estado, pendientes, relaciones, anotaciones, artifacts
  decisiones.md          cuando el proyecto lo tiene
  prd/                   PRD, tech-spec, gaps, discovery
  tickets/               tickets redactados, todavía sin número
  desarrollo/T#####-<slug>/
  soporte/T#####-<slug>/
  lotes/L-YYYY-MM-DD-<slug>/
  notas/
  adjuntos/              PDF, imágenes, diagramas, CSV
```

`transversal/<slug>/` tiene la misma forma y guarda lo que no es de ningún proyecto: el
módulo dCP, el perímetro PSP, Keycloak, los UMLs, las vacunas de dependencias.

Las novedades que cargás van a `proyecto.md` por el CLI. Las carpetas son documentos: si hay
que guardar un archivo, va a la categoría que le corresponde y se menciona en una anotación,
nunca se mete en `proyecto.md`.

## Paso 1 — Partir el bloque en unidades

Una unidad es **una novedad**. Si el bloque dice tres cosas sobre dos proyectos, son tres
unidades. No agrupes por proyecto: una unidad que habla de dos proyectos se parte en dos.

No resumas ni reescribas. El texto de la unidad es el del usuario, salvo lo que saque el
paso 3.

## Paso 2 — Clasificar cada unidad

Cuatro clases, y cada una se archiva distinto:

| Clase | Qué es | Cómo se archiva |
|---|---|---|
| **info** de proyecto | Lo que el proyecto es: alcance, decisiones, links, quién lo lleva | `cerebro anotar <slug> --texto "..." --origen "..."` |
| **estado** de proyecto | Dónde está parado: etapa, bloqueo, qué falta | `cerebro estado <slug> --texto "..."` |
| **relación** entre proyectos | Que A es la versión de B, que C depende de D | `cerebro relacionar <slug> <version-de\|depende-de\|relacionado-con> <otro>` |
| **cambio drástico** | Se cancela, se parte en dos, cambia de squad o de dueño; puede afectar a varios proyectos de una vez | Una operación por proyecto afectado, la que corresponda de las tres de arriba |

`estado` sobrescribe el vigente y manda el anterior al histórico. Usalo solo cuando la
unidad dice dónde está parado el proyecto; una novedad de contenido es **info**, no estado.

Cuando la unidad trae un dato de cabecera y no un párrafo, va al campo y no al estado:
`cerebro campo <slug> etapa "Desarrollo"`, `prioridad "Crítica"`, `bloqueado si|no`. Los
campos fijables son `etapa`, `prioridad`, `bloqueado`, `docs` y `tablero`. El nombre y el
squad no se fijan por acá: salen de `catalogo.md`, y si el tablero los cambió se alinean
con `cerebro sincronizar`.

Si la unidad trae un pendiente nuevo, `cerebro pendiente-agregar <slug> --texto "..."`. Si
cierra o desbloquea uno que ya existe, mirá el contexto con `cerebro contexto <slug>`,
buscá su número de orden y usá `cerebro pendiente-estado <slug> <orden> <estado>`
(`abierto`, `en-curso`, `bloqueado` con `--motivo`, `cerrado`). **No agregues un pendiente
nuevo para algo que ya está en la lista.**

La prioridad la pone el usuario, nunca vos: el orden de los pendientes se cambia solo si
él lo pide, con `cerebro pendiente-reordenar`.

Si el bloque menciona un artifact que armaron juntos, registralo:
`cerebro artifact-registrar <slug> --url "..." --titulo "..." --descripcion "..."`.
La descripción es un párrafo, no una línea: decí qué resuelve y, si reemplaza a otro
artifact anterior del mismo tema, cuál.

**Si te das cuenta de que archivaste algo en el proyecto equivocado**, no lo dejes:
`cerebro anotacion-borrar <slug> <n>` saca la anotación (la 1 es la más nueva) y
`cerebro desrelacionar <slug> <tipo> <otro>` borra las dos puntas de una relación. Después
archivá de nuevo donde iba, o mandalo a la bandeja.

## Paso 3 — Sacar el dato sensible antes de archivar

El perímetro de estos proyectos toca plata. **No archives** importes de operaciones
reales, números de cuenta, CBU, CVU, ni fragmentos crudos donde aparezcan.

Archivá la novedad sin el dato y dejá la referencia a dónde vive ("el importe está en la
operación tal", "la cuenta figura en el legajo"). Si al sacarlo la unidad deja de decir
algo, mandala a la bandeja con motivo `sensible` en lugar de archivarla recortada.

## Paso 4 — Resolver el proyecto

Por cada unidad: `cerebro resolver-nombre "<lo que la unidad nombra>"`.

La respuesta trae una `certeza`:

- `exacta` o `alias` → **archivá** con el `slug` que devolvió. No preguntes.
- `ambigua` → `cerebro bandeja-encolar --texto "..." --motivo ambigua --candidatos "a; b" --origen "..."`
- `desconocida` → `cerebro bandeja-encolar --texto "..." --motivo desconocida --origen "..."`

**Nunca inventes un proyecto que no está en el catálogo**, ni elijas entre candidatos por
tu cuenta. El catálogo es vocabulario cerrado: lo que no resuelve, va a la bandeja. Eso no
es una falla, es el diseño.

El squad LyC puede estar sin cargar en el catálogo. Si varias unidades caen
`desconocida` y todas suenan a un mismo squad, decilo en el informe: probablemente falte
poblarlo, no está mal clasificado.

## Paso 5 — Informar en una línea

Cuántas unidades se archivaron, en qué proyectos, y cuántas quedaron en la bandeja. Si hay
bandeja, agregá que se revisa con `cerebro bandeja-listar`.

No enumeres una por una lo que archivaste con certeza: el usuario pidió dejar de revisar
proyecto por proyecto.

## Errores comunes

- **Pedir confirmación de lo que resolvió con certeza** → no; eso devuelve el trabajo que
  la skill vino a quitar. Solo la bandeja llega a sus ojos.
- **Elegir entre dos candidatos de una ambigüedad** → va a la bandeja con los dos.
- **Crear un proyecto nuevo porque el nombre no estaba** → nunca.
- **Usar `estado` para una novedad de contenido** → eso es `anotar`; `estado` pisa el
  vigente.
- **Archivar un importe o un CBU** → sale, con referencia a dónde vive.
- **Invocar `cerebro` sin su ruta completa** → archiva en el directorio en que estés.
- **Dejar algo mal archivado porque ya se escribió** → hay comandos para deshacerlo.
- **Escribir en `proyectos.dcac.ar`** → nunca desde acá, ni siquiera si la unidad dice que
  hay que actualizar el tablero. Eso el usuario lo pide aparte y a mano.
