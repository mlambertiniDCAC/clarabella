---
name: resumir-ticket
description: Usar cuando un ticket del workspace dcac-ia-context ya fue planeado, implementado y testeado y hay que entregar un RESUMEN del desarrollo — consolida plan, tests y resultados de la ejecución del testeo (todos en `docs/{proyecto}/{tipo}/T#####-{slug}/`) en un solo documento. Triggers — "resumí el desarrollo de T#####", "armá el resumen de T#####", "cerrá T#####". Es la Fase 6 (última) del motor pipeline-desarrollo.
---

# Resumen de desarrollo

Consolida los artefactos de un ticket (**plan + tests + resultados de la ejecución del
testeo**) en un **resumen del desarrollo**: qué se pedía, qué se hizo, cómo se verificó, qué
quedó fuera y qué dudas/sugerencias surgieron. Es un documento de cierre, legible por el usuario
y por quien tome el ticket después.

Es la Fase 6 (última) del motor `pipeline-desarrollo`, pero también sirve standalone.

## Datos requeridos

| Dato | De dónde | Si falta |
|------|----------|----------|
| Plan de desarrollo | `docs/{proyecto}/{tipo}/T<ticket>-<slug>/plan.md` | Pedilo |
| Plan de test | `docs/{proyecto}/{tipo}/T<ticket>-<slug>/tests.md` | Avisá si no está |
| Reporte de implementación | Salida de la Fase 4 (`implementar-ticket`) | Pedilo |
| Resultados del testeo | Salida de la Fase 5 (`testear-ticket`): casos que pasan/fallan | Pedilo |
| Log de dudas (si el motor lo llevó) | `docs/{proyecto}/{tipo}/T<ticket>-<slug>/.pipeline/dudas.md` | Opcional |

**No inventes resultados.** El resumen refleja lo que realmente pasó: si un test falló o
una fase quedó frenada por una duda, el resumen lo dice tal cual.

## Convención de guardado

```
docs/{proyecto}/{tipo}/T<ticket>-<slug>/resumen.md
```
- Mismo `{tipo}` y `<slug>` que el plan de desarrollo (en el motor salen de `estado.json`; en el flujo manual, del paso 0 de `resolver-ticket`). Crear `T<ticket>-<slug>/` si no existe.

## Workflow

### Fase 1 — Recolectar
Leé el plan, el plan de test y el reporte de implementación. Extraé: objetivo del ticket,
repos/archivos tocados, endpoints/reglas, resultado de cada caso de test, dudas resueltas
y sugerencias pendientes.

### Fase 2 — Escribir el resumen
Estructura del documento:

```markdown
# Resumen de desarrollo — <Título> (T#####)

> **Ticket:** T#####
> **Estado:** entregado | entregado-con-observaciones | frenado

## Qué se pedía
El objetivo del ticket en 2-3 líneas.

## Qué se hizo
Por repo: archivos tocados y el cambio en una línea cada uno. Endpoints nuevos/modificados.

## Cómo se verificó
Resultado de los tests (tabla de casos: pasó/falló) + verificación contra DB. Link al
plan de test.

## Dudas y decisiones
Dudas que surgieron y cómo se resolvieron (con quién / qué se decidió). Sugerencias
aplicadas vs. diferidas.

## Fuera de alcance / pendientes
Qué quedó explícitamente afuera y qué habría que hacer después.

## Referencias
- Plan de desarrollo: <path>
- Plan de test: <path>
```

## Salida (modo orquestado)

Cuando la invoca el motor, devolvé al final:

```
ARTEFACTO: <path del resumen guardado>
ESTADO: completo
```

Esta fase normalmente no genera DUDAS (solo consolida); si detecta una inconsistencia
entre lo planeado y lo implementado, la marca como SUGERENCIA de revisión.

## Errores comunes

- **Inflar el resumen con lo que "debería" haber pasado** → reflejá lo real, incluidos fallos.
- **Omitir las sugerencias diferidas** → son deuda; tienen que quedar registradas.
- **Duplicar el plan entero** → el resumen linkea al plan, no lo copia.
