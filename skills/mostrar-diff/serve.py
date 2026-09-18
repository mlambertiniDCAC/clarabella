#!/usr/bin/env python3
"""Servidor de preview de cambios REALES (git diff), estilo GitHub.

A diferencia de previsualizar-cambios (que renderiza snippets de un plan.md
ANTES de implementar), este script arma el diff desde git de verdad: compara
un ref base (default: master) contra el working tree de un repo, archivo por
archivo, antes/despues completo, y lo sirve en un puerto local. Sin
dependencias externas: solo stdlib (subprocess + difflib + http.server).

Uso:
    python3 serve.py --repo <path_al_repo> [--base master] [--port 0] [--host 127.0.0.1]

--port 0 (default) busca automaticamente el primer puerto libre a partir de 8791.
"""

import argparse
import difflib
import html
import json
import re
import socket
import subprocess
import sys
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True
    )
    return result.stdout


def show_at_ref(repo: Path, ref: str, path: str) -> str:
    """Contenido de un archivo en un ref dado, o '' si no existe ahi (archivo nuevo)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else ""


def read_worktree(repo: Path, path: str) -> str:
    """Contenido actual en el working tree, o '' si el archivo fue eliminado."""
    full = repo / path
    if not full.exists():
        return ""
    return full.read_text(encoding="utf-8", errors="replace")


def classify(status: str) -> str:
    if status.startswith("A"):
        return "nuevo"
    if status.startswith("D"):
        return "eliminacion"
    return "modificacion"


def collect_changes(repo: Path, base: str) -> list[dict]:
    """git diff --name-status <base> -> working tree, con before/after completos."""
    name_status = run_git(repo, "diff", "--name-status", base).strip()
    branch = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    repo_label = repo.name

    cambios = []
    for line in name_status.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status, path = parts[0], parts[-1]
        tipo = classify(status)
        before = "" if tipo == "nuevo" else show_at_ref(repo, base, path)
        after = "" if tipo == "eliminacion" else read_worktree(repo, path)
        cambios.append({
            "id": f"{repo_label}/{path}",
            "repo": repo_label,
            "archivo": path,
            "tipo": tipo,
            "estado_actual": before,
            "cambio": after,
        })
    return cambios, branch


HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def render_diff_lines(before: str, after: str) -> str:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    diff = difflib.unified_diff(before_lines, after_lines, lineterm="", n=3)
    rows = []
    old_ln = new_ln = 0
    for line in diff:
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("@@"):
            m = HUNK_RE.match(line)
            if m:
                old_ln, new_ln = int(m.group(1)), int(m.group(2))
            rows.append(
                f'<div class="line hunk"><span class="ln"></span><span class="ln"></span>'
                f'<span class="txt">{html.escape(line)}</span></div>'
            )
            continue
        if line.startswith("+"):
            cls, old_s, new_s = "add", "", str(new_ln)
            new_ln += 1
        elif line.startswith("-"):
            cls, old_s, new_s = "del", str(old_ln), ""
            old_ln += 1
        else:
            cls, old_s, new_s = "ctx", str(old_ln), str(new_ln)
            old_ln += 1
            new_ln += 1
        content = line[1:] if line else ""
        rows.append(
            f'<div class="line {cls}"><span class="ln">{old_s}</span><span class="ln">{new_s}</span>'
            f'<span class="txt">{html.escape(content) or "&nbsp;"}</span></div>'
        )
    if not rows:
        rows.append(
            '<div class="line ctx nochange"><span class="ln"></span><span class="ln"></span>'
            '<span class="txt">(sin cambios detectables)</span></div>'
        )
    return "\n".join(rows)


def render_card(idx: int, change: dict) -> str:
    archivo = html.escape(change.get("archivo", "(sin archivo)"))
    tipo = html.escape(change.get("tipo", "modificacion"))
    before = change.get("estado_actual", "") or ""
    after = change.get("cambio", "") or ""
    body = render_diff_lines(before, after)
    added = sum(1 for l in body.split("\n") if 'class="line add"' in l)
    removed = sum(1 for l in body.split("\n") if 'class="line del"' in l)
    return f"""
    <section class="card" id="f{idx}">
      <header class="card-h">
        <span class="tipo tipo-{tipo}">{tipo}</span>
        <span class="path">{archivo}</span>
        <span class="stat"><span class="plus">+{added}</span> <span class="minus">-{removed}</span></span>
      </header>
      <div class="diff">{body}</div>
    </section>"""


def render_page(ticket: str, base: str, branch: str, cambios: list[dict]) -> str:
    ticket_e = html.escape(ticket)
    base_e = html.escape(base)
    branch_e = html.escape(branch)
    by_repo = defaultdict(list)
    for c in cambios:
        by_repo[c.get("repo", "(sin repo)")].append(c)

    nav, blocks, idx = [], [], 0
    for repo, changes in by_repo.items():
        repo_e = html.escape(repo)
        nav.append(f'<li class="nav-repo">{repo_e}</li>')
        blocks.append(f'<h2 class="repo">{repo_e}</h2>')
        for c in changes:
            nav.append(f'<li><a href="#f{idx}">{html.escape(c.get("archivo", "?"))}</a></li>')
            blocks.append(render_card(idx, c))
            idx += 1

    total = len(cambios)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Diff real — {ticket_e}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: -apple-system, Segoe UI, Roboto, sans-serif;
         background:#0d1117; color:#c9d1d9; }}
  header.top {{ position:sticky; top:0; z-index:5; background:#161b22;
         border-bottom:1px solid #30363d; padding:14px 20px; }}
  header.top h1 {{ margin:0; font-size:18px; }}
  header.top .sub {{ color:#8b949e; font-size:13px; margin-top:2px; font-family:ui-monospace,monospace; }}
  header.top .live {{ color:#3fb950; font-size:11px; margin-left:8px; }}
  .wrap {{ display:flex; gap:20px; padding:20px; align-items:flex-start; }}
  nav {{ position:sticky; top:96px; width:260px; flex:0 0 260px; font-size:13px;
         max-height:80vh; overflow:auto; border:1px solid #30363d; border-radius:8px; padding:10px; }}
  nav ul {{ list-style:none; margin:0; padding:0; }}
  nav .nav-repo {{ color:#58a6ff; font-weight:600; margin:8px 0 4px; }}
  nav a {{ color:#c9d1d9; text-decoration:none; display:block; padding:2px 6px;
         border-radius:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  nav a:hover {{ background:#21262d; }}
  main {{ flex:1; min-width:0; }}
  h2.repo {{ font-size:15px; color:#58a6ff; border-bottom:1px solid #30363d;
         padding-bottom:6px; margin:24px 0 12px; }}
  .card {{ border:1px solid #30363d; border-radius:8px; margin-bottom:18px; overflow:hidden; }}
  .card-h {{ display:flex; align-items:center; gap:12px; background:#161b22;
         padding:8px 12px; border-bottom:1px solid #30363d; }}
  .card-h .path {{ font-family:ui-monospace, monospace; font-size:13px; flex:1;
         overflow:hidden; text-overflow:ellipsis; }}
  .tipo {{ font-size:11px; padding:2px 8px; border-radius:12px; text-transform:uppercase; }}
  .tipo-nuevo {{ background:#12261a; color:#3fb950; border:1px solid #238636; }}
  .tipo-modificacion {{ background:#1c2432; color:#58a6ff; border:1px solid #1f6feb; }}
  .tipo-eliminacion {{ background:#2d1214; color:#f85149; border:1px solid #da3633; }}
  .stat {{ font-family:ui-monospace, monospace; font-size:12px; }}
  .plus {{ color:#3fb950; }} .minus {{ color:#f85149; }}
  .diff {{ font-family:ui-monospace, SFMono-Regular, monospace; font-size:15px;
         line-height:1.6; overflow-x:auto; }}
  .line {{ display:grid; grid-template-columns:48px 48px 1fr; white-space:pre; }}
  .line .ln {{ text-align:right; padding:0 10px; color:#484f58; user-select:none;
         border-right:1px solid #21262d; }}
  .line .txt {{ padding:0 14px; white-space:pre; }}
  .line.add {{ background:#12261a; color:#56d364; }}
  .line.add .ln {{ background:#1b3423; }}
  .line.del {{ background:#2d1214; color:#f85149; }}
  .line.del .ln {{ background:#3a181a; }}
  .line.hunk {{ background:#161b22; color:#8b949e; }}
  .line.ctx {{ color:#c9d1d9; }}
  .line.nochange {{ font-style:italic; }}
</style></head>
<body>
<header class="top">
  <h1>Diff real — {ticket_e} <span class="live">● live</span></h1>
  <div class="sub">{branch_e} vs {base_e} · {total} archivo(s) · se refresca solo, sin relanzar el servidor</div>
</header>
<div class="wrap">
  <nav><ul>{''.join(nav)}</ul></nav>
  <main>{''.join(blocks) or '<p>Sin diferencias contra el base ref en este momento.</p>'}</main>
</div>
<script>
  // Auto-refresh preservando la posicion de scroll entre reloads.
  window.addEventListener('beforeunload', () => sessionStorage.setItem('diffScroll', window.scrollY));
  window.addEventListener('load', () => {{
    const y = sessionStorage.getItem('diffScroll');
    if (y) window.scrollTo(0, parseInt(y, 10));
  }});
  setTimeout(() => location.reload(), 4000);
</script>
</body></html>"""


def find_free_port(host: str, start: int) -> int:
    port = start
    while port < start + 200:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No se encontro puerto libre")


def main() -> int:
    ap = argparse.ArgumentParser(description="Preview de diff real (git) estilo GitHub.")
    ap.add_argument("--repo", required=True, help="Path al repo (ej. microservicios/ms-decampopagos).")
    ap.add_argument("--base", default="master", help="Ref base para comparar (default master).")
    ap.add_argument("--ticket", default=None, help="Etiqueta del ticket para el titulo (default: branch actual).")
    ap.add_argument("--port", type=int, default=0, help="Puerto (default: primero libre desde 8791).")
    ap.add_argument("--host", default="127.0.0.1", help="Host (default 127.0.0.1).")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"ERROR: {repo} no es un repo git (no tiene .git)", file=sys.stderr)
        return 1

    cambios, branch = collect_changes(repo, args.base)
    ticket = args.ticket or branch

    if not cambios:
        print(f"Sin diferencias entre {args.base} y el working tree en {repo}.", file=sys.stderr)
        return 1

    port = args.port or find_free_port(args.host, 8791)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            # Recalcula el diff en cada request (no una foto fija del arranque):
            # deja ver los archivos a medida que se escriben durante la implementacion.
            cambios, branch = collect_changes(repo, args.base)
            page = render_page(ticket, args.base, branch, cambios).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, *a):  # silenciar logs por request
            pass

    httpd = ThreadingHTTPServer((args.host, port), Handler)
    url = f"http://{args.host}:{port}"
    print(f"Diff real de {ticket} ({len(cambios)} archivo(s)) sirviendo en vivo en {url}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nPreview detenido.")
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
