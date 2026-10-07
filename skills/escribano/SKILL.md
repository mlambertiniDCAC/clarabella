---
name: escribano
description: Usar al arrancar un ticket del workspace dcac-ia-context, ANTES de despachar a cualquier agente, para revisar la spec y dar fe de si está completa — el Escribano lista los puntos que la spec deja abiertos, las contradicciones con la documentación y con tickets anteriores, y los huecos de contrato que nadie mencionó (entradas inválidas, duplicados, permisos, códigos de error…), descarta lo que el usuario ya decidió, y le presenta al usuario todo lo demás en una sola ronda, cada punto con opciones y una propuesta por defecto. Con las respuestas, la spec queda escriturada y recién ahí arrancan los agentes. Triggers — "que el escribano revise la spec de T#####", "escriturá la spec", paso 0 de resolver-ticket y etapa 0 de ciclo-ticket. NO planea, NO escribe tests.
---

# El Escribano

Casi todas las dudas que frenan a los agentes se podían ver en la spec antes de empezar: la
spec deja puntos abiertos, choca con otro documento o no dice qué pasa en un caso borde.
El Escribano lee la spec **antes** de que trabaje nadie y da fe de lo que falta. El
usuario responde todo junto, una sola vez, y los agentes arrancan con la spec cerrada.

## Quién y cuándo

Un subagente nuevo (`general-purpose`, `model: "sonnet"`), despachado:
- en el paso 0 de `resolver-ticket`, con `spec.md` ya guardada;
- en la etapa 0 de `ciclo-ticket`.

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "Escribano T#####",
      prompt: "Invocá la skill clarabella:escribano para T##### (proyecto {proyecto}, tipo
               {tipo}, slug {slug}). Revisá spec.md, escribí escritura.md y devolvé el
               contrato.")
```

## Qué busca

**1. Lo que la spec deja abierto.** Las secciones tipo "A cerrar dentro del ticket", los
"definir si…", los "a confirmar", las preguntas sin respuesta.

**2. Contradicciones.** Lo que la spec dice contra lo que dicen otras fuentes: la
documentación del proyecto, planes y sentencias de tickets anteriores, el código actual
(cuando la spec describe "qué hay hoy" y el código dice otra cosa).

**3. Huecos de contrato.** Recorre esta lista y pregunta **solo lo que aplica** al ticket:

| Tema | La pregunta típica |
|------|--------------------|
| Entradas inválidas o vacías | ¿Un filtro con un valor que no existe da `400`, se ignora o da resultado vacío? |
| Cardinalidad y duplicados | ¿Puede venir el mismo elemento dos veces? ¿Cuál gana? |
| Permisos y roles | ¿Quién puede usarlo? ¿Qué recibe el que no puede: `401`, `403` o resultado vacío? |
| Códigos de respuesta | ¿Qué devuelve en cada error que el ticket implica? |
| Forma de la respuesta | ¿Array plano o envuelto? ¿Qué campos, cuáles nunca? |
| Orden, paginación, límites | ¿Importa el orden? ¿Hay tope? |
| Consumidores actuales | ¿Quién usa lo que cambia y cómo se coordina el deploy? |
| Datos y migraciones | ¿Hace falta migración? ¿Qué pasa con los datos existentes? |
| Datos de prueba y credenciales | ¿Con qué usuarios y datos se va a probar? |
| Documentación | ¿Se actualiza algún doc como parte del ticket? |

**4. Lo que ya está decidido.** Antes de preguntar algo, lo busca en
`docs/<proyecto>/decisiones.md`, en la memoria y en las decisiones registradas de tickets
anteriores (mismas reglas que el `baqueano`: precedente es solo una decisión registrada del
usuario). Si ya está decidido, no lo pregunta: lo lista como precedente, con derecho a veto.

**Lo que no pregunta:** detalles de desarrollo. Al usuario le van el negocio, el contrato
externo (lo que ve un consumidor del servicio o del endpoint) y las convenciones del
equipo (idioma de los nombres, documentación, cómo se prueba). No le van qué clase tocar,
qué patrón copiar, qué exporta un módulo internamente, los tipos de una firma interna o el
alcance técnico de una regla de lint: eso es trabajo del agente del plan, que lo decide y
lo justifica en su bitácora, y el Juez lo revisa. Si el Escribano ve un problema de ese
tipo (por ejemplo, una regla del ticket que bloquea algo que el mismo ticket necesita), lo
anota en "Fuera de la escritura" con su propuesta, para el agente del plan.

## La escritura — `escritura.md`

En la carpeta del ticket:

```markdown
# Escritura — T#####

## Puntos para decidir
### E1 · <tema> · abierto en la spec | contradicción | hueco de contrato
- **Qué falta definir:** <una o dos líneas>
- **Qué dicen las fuentes:** <cita> — `<ruta>` § <sección> (o "ninguna fuente lo trata")
- **Opciones:** a) … / b) … / c) …
- **Propuesta por defecto:** <la opción más conservadora o la que respalda la práctica previa>, porque <razón>
- **Decisión del usuario:** <pendiente>

## Ya decidido (precedentes, con veto)
- <decisión> — `<fuente>`

## Fuera de la escritura
<lo que el Escribano vio pero es de implementación, no de contrato>
```

**La propuesta por defecto** está para que el usuario pueda contestar rápido ("todas por
defecto salvo E3"). Es una propuesta, no una decisión: hasta que el usuario responde,
ningún punto está cerrado.

## Después

El orquestador le presenta al usuario `escritura.md` en una sola ronda. Con las respuestas:
1. Anota cada decisión en `escritura.md` ("Decisión del usuario").
2. Las agrega a `spec.md`, en `## Decisiones de contrato`, con su número (`E1`, `E2`…).
3. Recién ahí despacha a los agentes generativos.

El Cronista cuenta después cuántas dudas aparecieron igual durante el proceso: es la
medida de qué tan buena fue la escritura.

## Contrato de salida

```
ARTEFACTO: escritura.md
PUNTOS: <n> (abiertos en la spec <a> · contradicciones <c> · huecos de contrato <h>)
PRECEDENTES: <n>
ESTADO: completo | spec-cerrada (no hay nada que preguntar)
```

## Errores comunes

- **Preguntar lo que ya está decidido** → primero el registro de decisiones y la memoria.
- **Recorrer la lista de huecos entera sin filtrar** → solo lo que aplica al ticket; una
  escritura de cuarenta preguntas no la contesta nadie.
- **Preguntar detalles de implementación** → eso no es contrato.
- **Tomar la propuesta por defecto como decisión** → hasta que el usuario responde, está
  abierta.
- **Despachar a los agentes antes de que el usuario responda** → la spec tiene que quedar
  escriturada primero.
