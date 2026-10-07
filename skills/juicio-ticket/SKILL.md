---
name: juicio-ticket
description: Usar cuando un ticket del workspace dcac-ia-context ya tiene plan (plan.md) y tests (tests.md) escritos por agentes generativos separados y hay que juzgarlos antes de implementar, o cuando la implementación ya pasó GREEN y hay que juzgarla contra el plan y las reglas del workspace — un Juez compara los artefactos entre sí, contra la documentación del proyecto y contra lo solicitado; los agentes generativos se defienden; peritos verifican para el Juez cómo llegó cada agente a sus conclusiones (y las respuestas del Baqueano); lo que el Juez sostiene lo corrige el mismo agente, solo en lo marcado, y el Juez verifica solo la corrección. Es la fase 2 (El juicio) de resolver-ticket y el paso 3.4 (juicio de la implementación). Triggers — "juzgá T#####", "que el juez revise el plan y los tests", "llevá T##### a juicio". NO escribe plan ni tests, NO ejecuta tests.
---

# El juicio

El plan y los tests los escriben **agentes generativos** distintos, desde la spec, sin verse
entre sí. Cuando los dos terminan, se presentan ante un **Juez**. El Juez busca
incongruencias entre los dos artefactos, de cada uno con el proyecto, y entre lo
solicitado y lo que el proyecto permite. Los agentes se defienden. Los **peritos**
investigan, para el Juez y nadie más, si lo que dicen los agentes es verdad.

**Lo que el Juez sostiene, lo corrige el mismo agente, y solo eso.** Nadie rehace lo que ya
estaba bien: el agente se retoma con su contexto, corrige lo marcado, y el Juez verifica la
corrección sin volver a juzgar todo el artefacto.

## Los roles y sus modelos

| Rol | Quién | Modelo | Ve | No ve |
|-----|-------|--------|----|-------|
| **Agente generativo del plan** | Subagente con `planear-ticket` | `opus` | `spec.md`, la doc, el código, su `plan.md`, su bitácora, la acusación contra su artefacto | `tests.md`, lo del otro agente, los peritajes |
| **Agente generativo de los tests** | Subagente con `planear-tests-ticket` | `sonnet` | `spec.md`, la doc, la DB, su `tests.md`, su bitácora, la acusación contra su artefacto | `plan.md`, lo del otro agente, los peritajes |
| **Baqueano** | Subagente con `baqueano`, uno por agente generativo | `sonnet` | Las dudas de su agente y todas las fuentes | Los artefactos y bitácoras de los agentes, los peritajes |
| **Juez** | Subagente que acusa y sentencia (ver "El Juez, acotado") | `opus` | Spec, artefactos, bitácoras; la doc solo siguiendo una cita o para verificar una regla concreta | No ejecuta nada |
| **Verificador** | Subagente nuevo por cada tanda de correcciones | `sonnet` | La observación, la corrección anotada y lo que cambió en el artefacto | El resto del juicio |
| **Perito** | Subagente por cada orden de peritaje | `haiku` | Lo que el Juez le ordena verificar, la bitácora o las consultas investigadas, las fuentes, el código; puede interrogar | La sentencia; no opina sobre la calidad del artefacto |
| **Orquestador** | El hilo principal | — | Los contratos de salida, para rutear | **No lee `juicio/peritajes/`** ni toma partido; no genera ni defiende nada |
| **Usuario** | El usuario | — | Todo | — |

Los agentes generativos nunca se ven entre sí. Lo que necesiten en común (el contrato) vive
en `spec.md`, en `## Decisiones de contrato`, y lo decide el usuario.

## El oficio de un agente generativo

Cada agente generativo recibe estas reglas en su prompt (el orquestador las copia):

> Sos el agente generativo de **{plan|tests}** de T#####. Cuando termines, te vas a
> presentar ante un Juez que va a revisar tu trabajo contra la spec y la documentación.
> 1. **No inventes evidencia.** Un perito va a abrir tus citas y te puede interrogar. Una
>    fabricación probada te obliga a corregir y hace que se re-verifiquen tus demás citas.
> 2. **Si el Juez tiene razón, aceptá y corregí** solo lo que marcó. Reconocer un error es
>    lo más barato para todos.
> 3. **Si no la tiene, defendete con evidencia.** "Lo decidí así" no es defensa.
> 4. **Una duda honesta vale más que un supuesto.** Lo que la spec no dice, devolvelo como
>    DUDA.
> 5. **Escribí tu bitácora mientras trabajás**, y si una decisión sale de una respuesta del
>    Baqueano, citá la consulta (`C3`).

### Faltas (quedan en el prontuario del agente)

| Falta | Cuándo | Consecuencia |
|-------|--------|--------------|
| `fabricacion` | Un perito probó evidencia inventada o tergiversada | Corrige lo marcado, y el Juez ordena re-verificar por muestreo sus demás citas |
| `defensa-perdida` | El Juez sostuvo una observación que el agente defendió | Corrige lo marcado |
| `correccion-fallida` | La corrección no resolvió la observación o rompió otra cosa | Un segundo intento; si vuelve a fallar, se escala al usuario |

Nadie muere y nadie rehace de cero. Si un agente ya no está disponible para `SendMessage`,
se despacha uno nuevo **con el artefacto, la bitácora y la acusación**, para que continúe
desde donde quedó, no para que empiece de nuevo.

El prontuario (faltas por agente) queda en la sentencia y lo cuenta el Cronista.

## El Juez, acotado

El Juez es el rol más caro (opus, y el que más lee). Tres reglas para que no se dispare:

1. **No ejecuta nada.** Ni lint, ni tests, ni la app. Si duda de una afirmación, ordena un
   peritaje (haiku): verificar es trabajo del perito. En T23814 un Juez que verificó en
   persona tardó 445 s y gastó 171k tokens en la ronda 1, repitiendo pruebas que el
   agente del plan ya había hecho.
2. **Lee acotado.** Spec (con sus decisiones), los dos artefactos y las bitácoras. A la doc
   del proyecto, a otros tickets o al código entra **siguiendo una cita** de una bitácora o
   para verificar una regla concreta que va a invocar, no recorriéndolos enteros.
3. **No se lo retoma para verificar.** Acusa (ronda 1), ordena peritajes (ronda 3) y
   sentencia (ronda 5). La verificación de correcciones es del verificador (ronda 6).

El orquestador le pasa en el prompt la lista exacta de lo que lee, y nunca le ofrece
"podés correr comandos".

## La carpeta del juicio

```
docs/{proyecto}/{tipo}/T#####-{slug}/
├── spec.md
├── plan.md
├── tests.md
└── juicio/
    ├── bitacora-plan.md       ← la escribe el agente del plan mientras trabaja
    ├── bitacora-tests.md      ← la escribe el agente de tests mientras trabaja
    ├── consultas-plan.md      ← Baqueano del plan
    ├── consultas-tests.md     ← Baqueano de los tests
    ├── acusacion-plan.md      ← Juez
    ├── acusacion-tests.md     ← Juez
    ├── defensa-plan.md        ← agente del plan
    ├── defensa-tests.md       ← agente de tests
    ├── peritajes/             ← peritos; solo los lee el Juez
    ├── correccion-plan.md     ← agente del plan: qué cambió por cada observación sostenida
    ├── correccion-tests.md    ← agente de tests
    └── sentencia.md           ← Juez + decisiones del usuario
```

## La bitácora (lo que el perito investiga)

Cada agente generativo escribe su bitácora **mientras trabaja**, corta y concreta:

```markdown
# Bitácora — {plan|tests} · T#####

## Fuentes consultadas
| # | Fuente (ruta § sección, o ruta:línea) | Qué saqué de ahí |

## Decisiones
| # | Decisión | Por qué | Fuentes (# de arriba, o consulta C#) |

## Supuestos y dudas

## Presentación ante el Juez
Cada criterio de la spec → la parte del plan o el caso de test que lo cubre.
```

## Las fuentes y su autoridad

1. `spec.md`, incluida `## Decisiones de contrato`.
2. `product-dcac/00_context/` si existe.
3. `dcac-context/`: `context/business/`, `features/<feature>/`, `back/services/<ms>.md`,
   `back/conventions.md`, `back/database-ownership.md`, `api/*.json`.
4. `CLAUDE.md` de cada repo tocado.
5. El código en master, solo para saber cómo se comporta algo hoy.

## El procedimiento

### Ronda 0 — Presentación

El juicio empieza **cuando los dos agentes terminaron**: `plan.md`, `tests.md` y las dos
bitácoras escritas, y sus DUDAS respondidas (por el Baqueano o por el usuario). No se juzga
a uno solo.

### Ronda 1 — Acusación

```
Agent(subagent_type: "general-purpose", model: "opus", description: "Juez T#####",
      prompt: "Invocá la skill clarabella:juicio-ticket, rol Juez, ronda 1, para T#####
               (proyecto {proyecto}, tipo {tipo}, slug {slug}). Escribí
               juicio/acusacion-plan.md y juicio/acusacion-tests.md y devolvé el contrato
               del Juez.")
```

**Guardá su id:** el mismo Juez lleva todo el juicio vía `SendMessage`.

**Qué juzga:**

| Sobre | Busca |
|-------|-------|
| Lo solicitado | Si la spec tiene sentido frente al proyecto: contradice una regla documentada, pide algo que una regla crítica impide, o es ambigua en un punto que cambia el resultado. Es `spec-cuestionada` y va al usuario |
| El plan | Que cubra cada criterio de la spec; que respete las reglas críticas (los ms no se comunican entre sí, cada ms solo toca sus tablas, sin estado en propiedades de clase en Hyperf/apigateway); que use el contrato de la spec; que siga las convenciones del servicio |
| Los tests | Que cada caso salga de un criterio de la spec; que el esperado sea consistente con las reglas documentadas; que rutas, códigos y formatos coincidan con la spec y las convenciones; que cada verificación consulte una tabla del servicio dueño; que el "Esperado en RED" sea coherente |
| Los dos entre sí | Que usen el mismo contrato y describan el mismo comportamiento |

**Regla de redacción:** cada observación se formula contra una **fuente**, nunca contra el
otro artefacto, para que cada agente se defienda sin enterarse de lo que hizo el otro.
Cuando plan y tests se contradicen y **ninguna fuente lo resuelve**, no es culpa de
ninguno: va a la sentencia como decisión de contrato para el usuario.

```markdown
### O3 · bloqueante
- **Dice el artefacto:** <cita textual, con sección o caso>
- **Dice la fuente:** <cita textual> — `<ruta>` § <sección>
- **Por qué no cierra:** <una o dos líneas>
- **Propuesta:** <qué cambiaría>
```

Severidad: `bloqueante` (contradice la spec, una regla crítica o una regla de negocio
documentada, o deja un criterio sin cubrir) o `menor` (se aparta de una convención o es
impreciso, sin cambiar el comportamiento). Lo que no tiene fuente es SUGERENCIA.

### Ronda 2 — Defensa (los dos agentes en paralelo)

```
SendMessage(to: "<id del agente de {rol}>", message: "El Juez te acusa. Invocá la skill
  clarabella:juicio-ticket, rol agente generativo, ronda 2. Respondé cada observación de
  juicio/acusacion-{rol}.md en juicio/defensa-{rol}.md.")
```

| Respuesta | Qué hace el agente |
|-----------|--------------------|
| `ACEPTO` | Corrige su artefacto **solo en lo marcado** y lo anota en `correccion-{rol}.md` |
| `ACEPTO PARCIAL` | Corrige lo que acepta y defiende el resto con evidencia |
| `DEFIENDO` | No cambia nada y presenta evidencia |

Una defensa válida muestra, con cita verificable: una fuente de más autoridad que dice lo
contrario; que la fuente citada no aplica; que el Juez leyó mal; o que la fuente está
desactualizada y el código dice otra cosa (ruta:línea). Si la decisión salió de una
respuesta del Baqueano, el agente lo dice citando la consulta que ya figuraba en su
bitácora.

### Ronda 3 — Orden de peritaje

El Juez retomado lee las defensas y ordena peritajes **solo donde no puede dar la evidencia
por buena a simple vista**. Cada orden pide verificar puntos concretos, no "todo":

```
PERITAJES:
  - [P1] agente: plan · verificar: <afirmación concreta> · fuentes declaradas: <...>
  - [P2] baqueano: tests · verificar: C3 · usada en: <decisión del agente>
```

### Ronda 4 — Peritaje (los peritos en paralelo)

```
Agent(subagent_type: "general-purpose", model: "haiku", description: "Perito P1 T#####",
      prompt: "Invocá la skill clarabella:juicio-ticket, rol perito, para T##### (proyecto
               {proyecto}, tipo {tipo}, slug {slug}). Orden: [P1] <textual>. Escribí
               juicio/peritajes/P1.md. Tu informe es solo para el Juez.")
```

**Cómo trabaja el perito.** Frío y acotado: verifica solo lo que dice la orden.
1. **Verificar citas:** abrir cada fuente citada y confirmar que existe y dice eso.
2. **Seguir la bitácora o las consultas:** ¿la conclusión sale de lo declarado? ¿La defensa
   coincide con lo anotado mientras trabajaba?
3. **Contrastar con el código** si alguien dice que la doc está desactualizada.
4. **Interrogar** solo si hace falta: devuelve `PREGUNTAS_AL_AGENTE`, el orquestador se las
   pasa textuales con `SendMessage` (respuesta en `juicio/peritajes/P1-interrogatorio.md`)
   y lo retoma. Un interrogatorio por peritaje.

```markdown
# Peritaje P1 · {agente} · T#####
## Orden
## Hallazgos
| # | Qué se verificó | Cómo | Resultado |
## Dictamen
CONFIRMADA | NO CONFIRMADA | FALSA | INCONCLUSA — <una línea>
```

`FALSA` es solo para evidencia inventada o tergiversada, con la prueba. Un error honesto es
`NO CONFIRMADA`. **Los peritajes son del Juez:** el orquestador no los lee ni los resume.

### Ronda 5 — Sentencia

| Fallo | Cuándo |
|-------|--------|
| `RETIRO` | La defensa demostró que la observación no correspondía |
| `SOSTENGO` | La defensa no tiene evidencia válida, o el peritaje no la confirmó |
| `ESCALO` | Las dos posiciones tienen respaldo (fuentes contradictorias, doc desactualizada, spec cuestionada): decide el usuario |

Para cada `ACEPTO`, el Juez mira **solo el cambio** que el agente anotó en
`correccion-{rol}.md` y confirma que resuelve la observación sin romper otra cosa.

Un peritaje `FALSA` suma la falta `fabricacion`: el Juez ordena un peritaje de muestreo
sobre las demás citas de ese agente (las que sostienen decisiones bloqueantes) y lo que no
se confirme entra como observación nueva.

### Ronda 6 — Corrección y verificación

Cada agente con observaciones sostenidas se retoma con `SendMessage` y corrige **solo
esas**, anotando cada cambio en `correccion-{rol}.md` (observación → qué cambió, dónde).
Los dos en paralelo.

Los cambios los verifica un **verificador** nuevo (`sonnet`), no el Juez retomado: retomar
al Juez arrastra todo su contexto (en T23814, 200k tokens para verificar un renombre de
nueve líneas). El verificador recibe solo la observación, `correccion-{rol}.md` y lo que
cambió en el artefacto, y verifica **solo esos cambios**: no vuelve a acusar el artefacto
entero. Escribe su resultado en la sentencia.
- Resuelto → la observación se cierra.
- No resuelto o rompió algo → `correccion-fallida`, segundo intento.
- Segundo intento fallido → se escala al usuario con la observación, los dos intentos y por
  qué no alcanzaron.

La verificación de una corrección puede generar una observación nueva solo si el cambio
contradice una fuente. Lo que el Juez ya había aceptado no se reabre.

### Cierre — decide el usuario

`juicio/sentencia.md`:

```markdown
# Sentencia — T#####

## Prontuario
| Agente | Faltas | Correcciones | Resultado |

## Observaciones
| Obs | Artefacto | Severidad | Respuesta | Peritaje | Fallo | Corrección |

## Para decidir el usuario
### O5 · tests · escalada
- **Observación:** <textual>
- **Defensa:** <textual>
- **Peritaje:** <dictamen, si hubo>
- **Por qué escalo:** <razón>
- **Decisión del usuario:** <pendiente>

## Spec cuestionada
## Decisiones de contrato
## Documentación a revisar
```

El orquestador le presenta al usuario la sentencia **copiando las posiciones textuales**,
sin resumir ni tomar partido. Con sus decisiones: se anotan en `sentencia.md`, las de
contrato van a `spec.md`, cada agente aplica las que le tocan (otra vez solo en lo
afectado), y el usuario aprueba `plan.md` y `tests.md` finales.

## El Baqueano en el juicio

Cuando una observación cae sobre algo que se apoya en una respuesta del Baqueano, hay que
saber de quién es el error.

1. **Rastro.** La consulta tiene que figurar en la bitácora del agente desde antes. Si
   aparece recién en la defensa, no lo excusa.
2. **Peritaje sobre el Baqueano** (`[P2] baqueano: …`): el perito abre sus citas y su
   "dónde busqué", y puede interrogarlo.
3. **Fallo:**
   - **Error del agente** (la respuesta era buena y la usó mal): corrige el agente.
   - **Error del Baqueano** (`fabricacion`, `respuesta-erronea` o `decidio-por-el-usuario`,
     ver `baqueano`): el Baqueano se retoma, **corrige esa respuesta** y revisa las otras
     respuestas suyas que el agente citó en decisiones bloqueantes. El agente actualiza solo
     las partes que dependían de las respuestas que cambiaron. La falta va al prontuario del
     Baqueano, no al del agente.
   - **Las dos cosas:** corrigen los dos, cada uno lo suyo.

## Juicio de la implementación (fase 3)

GREEN verifica el comportamiento, pero no ve estado guardado en propiedades de clase en
Hyperf/apigateway, un ms que lee tablas ajenas, ms que se llaman entre sí, desvíos del plan
aprobado ni convenciones del servicio. Con GREEN completo, la implementación va a juicio.

**Acusados:** los implementadores (un subagente por repo, o el hilo principal si implementó
él; en ese caso, al presentar la sentencia copia las posiciones textuales). **Juez:** uno
nuevo y acotado, no el de la fase 2 retomado (arrastraría todo el contexto del juicio del
plan). Lee solo el diff, el plan aprobado, `spec.md` § Decisiones de contrato, las
bitácoras de los implementadores y las convenciones aplicables; no relee PRD, diagramas ni
otros tickets, que ya juzgó la fase 2, y no ejecuta nada: GREEN ya corrió.

**Qué juzga**, sobre `git -C .worktrees/T#####-{slug}/<ms> diff master`:

| Contra | Busca |
|--------|-------|
| El plan aprobado | Que cada Parte esté implementada; cambios fuera del plan sin anotar en la bitácora; los tests unitarios que el plan pedía |
| Las reglas críticas | Estado en propiedades de clase (salvo dependencias inyectadas por DI), tablas de otro servicio, comunicación directa entre ms |
| Las convenciones | `dcac-context/back/conventions.md`, el `CLAUDE.md` del repo, el código vecino, sin comentarios salvo que el archivo ya los use |

Mismas rondas y mismo modelo de corrección: lo sostenido lo corrige el implementador de ese
repo, solo en lo marcado; después corre un GREEN nuevo sobre los repos tocados y el Juez
verifica la corrección. Lo escalado: en el flujo manual, al usuario; en el ciclo, pasa por
el Baqueano (menor o provisoria).

Archivos en `juicio/implementacion/`: `bitacora-<ms>.md`, `acusacion-<ms>.md`,
`defensa-<ms>.md`, `correccion-<ms>.md`, `peritajes/`, `sentencia.md`.

## Contratos de salida

**Juez:**
```
ARTEFACTO: <archivos escritos en juicio/>
RONDA: 1 | 3 | 5 | 6
RESULTADO: <ronda 1: N observaciones (B bloqueantes) · ronda 5: fallos · ronda 6: correcciones verificadas>
PERITAJES: (solo ronda 3)
  - [P1] agente|baqueano: <rol> · verificar: <...>
A_CORREGIR: (ronda 5)
  - <rol>: O2, O5
DUDAS:
  - [D1] <spec cuestionada, decisión de contrato, fuentes contradictorias>
ESTADO: completo | con-correcciones | frenado-por-duda
```

**Perito:**
```
ARTEFACTO: juicio/peritajes/P<n>.md
PREGUNTAS_AL_AGENTE: <pregunta textual> | (ninguna)
DICTAMEN: CONFIRMADA | NO CONFIRMADA | FALSA | INCONCLUSA
ESTADO: completo | esperando-respuestas
```

El orquestador usa el dictamen solo para saber que el perito terminó; no lo comenta.

**Agente generativo, rondas 2 y 6:**
```
ARTEFACTO: juicio/defensa-{rol}.md o juicio/correccion-{rol}.md
RESULTADO: <ronda 2: X acepto · Y parcial · Z defiendo · ronda 6: N corregidas>
ESTADO: completo
```

## Errores comunes

- **Rehacer el artefacto entero por una observación** → se corrige solo lo marcado.
- **Que el Juez vuelva a acusar todo después de una corrección** → verifica solo el cambio.
- **Juzgar a un solo agente porque el otro no terminó** → el juicio empieza con los dos.
- **Que el Juez escriba observaciones contra el otro artefacto** → siempre contra una fuente.
- **Que el orquestador lea, resuma o use un peritaje** → son del Juez.
- **Ordenar peritajes de "todo"** → cada orden verifica puntos concretos.
- **Marcar `FALSA` un error honesto** → `FALSA` es invención probada; lo demás es `NO CONFIRMADA`.
- **Cargarle al agente el error de una respuesta mala del Baqueano** → la falta es del
  Baqueano, y corrige él primero.
- **Dar más de dos intentos de corrección** → al segundo fallo, decide el usuario.
- **Corregir `dcac-context/` dentro del juicio** → se lista en "Documentación a revisar".
