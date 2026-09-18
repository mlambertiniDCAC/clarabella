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
| `aislar-ticket` | Worktree + contenedor Docker + DB propios del ticket |
| `planear-ticket` | Plan del ticket (`docs/{proyecto}/{tipo}/T#####-{slug}/plan.md`) |
| `planear-tests-ticket` | Plan de tests E2E (`tests.md`) |
| `implementar-ticket` | Implementación guiada del plan |
| `testear-ticket` | Corre los casos documentados contra la DB del ticket |
| `mostrar-diff` | Diff estilo GitHub en un puerto local, en vivo |
| `resumir-ticket` | Resumen de cierre: plan + tests + resultados + desvíos |
| `enviar-review` | Commit + `arc diff --create`, solo con aprobación explícita |
| `crear-migracion` | Reglas para migraciones nasgrate |
| `consultar-grafo` | Usa `graphify-out/` del repo si existe |
| `leer-db` | Consultas de solo lectura a MariaDB/Postgres |

## Flujo de `resolver-ticket`

1. `preparar-repo` → `aislar-ticket`
2. `planear-ticket`
3. `planear-tests-ticket`
4. Implementar (directo o `implementar-ticket`), con `mostrar-diff` abierto
5. `testear-ticket`
6. `mostrar-diff`
7. `resumir-ticket`
8. `enviar-review`
