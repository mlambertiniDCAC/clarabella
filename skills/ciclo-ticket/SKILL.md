---
name: ciclo-ticket
description: Usar cuando el usuario quiere que el desarrollo de un ticket del workspace dcac-ia-context se repita solo hasta dar con la implementación correcta — el Escribano cierra la spec con el usuario antes de arrancar, y después el ciclo prepara, revisa, implementa, testea y vuelve a empezar desde donde falló, y cada agente corrige solo lo que se marcó; las dudas que aparecen en el camino se resuelven como decisiones provisorias en vez de frenar, y el usuario las confirma al final, hasta cumplir la definición de terminado, estancarse o agotar el presupuesto. Triggers — "corré T##### en ciclo", "que se repita hasta que ande", "modo ciclo para T#####", "iterá T##### hasta la implementación correcta". NO envía a review ni commitea.
---

# El ciclo

En el flujo manual de `resolver-ticket`, cada falla vuelve al usuario. En el ciclo, una
falla vuelve **a quien la causó**, y el desarrollo se repite solo hasta que la
implementación es correcta.

**El usuario interviene solo al final:** confirma o veta las decisiones provisorias y
valida el resultado. No se le pregunta nada en el medio, ni para aprobar plan y tests, ni
para decisiones de nombre o de desarrollo, ni para informarle avances o costos.

En el medio, el ciclo solo se detiene por algo que no puede resolver solo (ver "Cuándo
pausa").

## Etapa 0 — Presupuesto y escritura

**Presupuesto.** Usá los defaults (o lo que el usuario haya dicho al pedir el ticket) y
anotalo arriba de `registro.md`:

| Límite | Default sugerido | Cuenta |
|--------|------------------|--------|
| Vueltas de implementación | 8 | Cada GREEN cuenta una vuelta |
| Tokens | Lo fija el usuario | Suma de los tokens de `registro.md` |
| Tiempo | Lo fija el usuario | Desde el primer subagente |

**Escritura.** Despachá al `escribano` sobre `spec.md`. **No se la presentes al usuario:**
cada punto se toma con su propuesta por defecto, como provisoria (`P#` en
`revision/provisorias.md`), y queda en `spec.md` § Decisiones de contrato marcada como
provisoria. Los precedentes se aplican tal cual. Al final el usuario confirma o veta todo
junto.

## La definición de terminado

El ciclo termina bien cuando se cumplen **todas** a la vez:

1. El RED dio lo esperado sobre la versión vigente de `tests.md`.
2. El GREEN pasa completo, con un subagente nuevo, sobre el código actual.
3. `reglas.py` sin alertas abiertas (confirmadas y sin corregir) y la última revisión de la
   implementación sin bloqueantes.
4. No hay dudas abiertas: cada una está respondida, decidida como menor o tomada como
   provisoria.

Las provisorias no impiden terminar, pero el resultado es **terminado provisorio** hasta
que el usuario las confirma (ver "El final"). Que el código compile o que el implementador
diga que está listo no cuenta.

## Las etapas

### Etapa 1 — Preparación
Fase 1 de `resolver-ticket`: repos, entorno en background, agentes generativos de plan y de
tests, Baqueanos para sus dudas. En el ciclo, el Baqueano puede clasificar `DECISIÓN MENOR`
y `PROVISORIA` (ver `baqueano`): las dudas no frenan.

### Etapa 2 — Revisión del plan y los tests
Fase 2 de `resolver-ticket` (`revisar-ticket`, modo plan-tests), con un cambio: **"sin
bloqueantes" reemplaza la aprobación del usuario.** Los DESACUERDOS de los correctores
pasan por el Baqueano, que los resuelve como menor o como provisoria.

### Etapa 3 — RED
Como en `resolver-ticket` 3.1. Si no da lo esperado, un sonnet nuevo corrige los casos
(`test-no-discrimina`, `test-mal-documentado`), corre `trazabilidad.py` y se repite el RED
de esos casos. Una
`regresion-preexistente` pausa: el ciclo no puede arreglarla.

### Etapa 4 — Las vueltas de implementación
Cada vuelta:

1. **Implementar.** Los implementadores son agentes generativos (ver "La vida del
   implementador"), uno por repo si el ticket toca varios, en paralelo.
2. **GREEN** con un subagente nuevo. El reporte va a `revision/testeo/green-<n>.md`.
3. **Revisión de la implementación**, si el GREEN pasó completo: `revisar-ticket` modo
   implementación. La primera vez sobre el diff completo; después, solo el delta desde la
   última revisión (`revision/ultima-revision-<ms>.txt`).
4. **Evaluar** la definición de terminado. Si no se cumple, cada falla vuelve a quien
   corresponde:

| Falla | Vuelve a | Qué pasa |
|-------|----------|----------|
| `bug-implementacion` | El implementador de ese repo | Corrige; la próxima vuelta lo prueba |
| Hallazgo bloqueante o alerta confirmada | El implementador | Corrige solo lo marcado; GREEN y `reglas.py` en la próxima vuelta |
| `hueco-del-plan` | Un sonnet nuevo | Agrega la Parte que falta con su `Cubre:`; `trazabilidad.py`; después se implementa |
| `test-mal-documentado` | Un sonnet nuevo | Corrige el caso; `trazabilidad.py`; se repite el RED de ese caso |
| `ambiguedad-negocio` | El Baqueano | La resuelve como menor o como provisoria |

5. **Registrar la vuelta** en `registro.md` (ver "Estancamiento").

## Las decisiones provisorias

Cuando aparece una decisión mayor que la escritura no anticipó, el ciclo no frena:

1. El Baqueano la clasifica `PROVISORIA`: elige la opción más conservadora (la que cambia
   menos, la más fácil de revertir, o la que respalda la práctica previa) y arma el caso
   igual que para el usuario.
2. El orquestador la registra en `revision/provisorias.md` con un número (`P1`, `P2`…) y
   anota qué partes dependen de ella: el agente que la usa la cita en su artefacto (o en
   `revision/notas-<ms>.md`, si es el implementador).
3. El ciclo sigue sobre ese supuesto.

**Nunca son provisorias, siempre pausan:** el módulo financiero (DCP / `ms-decampopagos`),
permisos y seguridad, y migraciones o cambios sobre datos existentes. Ahí un supuesto
equivocado sale caro.

## El implementador

En el ciclo, el implementador anota sus desvíos del plan en `revision/notas-<ms>.md`, como
en el flujo manual. **No se reemplaza:** se lo retoma con `SendMessage`, con su contexto, y corrige lo que falló.

| Señal | Cuándo | Qué pasa |
|-------|--------|----------|
| `sin-progreso` | Dos vueltas seguidas en las que los casos `bug-implementacion` de su repo no bajaron | Antes de la próxima vuelta, el orquestador le pide un diagnóstico: por qué no avanza y qué va a cambiar de enfoque. Si el enfoque entero estaba mal, guarda el trabajo con `git -C .worktrees/T#####-{slug}/<ms> stash push -u -m "T##### impl <ms>"` (se puede recuperar) y el mismo implementador reescribe desde master |

`sin-progreso` lo cuenta el Cronista. Si un implementador ya no está disponible, se
despacha uno nuevo con el código actual, sus notas y el último reporte
de GREEN, para que siga desde ahí.

## Cuándo pausa

| Causa | Qué le muestra al usuario |
|-------|---------------------------|
| **Decisión mayor en terreno sensible** (financiero, permisos/seguridad, datos) | El caso armado por el Baqueano. Con la respuesta, el ciclo sigue |
| **Corrección fallida dos veces** | El hallazgo, los dos intentos y por qué no alcanzaron: el problema suele estar en la spec o en la doc |
| **Regresión preexistente** | El caso que falla en master |
| **Entorno caído** | Qué contenedor o servicio, sin tocar infra compartida |
| **Estancamiento** | La firma que se repite y las últimas vueltas |
| **Presupuesto agotado** | Lo gastado, en qué vuelta estaba y qué fallaba |

Las dos últimas terminan el ciclo.

## Estancamiento

Al cerrar cada vuelta, anotá en `registro.md` su **firma**: los casos que fallan con su
clasificación, más los hallazgos bloqueantes.

```markdown
## Vuelta 4
- Firma: C9 bug-implementacion · C12 bug-implementacion · H2 bloqueante
- sin-progreso: implementador apigateway-psp
- Provisorias nuevas: P2
- Tokens de la vuelta: <n>
```

**Hay estancamiento cuando la misma firma se repite tres vueltas seguidas.** Que los
agentes corrijan algo no cuenta como progreso si la firma no cambia.

## El final

1. **Despachá al `cronista`.** La crónica cuenta todas las vueltas (firma, sin-progreso, costo,
   qué destrabó cada avance), cuántas dudas aparecieron pese a la escritura, y todas las
   provisorias.
2. **Provisorias.** Presentale al usuario `revision/provisorias.md` completo, cada una con su
   caso y lo que depende de ella.
   - **Confirmadas:** pasan a ser decisiones del usuario (van a `spec.md` y, vía crónica,
     al registro de decisiones).
   - **Vetadas:** la decisión del usuario va a `spec.md`, y el ciclo **se reanuda** desde el
     punto más temprano afectado (plan, tests o implementación), con el presupuesto que
     quede.
3. **Sin provisorias vetadas:** el ciclo para y espera. El usuario valida el diff
   (`mostrar-diff`) y la crónica, y aprueba el envío con `enviar-review` como siempre.

Si terminó por estancamiento o presupuesto, también va el `cronista`, con estado
"frenado" y el diagnóstico de dónde se trabó.

El ciclo nunca commitea ni envía a review.

## Errores comunes

- **Arrancar los agentes sin la escritura** → las dudas que se podían anticipar aparecen en
  el medio. La escritura se toma con sus defaults como provisorias, sin preguntar.
- **Preguntarle al usuario en el medio** (aprobar plan y tests, nombres, decisiones de
  desarrollo, avances, costos) → el objetivo es que el ticket se resuelva sin intervención.
- **Pausar por una decisión mayor común** → es provisoria; solo pausan las de terreno
  sensible.
- **Tomar como provisoria algo financiero, de permisos o de datos** → siempre pausa.
- **Usar una provisoria sin registrar qué depende de ella** → si el usuario la veta, no se
  sabe desde dónde rehacer.
- **Declarar terminado sin un GREEN de un subagente nuevo sobre el código final** → la
  definición de terminado lo exige.
- **Rehacer de cero lo que ya estaba bien** → cada agente corrige solo lo que falló.
- **Contar como progreso que un agente corrigió algo** → el progreso es que cambie la firma.
- **Seguir después de tres vueltas con la misma firma** → es estancamiento; para.
- **Borrar el trabajo de un implementador** → si hay que reescribir, se guarda antes con
  `git stash push -u`.
- **Resetear el presupuesto en medio del ciclo sin preguntar** → lo fija el usuario.
- **Enviar a review al terminar** → el ciclo para y espera al usuario.
