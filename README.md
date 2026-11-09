# Clarabella

```
 ____________________________________________________
< Muu, soy Clarabella. ¿Qué ticket resolvemos hoy? >
 ----------------------------------------------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||
```

Plugin de Claude Code: Clarabella es una vaca a la que le mandás a resolver tickets
(desarrollo o soporte), paso a paso y con tu revisión en cada etapa.

## Hablarle a Clarabella

Pedile lo que necesites nombrándola, en lenguaje natural:

```
Clarabella, quiero que me ayudes con un ticket
Clarabella, fijate en la base de stage qué quedó en la tabla X
Clarabella, mostrame el diff
```

Ella deriva el pedido a la skill que corresponde. Un hook del plugin detecta su nombre en
cada mensaje, así que no depende de que Claude "adivine" la skill. Si preferís, podés
invocar cualquier skill directo (`/clarabella:resolver-ticket`).

## Dos modos

| Modo | Cómo | Para qué |
|------|------|----------|
| **Manual** | "Clarabella, ayudame con T#####" → `resolver-ticket` | Un ticket, vos con el control: 8 pasos en la sesión, sin subagentes |
| **Autónomo** | `claude --agent clarabella:coordinador` → `resolver-proyecto` | Uno o más tickets relacionados: generadores, alineación, juicio antes de implementar, Implementador con Obreros, casos como scripts |

El juicio de un proyecto corre en una sesión aparte: `claude --agent clarabella:juez`.

## Instalación

Desde Claude Code:

```
/plugin marketplace add mlambertiniDCAC/clarabella
/plugin install clarabella@clarabella
```

Actualizar: `/plugin marketplace update clarabella`.

Las skills quedan con prefijo del plugin (`/clarabella:resolver-ticket`). Se usan
corriendo Claude Code desde el root de `dcac-ia-context`: asumen su estructura
(`microservicios/`, `dcac-context/`, `docs/`, `.worktrees/`, `gestion/equipo/`).

## Requisitos

| | Linux / macOS | Windows |
|---|---|---|
| Instalar el plugin y hablarle a Clarabella | ✔ | ✔ (el hook necesita Git Bash, que viene con Git for Windows) |
| Flujo completo de tickets | ✔ | Recomendado dentro de **WSL2**: el flujo usa Docker, scripts bash, `python3`, `arc` y clientes `mariadb`/`psql` |

Herramientas que usan las skills: `git`, Docker (también para `trivy`, que no se instala
en el host), `python3` (para `mostrar-diff`), Arcanist
(`arc`) para enviar a review, y `mariadb` o `psql` para `leer-db` (en Postgres también puede
usar un contenedor efímero).

El repo es privado: para instalarlo necesitás acceso de lectura en GitHub y tu git
autenticado (SSH o `gh auth login`).

## Configuración por dev (una sola vez)

Nada de esto viaja en el plugin: cada dev lo configura con sus propios datos.

1. **Git**: `git config user.name` y `git config user.email` en los repos que vayas a
   tocar. Commits y migraciones se firman con eso, nunca con Claude.
2. **Arcanist**: `arc install-certificate` contra Phabricator con tu cuenta
   (queda en tu `~/.arcrc`). Sin eso `enviar-review` no puede crear el diff.
3. **Bases de datos (`leer-db`)**: las credenciales viven en el directorio de datos
   del plugin, `~/.claude/plugins/data/clarabella-clarabella/leer-db/credenciales/`,
   un `<entorno>.cnf` por base. No hace falta crearlos a mano: la primera vez que uses
   `leer-db` te pide los datos y arma el archivo (`chmod 600`). Las plantillas están
   en `skills/leer-db/plantillas/`. Usá un usuario de DB con permisos solo de
   `SELECT` si lo tenés.

## Skills

| Skill | Para qué |
|-------|----------|
| `clarabella` | Puerta de entrada: entiende el pedido y deriva a la skill que va |
| `resolver-ticket` | Los 8 pasos manuales (0.3.0): vos con el control, en la sesión, sin subagentes |
| `resolver-proyecto` | Uno o más tickets, solos: Coordinador, generadores, alineación, juicio antes de implementar, Implementador con Obreros, casos como scripts |
| `juzgar-proyecto` | El Juez, en sesión aparte: dictamina si la solución de un lote sirve, antes de implementarla |
| `preparar-repo` | Master actualizado + branch `T#####` aislada |
| `aislar-ticket` | Worktree (etapa A) + contenedor Docker y DB propios del ticket (etapa B, en background) |
| `planear-ticket` | Plan del ticket (`<carpeta del ticket en el cerebro>/plan.md`), con `Cubre: CA#` por Parte |
| `planear-tests-ticket` | Plan de tests E2E (`tests.md`) desde la spec, sin mirar el plan, con columna `Criterio` |
| `revisar-ticket` | Trazabilidad y reglas críticas por script, y un revisor sonnet de una pasada (plan y tests, o implementación); corrige un agente nuevo, nunca se retoma al autor |
| `escribano` | Revisa la spec antes de arrancar y le pide al usuario, en una sola ronda, todo lo que falta definir |
| `baqueano` | Responde las dudas de los agentes generativos desde las fuentes; lleva al usuario solo las decisiones |
| `implementar-ticket` | Implementación guiada del plan (también la usan los Obreros) |
| `testear-ticket` | Corre los casos documentados en RED o GREEN; en el flujo manual, en la sesión principal |
| `resumir-ticket` | Resumen de cierre del flujo manual |
| `mostrar-diff` | Diff estilo GitHub en un puerto local, en vivo |
| `cronista` | La crónica del ticket (para equipo, producto, el usuario y el próximo ticket), borradores de arc diff y comentario, y el registro de decisiones del proyecto |
| `enviar-review` | Commit + `arc diff --create`, solo con aprobación explícita |
| `bajar-entorno` | Apaga lo del ticket (contenedores, volúmenes, preview, datos de prueba) |
| `crear-migracion` | Reglas para migraciones nasgrate |
| `consultar-grafo` | Usa `graphify-out/` del repo si existe |
| `cargar-portfolio` | Clasifica un bloque crudo de novedades y lo archiva en el cerebro de contexto |
| `consultar-portfolio` | Trae del cerebro en qué quedó un proyecto, sus pendientes y sus relaciones |
| `leer-db` | Consultas de solo lectura a MariaDB/Postgres |
| `vacunar-repos` | Scan de vulnerabilidades de los repos Node (npm audit + trivy), fix seguro validado y diff por repo |

### Scripts (`scripts/`, Python stdlib)

| Script | Qué hace |
|--------|----------|
| `trazabilidad.py <ticket>` | Cruza los `CA#` de la spec con `Cubre:` del plan y la columna `Criterio` de los tests |
| `reglas.py --worktree … --ownership …` | Alertas de tabla ajena, llamada entre ms y estado en clase sobre el diff (incluye archivos nuevos); `--snapshot` para el delta |
| `hechos.py <ticket> --worktree …` | Datos duros para el Cronista (economía con el contexto retomado aparte, RED/GREEN, repos, hallazgos, decisiones) |
| `contratos.py <tickets>` | Cruza lo que cada ticket expone y consume, detecta consumos sin dueño y ciclos, y da el orden del lote; `--deriva` al cierre |
| `fichas.py <ticket>` | Ficha de un ticket para el juicio |
| `correr_casos.py <ticket> [--red]` | RED y GREEN sin tokens: corre `casos/<ms>/T##.sh` |
| `vacunas.py --worktree … --repo … --out …` | Scan de un repo Node en contenedores efímeros (npm audit + trivy fs/image/secret) normalizado a JSON chico; `--detectar` lista los repos Node, `--comandos` imprime el fix y la validación |

`vacunar-repos` despacha un **Veterinario** (sonnet · medio) por repo.

Tests: `python3 -m unittest discover -s tests -v`.

## Flujo de `resolver-ticket` (manual)

0. Fijar ticket, tipo, proyecto y `spec.md` (criterios numerados `CA#`)
1. `preparar-repo` → `aislar-ticket`
2. `planear-ticket`
3. `planear-tests-ticket` (desde la spec, sin mirar el plan)
4. Implementar (directo o `implementar-ticket`) con `mostrar-diff` en vivo
5. `testear-ticket` (GREEN, en la sesión)
6. `mostrar-diff`
7. `resumir-ticket`
8. `enviar-review`; después, `bajar-entorno`

## Flujo de `resolver-proyecto` (autónomo)

Se arranca con `claude --agent clarabella:coordinador` desde la raíz del workspace.

0. **Armar el lote:** tickets, specs, Escribano por ticket (una sola ronda de decisiones con vos)
1. y 2. **Generadores** de plan (con `## Contrato`) y de tests, por ticket, sin verse
3. **Alineación:** `trazabilidad.py`, `contratos.py` (orden del lote) y el Alineador
4. **Corrección:** Verificador (Chain-of-Verification) y Correctores nuevos; se verifica con scripts
5. **Juicio de valor** en sesión aparte (`claude --agent clarabella:juez`): sirve, se recorta o se frena
6. **Implementación**, en el orden del lote: QA escribe los casos como scripts, RED, el
   Implementador despacha un Obrero por microservicio y corre GREEN, y un Revisor por repo
7. **Cierre:** integración del lote, deriva de contratos, medición, crónica y envío en orden

## Roles de `resolver-proyecto`

| Rol | Modelo · esfuerzo | Qué hace |
|-----|-------------------|----------|
| Coordinador | Haiku · medio | Sesión principal: despacha, lleva `estado.json`; no decide |
| Escribano | Sonnet · alto | Revisa cada spec antes de arrancar |
| Baqueano | Sonnet · medio | Contesta las dudas de los generadores desde las fuentes |
| Generador de plan / de tests | Sonnet · alto | Escriben `plan.md` y `tests.md` |
| Alineador | Opus · alto | Cruza los contratos del lote y marca los choques |
| Verificador | Sonnet · medio | Preguntas desde la spec, contestadas sin ver al generador |
| Corrector | Sonnet · medio | Corrige solo lo marcado |
| Juez | Opus · alto | Sesión aparte: ¿la solución sirve? |
| QA | Sonnet · alto | Convierte los casos en scripts |
| Implementador | Sonnet · medio | Despacha Obreros, corre GREEN, clasifica fallas |
| Obrero | Sonnet · medio (alto al escalar) | Implementa la Parte de un microservicio |
| Revisor | Sonnet · medio | Revisa la implementación de un repo |
| Cronista | Sonnet · medio | Cuenta lo que pasó |

Quién despacha: el Coordinador a todos; el Implementador a sus Obreros, Correctores y QA.
