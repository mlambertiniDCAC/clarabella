---
name: testear-ticket
description: Usar cuando hay que EJECUTAR el testeo ya documentado de un ticket del workspace dcac-ia-context — existe el plan de test (docs/{proyecto}/{tipo}/T<ticket>-<slug>/tests.md) y una implementación en la branch del ticket, y hay que correr los casos contra la DB de pruebas y verificar el comportamiento. Es la Fase 5 del motor pipeline-desarrollo (separada de implementar). Triggers — "corré los tests documentados de T#####", "ejecutá el testeo de T#####", "probá la implementación de T#####". NO documenta tests (eso es planear-tests-ticket) ni escribe código (eso es implementar-ticket).
---

# Ejecutar tests

Toma el **plan de test documentado** (Fase 3) y una **implementación ya aplicada** (Fase 4)
y **ejecuta el testeo de comportamiento**: corre los casos, verifica contra la DB de
pruebas, y **clasifica cada fallo** para que el motor sepa qué hacer. Es la contraparte
ejecutora de `planear-tests-ticket` (que solo documenta).

Ordena el trabajo en 3 fases: **preparar entorno → ejecutar → clasificar resultados**.

## Datos requeridos

| Dato | De dónde | Si falta |
|------|----------|----------|
| Plan de test | `docs/{proyecto}/{tipo}/T<ticket>-<slug>/tests.md` | Pedilo / avisá |
| Implementación | Branch `T#####` de los repos tocados | Si no está implementado, avisá (esto va después de Fase 4) |
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
Corré, en el orden del plan:
- **Tests unitarios** dentro del contenedor (según `dcac-context/back/testing.md`).
- **Curls E2E** documentados: ms directo (headers internos) + por gateway (`/v1/...`, auth real).
- Por cada caso, la **verificación contra la DB** (la query que el plan definió).
- Mapeá cada resultado al **escenario Gherkin** correspondiente (Given/When/Then): quedó
  verde o rojo, con evidencia (respuesta + query).

### Fase 3 — Clasificar resultados
Por cada caso: `PASA` o `FALLA`. Para cada `FALLA`, **clasificá la causa** (esto le dice al
motor a dónde volver):

| Clasificación | Qué significa | A dónde vuelve |
|---------------|---------------|----------------|
| `bug-implementacion` | El código no hace lo que el plan esperaba | Fase 4 (implementar-ticket) a corregir |
| `ambiguedad-negocio` | El comportamiento esperado no está claro / el plan y la realidad discrepan por una regla no definida | **DUDA** (hard stop, decide el usuario) |
| `test-mal-documentado` | El caso/curl/query del plan está mal | Fase 3 (planear-tests-ticket) a corregir |

### Teardown — dejar la DB como estaba
`cd microservicios/db-test && docker compose down -v && docker compose up -d`. Revertí los
`.env` a :3306. La DB de desarrollo nunca se tocó.

## Salida (modo orquestado)

```
ARTEFACTO: reporte de ejecución — [caso: PASA/FALLA + clasificación + evidencia]
RESULTADO: <N pasan / M fallan>
FALLAS:
  - [caso X] <clasificación> · <evidencia> · <qué habría que corregir>
DUDAS:
  - [D1] <solo las fallas ambiguedad-negocio> · por qué no se puede asumir
SUGERENCIAS:
  - [S1] <mejora de cobertura / robustez>
ESTADO: completo | frenado-por-duda
```

- `ESTADO: completo` **solo si todos los casos pasan.** Si hay fallas, `ESTADO` refleja
  si son resolubles por el motor (loop a Fase 4/3) o si hay una `ambiguedad-negocio`
  (`frenado-por-duda`).
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
- **No clasificar la falla** → el motor necesita saber si vuelve a Fase 4, a Fase 3, o frena.
- **Reportar sin evidencia** → cada resultado lleva respuesta + query.
