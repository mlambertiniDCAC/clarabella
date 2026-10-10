---
name: testear-ticket
description: Usar cuando hay que EJECUTAR el testeo ya documentado de un ticket del workspace dcac-ia-context — existe el plan de test (docs/{proyecto}/{tipo}/T<ticket>-<slug>/tests.md) y hay que correr los casos contra la DB de pruebas, en RED (antes de implementar, para confirmar que los tests discriminan) o en GREEN (después de implementar, para verificar la solución). Es la Fase 5 del motor pipeline-desarrollo y los pasos 3.1 (RED) y 3.3 (GREEN) de resolver-ticket, y corre en un subagente que no escribió el código. Triggers — "corré los tests documentados de T#####", "ejecutá el testeo de T#####", "probá la implementación de T#####". NO documenta tests (eso es planear-tests-ticket) ni escribe código (eso es implementar-ticket).
---

# Ejecutar tests

Toma el **plan de test documentado** y **ejecuta el testeo de comportamiento**: corre los
casos, verifica contra la DB de pruebas, y **clasifica cada resultado** para que quien la
despachó sepa qué hacer. Es la contraparte ejecutora de `planear-tests-ticket` (que solo
documenta).

Ordena el trabajo en 3 fases: **preparar entorno → ejecutar → clasificar resultados**.

## Dos modos: RED y GREEN

Los tests salen de la spec, por separado del plan. Esta skill es donde se encuentran con
el código, dos veces. El prompt que te invoca dice cuál; si no lo dice, es GREEN.

| Modo | Cuándo | Qué se espera | Qué detecta |
|------|--------|---------------|-------------|
| **RED** | Antes de implementar, con el entorno del ticket arriba y el código en master | Cada caso da lo que dice su columna "Esperado en RED": `falla` los de comportamiento nuevo, `pasa` los de regresión | Tests que no discriminan (pasan sin implementación) y regresiones que ya estaban rotas |
| **GREEN** | Después de implementar | Todos los casos pasan | Bugs de implementación y criterios que el plan no cubrió |

En RED no hay tests unitarios del ticket (los escribe la implementación) ni migración del
ticket (todavía no existe): corré solo los casos de `tests.md`. Que un caso nuevo falle
porque la ruta o la columna no existen **es** el RED esperado.

## Quién la ejecuta

- En `resolver-ticket` (manual) la corre la **sesión principal**, a la vista del usuario:
  él es el contexto independiente que mira los resultados.
- En el motor `pipeline-desarrollo`, un **subagente nuevo** por corrida, con un prompt que
  dice "modo orquestado".
- En `resolver-proyecto` no se usa: los casos son scripts (`correr_casos.py`).

En cualquier caso: tus fuentes son `tests.md`, el código en los worktrees, los contenedores
y la DB. **No modificás código ni `tests.md`.** Ejecutás, verificás y clasificás.

## Datos requeridos

| Dato | De dónde | Si falta |
|------|----------|----------|
| Plan de test | `docs/{proyecto}/{tipo}/T<ticket>-<slug>/tests.md` | Pedilo / avisá |
| Implementación (solo GREEN) | Branch `T#####` de los repos tocados | Si no está implementado, avisá |
| Plan de desarrollo (solo GREEN, solo para clasificar) | `plan.md` de la carpeta del ticket | Sirve para distinguir un bug de un criterio que el plan no cubrió; no lo uses para cambiar qué se espera |
| Acceso a la DB de pruebas | `db-test`, :3307 | Confirmá contenedor/credenciales; si no los tenés, pedíselos al usuario |

## Entorno aislado por ticket (cuando corre en el motor)

En el motor, el testeo corre **contra el contenedor del ticket** (`T#####-<ms>`) y su **DB
propia** (`T#####-db`), no contra la DB compartida (ver `entorno-ticket`). Implicancias:
- **Tests directos al ms** → 100% aislados: corren contra `T#####-<ms>` + `T#####-db`. Se
  pueden ejecutar **en paralelo** con los de otros tickets.
- **E2E por gateway** → el gateway compartido solo puede apuntar a un `T#####-<ms>` por vez:
  **serializar** el E2E-por-gateway del servicio modificado (o diferirlo si otro ticket lo
  está usando). No es un aislamiento total del grafo (regla acordada: solo se aíslan los
  servicios que el ticket toca).
- La migración del ticket se aplica contra `T#####-db` (no la compartida).
- Teardown = borrar la lane del ticket (`docker rm -f T#####-*`), no `down -v` de la DB
  compartida. El clon canónico nunca se tocó.

En modo standalone (sin motor), aplica la regla clásica de la DB de pruebas de abajo.

## Regla dura: DB de pruebas, no la de desarrollo

- Se ejecuta contra la **DB de pruebas dedicada** (`db-test`, :3307), **NUNCA** la de
  desarrollo (:3306). Para apuntar un servicio: en su `.env` cambiar solo `DB_PORT=3306`
  → `3307` (host igual), reiniciar el contenedor (obligatorio en Hyperf/Swoole), y
  **revertir a 3306 al terminar**.
- **TODO corre en Docker.** Tests unitarios y curls, dentro de los contenedores.
- El éxito **no** se confirma solo con el código HTTP: **siempre** hay verificación contra
  la DB (POST→fila insertada, GET→output vs DB, PUT→campos actualizados, DELETE→baja
  física/lógica), según lo documentó el plan de test.

## Workflow

### Fase 1 — Preparar entorno
Levantá la DB de pruebas (`cd microservicios/db-test && docker compose up -d`), aplicá las
migraciones si el ticket trae una (`nasgrate up` contra la DB de pruebas), apuntá los `.env`
de los servicios del flujo a :3307 y reiniciá los contenedores. Cargá las precondiciones de
datos que pide el plan ("Preparación de datos de prueba").

### Fase 2 — Ejecutar
Tres tandas, en este orden:

1. **Tests unitarios de todos los repos tocados, en paralelo.** Cada repo tiene su
   contenedor `T#####-<ms>`: lanzá cada suite en background (`run_in_background`) y juntá
   los resultados. No dependen entre sí ni de la DB del ticket.
2. **Curls directos a cada ms**, en paralelo **entre repos** y en el orden del plan
   **dentro de cada repo** (los casos de un mismo servicio suelen compartir datos
   preparados). Por cada caso, la **verificación contra la DB** (la query que documentó
   el plan de test).
3. **E2E por gateway** (`/v1/...`, auth real), **en serie y al final.** El gateway
   compartido apunta a un `T#####-<ms>` por vez; si otro ticket lo está usando, esperá o
   diferí esta tanda y reportalo.

Mapeá cada resultado al **escenario Gherkin** correspondiente (Given/When/Then): quedó
verde o rojo, con evidencia (respuesta + query).

Si los datos preparados de dos repos viven en la misma `T#####-db` y se pisan (mismas
filas, mismos IDs), corré esa tanda 2 en serie. Ante la duda, en serie.

### Fase 3 — Clasificar resultados
Por cada caso: `PASA` o `FALLA`, comparado contra lo esperado **en el modo que corre**.

**En RED**, lo que hay que reportar es cada caso que no dio su esperado en RED:

| Clasificación | Qué significa | Quién decide |
|---------------|---------------|--------------|
| `test-no-discrimina` | Un caso de comportamiento nuevo pasa sin implementación: o el test no ejercita lo que dice, o el comportamiento ya existía | El usuario: se corrige el test o se revisa si el ticket ya estaba resuelto |
| `regresion-preexistente` | Un caso de regresión falla en master, antes de tocar nada | El usuario: no es culpa del ticket, pero hay que saberlo antes de implementar |
| `test-mal-documentado` | El caso no se puede ni ejecutar (curl mal formado, query inválida, precondición imposible) | El usuario aprueba la corrección del test |

**En GREEN**, para cada `FALLA`, **clasificá la causa**:

| Clasificación | Qué significa | A dónde vuelve |
|---------------|---------------|----------------|
| `bug-implementacion` | El plan cubre el caso pero el código no hace lo que tendría que hacer | Implementación, a corregir |
| `hueco-del-plan` | El caso sale de un criterio de la spec que el plan no contempla | El usuario decide si se amplía el plan o el criterio queda fuera |
| `ambiguedad-negocio` | El comportamiento esperado no está claro, o la spec y la realidad discrepan por una regla no definida | **DUDA** (hard stop, decide el usuario) |
| `test-mal-documentado` | El caso/curl/query está mal | El usuario aprueba la corrección del test |

Un test que salió de la spec no se ajusta para que pase con lo implementado: si el código
y el test discrepan, el test manda hasta que el usuario diga lo contrario.

### Teardown — dejar la DB como estaba
`cd microservicios/db-test && docker compose down -v && docker compose up -d`. Revertí los
`.env` a :3306. La DB de desarrollo nunca se tocó.

## Salida (modo orquestado)

```
ARTEFACTO: reporte de ejecución — [caso: PASA/FALLA + clasificación + evidencia]
MODO: RED | GREEN
RESULTADO: <N pasan / M fallan> (en RED: <K dieron su esperado / J no>)
FALLAS:
  - [caso X] <clasificación> · <evidencia> · <qué habría que corregir>
DUDAS:
  - [D1] <solo las fallas ambiguedad-negocio> · por qué no se puede asumir
SUGERENCIAS:
  - [S1] <mejora de cobertura / robustez>
ESTADO: completo | frenado-por-duda
```

- En GREEN, `ESTADO: completo` **solo si todos los casos pasan.** En RED, `completo` si
  todos los casos dieron su esperado en RED. Si no, `ESTADO` refleja si se resuelve
  corrigiendo código o si hay algo que decide el usuario (`frenado-por-duda`).
- **No arregles el código vos.** Tu trabajo es ejecutar, verificar y clasificar. La
  corrección la hace la fase que corresponda.

**Latido de actividad (feed en vivo):** appendeá una línea al
`docs/{proyecto}/{tipo}/T#####-{slug}/.pipeline/actividad.jsonl` (solo en el motor) al arrancar cada caso y al clasificar una
falla, así el usuario ve el avance del testeo en el dashboard:
```bash
echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"fase\":\"5\",\"actor\":\"subagente\",\"tipo\":\"test\",\"texto\":\"caso <X>: PASA/FALLA\",\"meta\":{}}" >> docs/{proyecto}/{tipo}/T#####-{slug}/.pipeline/actividad.jsonl
```

## Errores comunes

- **Correr contra la DB de desarrollo (:3306)** → siempre `db-test` (:3307), y revertir.
- **Dar "verde" solo por el código HTTP** → sin la query a la DB no está verificado.
- **Arreglar el código para que pase** → no; eso es implementar-ticket. Vos clasificás.
- **No dejar teardown** → recreá la DB de pruebas y revertí los `.env`.
- **No clasificar la falla** → quien te despachó necesita saber si se corrige código, si
  decide el usuario, o si se frena.
- **Dar por bueno un RED donde un caso nuevo pasa** → es `test-no-discrimina`, no un éxito.
- **Leer `plan.md` en RED, o usarlo en GREEN para cambiar qué se espera** → en GREEN solo
  sirve para distinguir `bug-implementacion` de `hueco-del-plan`.
- **Reportar sin evidencia** → cada resultado lleva respuesta + query.
- **Correr el testeo en el mismo hilo que implementó** → va en un subagente nuevo; ver
  "Quién la ejecuta".
- **Correr el E2E por gateway en paralelo** → el gateway compartido apunta a un solo
  `T#####-<ms>` por vez; esa tanda va en serie y al final.
