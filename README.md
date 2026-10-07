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

Herramientas que usan las skills: `git`, Docker, `python3` (para `mostrar-diff`), Arcanist
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
| `resolver-ticket` | Checklist del flujo completo; encadena las demás |
| `preparar-repo` | Master actualizado + branch `T#####` aislada |
| `aislar-ticket` | Worktree (etapa A) + contenedor Docker y DB propios del ticket (etapa B, en background) |
| `planear-ticket` | Plan del ticket (`docs/{proyecto}/{tipo}/T#####-{slug}/plan.md`) |
| `planear-tests-ticket` | Plan de tests E2E (`tests.md`) desde la spec, sin mirar el plan |
| `juicio-ticket` | Juicio de plan y tests (y de la implementación): Juez, defensa, peritos; lo sostenido lo corrige el mismo agente, solo en lo marcado |
| `escribano` | Revisa la spec antes de arrancar y le pide al usuario, en una sola ronda, todo lo que falta definir |
| `baqueano` | Responde las dudas de los agentes generativos desde las fuentes; lleva al usuario solo las decisiones |
| `ciclo-ticket` | Repite el desarrollo solo hasta la implementación correcta: escritura previa, vueltas con corrección acotada, provisorias, estancamiento y presupuesto |
| `ensayar-juicio` | Calibra el juicio con un ticket cerrado: código y doc del pasado, auditor contra la solución real |
| `implementar-ticket` | Implementación guiada del plan |
| `testear-ticket` | Corre los casos documentados en RED (antes de implementar) o GREEN (después), en un subagente que no escribió el código |
| `mostrar-diff` | Diff estilo GitHub en un puerto local, en vivo |
| `cronista` | La crónica del ticket (para equipo, producto, el usuario y el próximo ticket), borradores de arc diff y comentario, y el registro de decisiones del proyecto |
| `enviar-review` | Commit + `arc diff --create`, solo con aprobación explícita |
| `bajar-entorno` | Apaga lo del ticket (contenedores, volúmenes, preview, datos de prueba) |
| `crear-migracion` | Reglas para migraciones nasgrate |
| `consultar-grafo` | Usa `graphify-out/` del repo si existe |
| `leer-db` | Consultas de solo lectura a MariaDB/Postgres |

## Flujo de `resolver-ticket`

0. Fijar ticket, tipo, proyecto, guardar la spec (`spec.md`) y escriturarla con el `escribano` (una sola ronda de decisiones)
1. **Preparación**
   - `preparar-repo` → `aislar-ticket` etapa A (worktrees, repos en paralelo)
   - en background: `aislar-ticket` etapa B (contenedores + DB del ticket, de a uno)
   - en paralelo, sin verse: el agente generativo de tests (`planear-tests-ticket`) y el
     del plan (`planear-ticket`, con un explorador por repo antes)
   - sus dudas van al `baqueano` (uno por agente); al usuario llegan solo las decisiones
2. **El juicio** (`juicio-ticket`): el Juez acusa, los agentes se defienden, los peritos
   verifican para el Juez, el Juez sentencia, y lo sostenido lo corrige el mismo agente
   (solo en lo marcado; el Juez verifica solo el cambio). Decide y aprueba el usuario
3. **La implementación**: `testear-ticket` en RED → implementar con `mostrar-diff`
   abierto (en el hilo principal, o un subagente por repo en paralelo) → `testear-ticket`
   en GREEN (subagente nuevo) → juicio de la implementación → el usuario valida el diff
4. **La entrega**: `cronista` (crónica + borradores + decisiones al registro, con validación del usuario) → `enviar-review` → `bajar-entorno`

**Modo ciclo** (`ciclo-ticket`): presupuesto y escritura (todas las decisiones juntas,
antes de arrancar) → preparación → juicio → RED → vueltas de implementar, GREEN y juicio de la implementación hasta
cumplir la definición de terminado. Las fallas vuelven a quien las causó; el Baqueano
decide las menores con veto y toma las mayores como provisorias que el usuario confirma o
veta al final; pausa solo por terreno sensible (financiero, permisos, datos), una corrección fallida dos veces,
una regresión preexistente o el entorno caído; termina por terminado, estancamiento (misma
firma tres vueltas) o presupuesto. Al final, crónica y espera al usuario.

**Modelos por rol:** opus para el Juez, el agente del plan y el auditor de ensayos; sonnet
para el agente de tests, el Baqueano, el Escribano, los implementadores, RED/GREEN, el
verificador de correcciones y el Cronista; haiku para los peritos y los exploradores
(estos, solo con tres repos o más).
