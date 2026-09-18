---
name: implementar-ticket
description: Usar cuando el usuario (o el motor pipeline-desarrollo) quiere IMPLEMENTAR un ticket ya planeado sobre el workspace dcac-ia-context — existe un plan de desarrollo (docs/{proyecto}/{tipo}/T<ticket>-<slug>/plan.md) y hay que escribir el código en la branch del ticket. Triggers — "implementá T#####", "dale, codeá el plan de T#####", "arrancá con la Parte 1 de T#####". Es la Fase 4 del motor. NO ejecuta el testeo documentado (eso es la Fase 5, testear-ticket).
---

# Implementar desarrollo

Toma un **plan de desarrollo aprobado** y produce el **código real** en la branch del
ticket. Ordena el trabajo en 3 fases: **releer → implementar → cerrar**.

**Esta skill NO ejecuta el testeo documentado.** Eso es una fase aparte
(`testear-ticket`, Fase 5 del motor). Acá se escribe el código —incluidos los archivos de
test unitario que el plan pida— y se deja el repo listo para que la fase de testeo lo pruebe.

Es la Fase 4 del motor `pipeline-desarrollo`, pero también sirve standalone cuando el usuario
dice explícitamente "implementá T#####". La implementación es una decisión explícita del
usuario (o del motor tras pasar el doubt-gate): **no arranques a codear sin ese disparo**.

## Datos requeridos

Si falta alguno, **preguntá antes de avanzar** (no inventes):

| Dato | Para qué | Si falta |
|------|----------|----------|
| Plan de desarrollo | Qué código escribir | Buscá `docs/{proyecto}/{tipo}/T<ticket>-<slug>/plan.md`; si no está, pedilo |
| Ticket `T#####` + proyecto | Ubicar el doc y la branch | Preguntá |
| Plan de test (opcional) | Contexto de qué se va a probar después | Buscá `tests.md` en la misma carpeta del plan; útil, no bloqueante |

## Reglas duras del workspace (no negociables)

- **TODO corre en Docker.** App, tests y DB se ejecutan DENTRO de los contenedores, nunca
  en el host (ver `dcac-context/back/docker.md`).
- **Cada microservicio SOLO accede a sus propias tablas.** Nada de queries cross-servicio
  directas; los datos de otro dominio se piden vía API Gateway (Composition).
- **Los microservicios NO se comunican entre sí** — solo por API Gateway.
- **PROHIBIDO estado en variables de clase** en apigateway y ms Hyperf (Swoole persistente).
  Usar variables locales / parámetros / estáticos puros (`dcac-context/back/conventions.md`).
- **NO commits, NO push.** El usuario maneja git. Vos dejás los archivos modificados
  en el working tree de la branch `T#####`.
- **Sin comentarios en el código** salvo que el patrón del archivo ya los use.

## Workflow

### Fase 1 — Releer
Leé el plan de desarrollo completo. Para cada archivo listado, abrí con Read el **estado
actual real** y confirmá que coincide con el "Estado actual" del plan. Si el código cambió
respecto de lo que el plan asumía → es una **DUDA** (el plan quedó desactualizado, no
improvises).

### Fase 2 — Implementar
**En el motor, las escrituras van al contenedor aislado del ticket** (`T#####-<ms>`, ver
`entorno-ticket`), NO al clon canónico (que es solo lectura/fuente). Confirmá que el
contenedor existe y está en branch `T#####`; si no, provisionalo con `entorno-ticket`. El
trabajo aterriza en esa branch dentro del contenedor; **no se commitea acá** (el commit +
sync-out al canónico lo hace `enviar-cambios`, Fase 7).

Aplicá los cambios del plan **archivo por archivo, en el orden de las Partes**. Seguí el
snippet "Cambio" del plan. Espejá los patrones del código vecino (naming, estructura,
manejo de errores). Si al implementar aparece algo que el plan no previó y que requiere una
decisión de negocio/producto → **pará y reportalo como DUDA**, no lo resuelvas asumiendo.
Si ves una mejora de buenas prácticas fuera del plan → **SUGERENCIA**, no la apliques sola.

### Fase 3 — Cerrar (handoff a la fase de testeo)
No ejecutás el testeo documentado (eso es `testear-ticket`, Fase 5). Acá:
- Confirmá que **todos los cambios del plan quedaron aplicados** (todas las Partes).
- Sanity check mínimo: que el contenedor **levanta** y el código no rompe sintácticamente
  (arranque del servicio en Docker). Sin correr los casos del plan de test.
- Dejá el trabajo en la branch `T#####` (sin commitear) listo para que la Fase 5 lo pruebe.

Si en la Fase 5 un test vuelve clasificado como `bug-implementacion`, el motor te
re-despacha con el diagnóstico para corregir ese punto puntual, y se re-ejecuta el testeo.

## Salida

Producí un reporte de implementación con: qué archivos se tocaron (ruta + resumen del
cambio), en qué branch quedaron, y el resultado del sanity check de arranque.

## Skills especiales por tipo de cambio

Si el plan incluye un cambio que tiene skill propia, seguí sus reglas al implementarlo:

| Tipo de cambio | Skill | Qué hacés |
|----------------|-------|-----------|
| Migración de DB (nasgrate) | `crear-migracion` | Creás el archivo en `microservicios/nasgrate/data/migrations/` con el formato exacto (nombre `YYYYMMDDHHMMSS_...`, solo `-- UP --`, solo `PRIMARY KEY`, tablas prefijadas con el esquema del ticket, autor = `git config user.name`, nunca "claude"). **Aplicar la migración** (`nasgrate up`) contra la DB de pruebas lo hace la Fase 5 (`testear-ticket`) al preparar el entorno. **Si el repo `nasgrate` no existe → frená y avisá.** |

## Modo orquestado (invocada por el motor `pipeline-desarrollo`)

Cuando la invoca el motor como Fase 4 (el prompt lo dice explícitamente), además de lo de
arriba, terminá devolviendo **este contrato exacto**:

```
ARTEFACTO: <resumen de archivos modificados + branch T##### + sanity de arranque>
DUDAS:
  - [D1] <qué requiere decisión del usuario> · <dónde surgió> · <por qué no se puede asumir>
SUGERENCIAS:
  - [S1] <mejora> · <beneficio> · <costo/riesgo>
ESTADO: completo | frenado-por-duda
```

- `ESTADO: frenado-por-duda` si el plan quedó desactualizado o aparece una decisión de
  negocio no resuelta. **No fuerces** la implementación: dejá lo hecho y reportá.
- `ESTADO: completo` si **todo el código del plan quedó aplicado** y el servicio arranca.
  La verificación del comportamiento la hace la Fase 5 (`testear-ticket`), no vos.
- Listas vacías: `DUDAS: (ninguna)` / `SUGERENCIAS: (ninguna)`.

**Latido de actividad (feed en vivo):** appendeá una línea al
`docs/{proyecto}/{tipo}/T#####-{slug}/.pipeline/actividad.jsonl` (solo en el motor) cada vez que escribís un archivo o hacés un
paso relevante — la Fase 4 puede tardar minutos y sin latido el dashboard parece colgado:
```bash
echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"fase\":\"4\",\"actor\":\"subagente\",\"tipo\":\"escritura\",\"texto\":\"escribiendo <archivo>\",\"meta\":{}}" >> docs/{proyecto}/{tipo}/T#####-{slug}/.pipeline/actividad.jsonl
```

## Errores comunes

- **Codear sin releer el estado actual** → el plan pudo quedar viejo; confirmá contra el código.
- **Asumir una decisión de negocio que el plan no cerró** → eso es una DUDA, no una licencia.
- **Ejecutar el testeo documentado acá** → no; eso es la Fase 5 (`testear-ticket`). Acá solo
  codeás y hacés un sanity de arranque.
- **Commitear/pushear** → no; el usuario maneja git.
- **Escalar el scope** → implementá solo lo del plan; lo demás es SUGERENCIA o DUDA.
