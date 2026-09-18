---
name: mostrar-diff
description: Usar cuando ya hay cambios REALES (implementados, commiteados o no) en un repo del workspace dcac-ia-context y el usuario quiere ver el diff archivo por archivo, estilo GitHub, en un puerto local. Triggers — "mostrame los cambios que vas a subir", "quiero ver el diff estilo github", "levantalo en otro puerto", "diff real de T#####". NO usar para cambios todavia no implementados (eso es previsualizar-cambios, que renderiza snippets desde plan.md antes de tocar codigo). NO levanta el dashboard.
---

# Previsualizar diff real

Sirve el **diff real de git** (no un plan) de un repo del workspace, archivo por archivo,
con estilo visual tipo GitHub (verde/rojo, unified diff), en un puerto local standalone —
sin dashboard. **Es en vivo**: recalcula el diff en cada request (no una foto fija tomada al
arrancar) y la página se auto-refresca sola cada pocos segundos — dejalo abierto mientras
implementás y vas viendo cada archivo aparecer/cambiar sin relanzar el servidor (ver
`resolver-ticket` para el uso durante la implementación).

## Cuándo usar

- Ya hay código escrito (working tree con cambios, o una branch ya commiteada) y el usuario
  quiere revisarlo visualmente antes de aprobar `/enviar-cambios`.
- Pide explícitamente verlo "en un puerto", "estilo GitHub", "sin dashboard".

**No usar** para cambios todavía no implementados — eso es `previsualizar-cambios` (extrae
snippets de un `plan.md` antes de la Fase 4). Esta skill lee el estado real vía `git`, no
un plan.

## Uso

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/mostrar-diff/serve.py \
  --repo microservicios/<ms>  \
  --base master
```

- `--repo`: path al repo (debe tener `.git`). Requerido.
- `--base`: ref contra el que comparar (default `master`). Usar `master` salvo que el usuario
  pida comparar contra otra cosa.
- `--ticket`: etiqueta para el título (default: nombre de la branch actual).
- `--port`: si se omite, busca automáticamente el primer puerto libre desde `8791` —
  **no asumas un puerto fijo**, el 8790 suele estar ocupado por `dashboard-desarrollo`.

El script arma el diff solo (antes/después completo por archivo vía `git show <base>:<archivo>`
+ contenido actual del working tree) y lo sirve — no requiere un JSON intermedio como
`previsualizar-cambios`.

**Correr siempre en background** (bloquea sirviendo):
```bash
python3 -u ${CLAUDE_PLUGIN_ROOT}/skills/mostrar-diff/serve.py --repo <repo> --base master \
  > /tmp/diff_preview.log 2>&1 &
disown
sleep 1 && cat /tmp/diff_preview.log   # confirma el puerto elegido
```

Si no hay diferencias contra `--base`, o el path no es un repo git, el script termina con
`exit 1` y un mensaje claro en stderr — no cuelga ni sirve una página vacía.

## Salida

Devolvé al usuario la URL (`http://127.0.0.1:<puerto>`) que imprime el script. Aclarale que
es el diff **real** (working tree vs `--base`), no un plan.

## Errores comunes

- **Asumir el puerto 8790/8792** → puede estar ocupado (dashboard u otra preview corriendo).
  Dejar que el script elija puerto libre, o revisar el log antes de pasarle la URL al usuario.
- **Correrlo en foreground** → bloquea la sesión; siempre `&` + `disown` + redirect a log.
- **Usarlo para cambios de un plan.md sin implementar** → esa es `previsualizar-cambios`.
- **No matar el proceso viejo antes de relanzar** → si el usuario pide "otro puerto", el
  anterior puede seguir vivo; no hace falta matarlo (son procesos livianos), pero si genera
  confusión sobre qué preview está en qué puerto, `pkill -f mostrar-diff/serve.py`.
