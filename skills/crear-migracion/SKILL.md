---
name: crear-migracion
description: Usar cuando un ticket del workspace dcac-ia-context indica que hay que agregar una migración de base de datos (cambios de esquema/datos vía nasgrate). Es una skill ESPECIAL por tipo de cambio, invocada desde el plan de desarrollo (planear-ticket) y la implementación (implementar-ticket) cuando el ticket pide una migración. Triggers — "el ticket necesita una migración", "agregá la migration de T#####", "creá la migración para estos cambios de DB". NO crear migraciones si el ticket no lo pide.
---

# Crear migración (nasgrate)

Encapsula las reglas para agregar una migración de base de datos en el ecosistema dCaC.
Las migraciones **no viven en los repos de los microservicios**: viven centralizadas en el
repo `nasgrate`. Esta es una **skill especial por tipo de cambio**: se invoca desde el plan
de desarrollo y desde la implementación **solo cuando el ticket indica que hace falta una
migración** (no se crean migraciones "porque sí").

## Precondición — repo nasgrate (regla dura)

Antes de tocar nada, verificá que existe el repo:
`microservicios/nasgrate/data/migrations/`.

**Si el repo NO existe → FRENÁ el proceso y notificá al usuario.** No inventes otra ubicación
ni crees el directorio: es señal de que falta clonar el repo (`microservicios/clone-all.sh`).

## Precondición — branch del ticket (regla dura)

**`nasgrate` es un repositorio git independiente, igual que cualquier microservicio.** No
escribas el archivo de migración estando en `master` (ni en la branch de otro ticket).
Antes de crear el archivo:

```bash
cd microservicios/nasgrate && git status && git branch --show-current
```

- Si está en `master` (o en la branch de otro ticket) y **limpio** → `git checkout -b T#####`
  (o `git checkout T#####` si ya existe) antes de escribir el archivo.
- Si tiene cambios sin commitear de **otro** ticket → no lo toques; usá el mismo criterio de
  aislamiento que el resto del workspace (ver `entorno-ticket`) y avisá si hace falta una
  branch/clon aparte.
- El archivo de migración se crea **dentro de la branch `T#####`**, nunca en `master`.

## Las 8 reglas

1. **Ubicación:** toda migración va en `microservicios/nasgrate/data/migrations/`. En
   ningún otro lado.
2. **Repo ausente ⇒ stop:** si no existe el repo, frená y avisá (ver precondición).
3. **Nombre del archivo:** formato `YYYYMMDDHHMMSS_Descripcion_En_Snake_Case.sql`.
   - El prefijo es un timestamp de 14 dígitos (`date +%Y%m%d%H%M%S`).
   - La descripción va en `Snake_Case` con mayúscula inicial por palabra, **sin el número
     de ticket** (ej. `20260704114746_Contratos_Origen.sql`, no
     `20260704114746_T20993_Contratos_Origen.sql`). El `Name:` del header replica ese mismo
     nombre sin ticket. La referencia al ticket va **solo** en `Description` (regla 7 del
     header) — ese campo sí la necesita para trazabilidad.
   - La forma canónica del equipo es `docker-compose run --rm nasgrate generate <Nombre>`
     (genera el archivo con timestamp + header). Si se crea el archivo directo, respetar
     exactamente este formato de nombre.
4. **Un archivo, todos los cambios:** salvo que semánticamente no convenga, el archivo
   contiene **TODOS los cambios de DB del ticket** (varias tablas/ALTERs juntos). No
   partir en muchas migraciones lo que es un solo entregable.
5. **Nunca de más:** no se crean migraciones si el ticket no lo pide. El ticket indica que
   hace falta y recién ahí se invoca este comportamiento.
6. **Solo UP, nunca DOWN:** la base siempre muta hacia adelante. Escribí únicamente la
   sección `-- UP --`. Dejá `-- DOWN --` vacía (o no la escribas). Nunca escribas SQL de
   reversión.
7. **Autor = usuario real, nunca "claude":** en el header, el autor debe ser el dev real.
   Tomalo de `git config user.name`. **Jamás** debe figurar
   que la migración la creó Claude/una IA. Si `git config user.name` está vacío, pedíselo
   al usuario.
8. **Sin esquemas nuevos:** no crear schemas/bases nuevas. Prefijar cada tabla con el
   esquema existente que indique el ticket (`dcac.`, `negocios.`, etc.). Si el ticket no
   dice en qué esquema, es una **DUDA** (no lo asumas).

## Regla adicional del workspace (ya vigente)

- **Solo `PRIMARY KEY`.** En las migraciones nasgrate no se agregan índices secundarios ni
  FK constraints, aunque haya columnas `*_id`. Solo la clave primaria.

## Formato del archivo

Header (lo genera `nasgrate generate`; si lo escribís a mano, replicalo tal cual):

```sql
-- Skip: no
-- Name: <Nombre_De_La_Migracion>
-- Date: DD.MM.YYYY HH:MM:SS
-- Description: T##### - <qué hace>. Created by <git user.name>, <YYYY-MM-DD HH:MM:SS>

-- UP --

ALTER TABLE dcac.detalles_carga
    ADD COLUMN gastos_bancarios FLOAT DEFAULT 0;

-- DOWN --
```

- El bloque `-- UP --` contiene **todo el SQL del ticket**, cada tabla prefijada con su
  esquema.
- `-- DOWN --` queda **vacía** (regla 6).
- Tablas nuevas: `ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_spanish_ci`, con
  `created_at/updated_at/deleted_at` si el patrón del dominio los usa, y **solo**
  `PRIMARY KEY (\`id\`)` (sin FKs).

## Aplicar la migración (fuera de esta skill)

Esta skill **crea el archivo correcto**. Aplicarla corre en la fase de implementación
(`implementar-ticket`), en Docker y contra la **DB de pruebas** (`db-test`, :3307)
para los tests, nunca la de desarrollo:
`cd microservicios/nasgrate && docker-compose run --rm nasgrate up` (apuntando el `.env`
a la DB que corresponda). No commitees el archivo — el usuario maneja git.

## Salida (modo orquestado)

Cuando la invoca el motor / `implementar-ticket`, devolvé:

```
ARTEFACTO: microservicios/nasgrate/data/migrations/<archivo>.sql (branch T##### de nasgrate)
DUDAS:
  - [D1] <ej. el ticket no dice en qué esquema> · <por qué no se puede asumir>
SUGERENCIAS:
  - [S1] <ej. conviene un índice, pero va aparte por la regla PK-only>
ESTADO: completo | frenado-por-duda
```

## Errores comunes

- **Crear la migración en el repo del microservicio** → no; siempre en `nasgrate`.
- **Crear el archivo estando en `master` de `nasgrate`** → no; `nasgrate` es un repo propio,
  hay que pasar a la branch `T#####` (o crearla) antes de escribir el archivo, igual que en
  cualquier otro microservicio del ticket.
- **Incluir el número de ticket en el nombre del archivo/`Name:`** → no; va solo en
  `Description`. El nombre del archivo describe el cambio, no el ticket.
- **Escribir SQL en `-- DOWN --`** → no; solo UP (regla 6).
- **Firmar como "creada por Claude"** → jamás; autor = `git config user.name` (regla 7).
- **Crear un schema nuevo o no prefijar la tabla** → prohibido; usar el esquema del ticket
  (regla 8). Si no está indicado, es una DUDA.
- **Agregar índices secundarios o FKs** → no; solo `PRIMARY KEY`.
- **Partir en varias migraciones un mismo entregable** → un archivo con todos los cambios,
  salvo que semánticamente no convenga (regla 4).
- **Crear una migración que el ticket no pidió** → no; solo si el ticket lo indica (regla 5).
