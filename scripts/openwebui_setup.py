"""Put webllm into Open WebUI (PLAN-v5 D2, F1/F2), through Open WebUI's own admin API.

    python scripts/openwebui_setup.py --clave <clave de Open WebUI> [--openwebui http://127.0.0.1:8080]
                                      [--webllm http://127.0.0.1:20130] [--webllm-token TOKEN]

Without --openwebui it finds Open WebUI on this PC (the desktop app uses 8080; Docker installs, 3000).

What it does (running it again updates everything, nothing is duplicated):
1. installs the "webllm" pipe (openwebui/webllm_pipe.py) and gives it webllm's address and key;
2. installs the mode switches (openwebui/webllm_modo_*.py) for the "+" of the text box;
3. sets every webllm model in Open WebUI: its files go whole to webllm (Open WebUI does not read them
   itself: "file_context" off), pictures allowed, the mode switches it can use, and only the tools Iván
   switches on (Open WebUI's own built-in tools off: "builtin_tools");
4. turns off the background jobs that would only add noise (tags, follow-up suggestions,
   autocompletion, search queries); titles stay on, and the pipe makes them without asking anyone;
5. hides Open WebUI's own "Arena" model (not used);
6. files are not read nor indexed by Open WebUI on upload (webllm gets them whole; this also avoids
   downloading its embedding model to the PC);
7. the suggestions under the text box, in Spanish;
8. tool approvals are on, and every conversation asks first by default (Iván's own setting,
   D21: nothing runs without his yes); "context compaction" is off (it would ask the model for
   summaries: messages of Iván's chats).
9. every webllm model gets Open WebUI's tools as they are ("function_calling: native"): webllm decides which tools
   an AI may even see and checks every request (acciones.yaml, PLAN-v5 F9); the old "legacy" mode would have
   Open WebUI choose the tool itself, around webllm.
The Open WebUI key: Open WebUI → Ajustes → Cuenta → Claves de API → Crear (an administrator's key).
Without --webllm-token it reads webllm's own key from data/state/bridge_token on this PC.

Connectors (PLAN-v5 F9), added to the ones Open WebUI already has (by their id, nothing duplicated):
    --github          GitHub's official MCP server; the token (fine-grained, only your repositories, no
                      administration) comes from the environment variable WEBLLM_GITHUB_TOKEN or is asked for
                      without showing it. It is kept only in Open WebUI's own settings: never in webllm, never in git.
    --terminal URL    your terminal's MCP server (through mcpo: http://127.0.0.1:8765; a URL ending in /mcp is an
                      MCP server Open WebUI talks to directly).
    --solo-conectores only the connectors (webllm itself is not reinstalled).
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS_DIR = ROOT / "openwebui"
PIPE_ID = "webllm"
ACTION_ID = "webllm_continuar"  # "Continuar en la web", under the answers of the web chats (PLAN-v5 F6)
# The background jobs turned off; ENABLE_TITLE_GENERATION stays as it is (the pipe answers it itself).
TASKS_OFF = ("ENABLE_TAGS_GENERATION", "ENABLE_FOLLOW_UP_GENERATION", "ENABLE_AUTOCOMPLETE_GENERATION",
             "ENABLE_SEARCH_QUERY_GENERATION", "ENABLE_RETRIEVAL_QUERY_GENERATION")
SUGGESTIONS = [
    {"title": ["Explícame algo", "con palabras sencillas"], "content": "Explícame con palabras sencillas: "},
    {"title": ["Ayúdame a programar", "paso a paso"], "content": "Ayúdame a programar esto, paso a paso: "},
    {"title": ["Resume un texto", "en cinco puntos"], "content": "Resume este texto en cinco puntos:\n\n"},
]
# builtin_tools off: Open WebUI would hand every model its own tools (the time, memory, notes...) without
# Iván switching them on; with it off, an AI only gets the tools he turns on in the "+" (D21).
# PLAN-v5 F9: GitHub's official MCP server (docs/remote-server.md of github/github-mcp-server) with the toolsets
# for reading and proposing; webllm narrows it further to the tools in acciones.yaml ("github" = their prefix).
GITHUB_MCP = "https://api.githubcopilot.com/mcp/"
GITHUB_TOOLSETS = "context,repos,issues,pull_requests"
CAPABILITIES = {"file_context": False, "vision": True, "file_upload": True, "web_search": False,
                "image_generation": False, "code_interpreter": False, "citations": False, "builtin_tools": False}


def frontmatter(source: str) -> dict[str, str]:
    """The "key: value" lines of a function file's header docstring."""
    head = source.split('"""', 2)[1] if source.startswith('"""') else ""
    return {k.strip(): v.strip() for k, v in re.findall(r"^([a-z_]+):\s*(.+)$", head, re.M)}


def functions_to_install() -> list[dict[str, str]]:
    out = [{"id": PIPE_ID, "file": "webllm_pipe.py"}, {"id": ACTION_ID, "file": "webllm_continuar.py"}]
    for f in sorted(FUNCTIONS_DIR.glob("webllm_modo_*.py")):
        out.append({"id": f.stem.replace("webllm_modo_", "webllm_"), "file": f.name})
    for item in out:
        source = (FUNCTIONS_DIR / item["file"]).read_text(encoding="utf-8")
        meta = frontmatter(source)
        item.update(content=source, name=meta.get("title", item["id"]), description=meta.get("description", ""))
    return out


class OpenWebUI:
    def __init__(self, url: str, key: str, transport: httpx.BaseTransport | None = None) -> None:
        self.http = httpx.Client(base_url=url.rstrip("/"), headers={"Authorization": f"Bearer {key}"}, timeout=60,
                                 transport=transport)

    def call(self, method: str, path: str, missing_ok: bool = False, **kw):
        r = self.http.request(method, path, **kw)
        if missing_ok and r.status_code == 404:
            return None
        if r.status_code == 401:
            raise SystemExit("Open WebUI no acepta la clave: créala de nuevo en Ajustes → Cuenta → Claves de API "
                             "(con tu usuario administrador) y vuelve a ejecutar esto.")
        r.raise_for_status()
        return r.json() if r.content else None


def webllm_models(webllm_url: str, webllm_token: str) -> dict[str, dict[str, str]]:
    """webllm's own name and card for each model (Open WebUI keeps the names it saved the first time)."""
    data = httpx.get(f"{webllm_url}/gw/v1/models", headers={"Authorization": f"Bearer {webllm_token}"}, timeout=10).json()
    return {PIPE_ID + "." + m["id"]: {"name": m.get("name") or m["id"], "card": (m.get("webllm") or {}).get("card", ""),
                                      "kind": (m.get("webllm") or {}).get("kind", "")}
            for m in data["data"]}


def install(ow: OpenWebUI, webllm_url: str, webllm_token: str, say=print,
            known: dict[str, dict[str, str]] | None = None) -> dict[str, list[str]]:
    report: dict[str, list[str]] = {"functions": [], "models": []}
    existing = {f["id"]: f for f in ow.call("GET", "/api/v1/functions/")}
    filters: list[str] = []
    for fn in functions_to_install():
        form = {"id": fn["id"], "name": fn["name"], "content": fn["content"], "meta": {"description": fn["description"]}}
        if fn["id"] in existing:
            ow.call("POST", f"/api/v1/functions/id/{fn['id']}/update", json=form)
        else:
            ow.call("POST", "/api/v1/functions/create", json=form)
        current = ow.call("GET", f"/api/v1/functions/id/{fn['id']}")
        if not current.get("is_active"):
            ow.call("POST", f"/api/v1/functions/id/{fn['id']}/toggle")
        if fn["id"] in (PIPE_ID, ACTION_ID):
            ow.call("POST", f"/api/v1/functions/id/{fn['id']}/valves/update",
                    json={"WEBLLM_URL": webllm_url, "WEBLLM_TOKEN": webllm_token})
        else:
            filters.append(fn["id"])
        report["functions"].append(fn["id"])
        say(f"  instalado: {fn['name']}")

    models = [m for m in ow.call("GET", "/api/models").get("data", []) if str(m.get("id", "")).startswith(PIPE_ID + ".")]
    if not models or any(m["id"] in (f"{PIPE_ID}.apagado", f"{PIPE_ID}.sin-llave") for m in models):
        raise SystemExit("webllm no contesta a Open WebUI (¿está apagado, o la llave no vale?). "
                         "Abre webllm con su icono y vuelve a ejecutar esto.")
    known = known if known is not None else webllm_models(webllm_url, webllm_token)
    for m in models:
        mine = known.get(m["id"], {})
        form = {"id": m["id"], "base_model_id": None, "name": mine.get("name") or m.get("name") or m["id"],
                "params": {"function_calling": "native"},
                "meta": {"description": mine.get("card") or "Una IA de webllm.", "capabilities": CAPABILITIES,
                         # the Committee decides "pensar" for each chat itself (its plan says so) and Automático
                         # chooses the AI by its written rules: neither gets the switches
                         "filterIds": filters if mine.get("kind") not in ("comite", "automatico") else [],
                         "actionIds": [ACTION_ID] if mine.get("kind") == "chat" else []}}
        if ow.call("GET", "/api/v1/models/model", missing_ok=True, params={"id": m["id"]}):
            ow.call("POST", "/api/v1/models/model/update", json=form)
        else:
            ow.call("POST", "/api/v1/models/create", json=form)
        report["models"].append(m["id"])
    say(f"  modelos de webllm configurados: {len(models)}")

    ow.call("POST", "/api/v1/retrieval/config/update", json={"BYPASS_EMBEDDING_AND_RETRIEVAL": True})
    ow.call("POST", "/api/v1/configs/suggestions", json={"suggestions": SUGGESTIONS})
    say("  archivos: van enteros a webllm (Open WebUI no los lee por su cuenta); sugerencias en español")
    chat = ow.call("GET", "/api/v1/chats/config")
    chat.update(ENABLE_TOOL_PERMISSIONS=True, ENABLE_CONTEXT_COMPACTION=False)
    ow.call("POST", "/api/v1/chats/config", json=chat)
    settings = ow.call("GET", "/api/v1/users/user/settings", params={"raw": "true"}) or {}
    ui = dict(settings.get("ui") or {})
    ui["params"] = {**(ui.get("params") or {}), "tool_approval_mode": "ask"}
    ow.call("POST", "/api/v1/users/user/settings/update", json={**settings, "ui": ui})
    say("  herramientas: siempre te preguntan antes de usarse; resúmenes automáticos del contexto: apagados")
    # Open WebUI's own "Arena" model (blind comparisons) is not used: out of the selector (D18).
    ow.call("POST", "/api/v1/evaluations/config", json={"ENABLE_EVALUATION_ARENA_MODELS": False})
    tasks = ow.call("GET", "/api/v1/tasks/config")
    tasks.update({k: False for k in TASKS_OFF})
    ow.call("POST", "/api/v1/tasks/config/update", json=tasks)
    say("  tareas de fondo que gastarían mensajes: apagadas (los títulos los pone webllm sin preguntar a nadie)")
    return report


def connect_tools(ow: OpenWebUI, *, github_token: str | None = None, terminal_url: str | None = None,
                  say=print) -> list[str]:
    """GitHub and the terminal as Open WebUI connections (PLAN-v5 F9). The others Iván has are kept; these are
    replaced by their id. Open WebUI asks before each tool is used (step 8)."""
    current = (ow.call("GET", "/api/v1/configs/tool_servers") or {}).get("TOOL_SERVER_CONNECTIONS") or []
    new = []
    if github_token:
        new.append({"url": GITHUB_MCP, "path": "", "type": "mcp", "auth_type": "bearer", "key": github_token,
                    "headers": {"X-MCP-Toolsets": GITHUB_TOOLSETS}, "config": {"enable": True},
                    "info": {"id": "github", "name": "GitHub", "description": "Leer y proponer cambios (issues, ramas, PR)"}})
        say("  GitHub: conectado (solo leer y proponer; cada uso te pide permiso)")
    if terminal_url:
        mcp = terminal_url.rstrip("/").endswith("/mcp")
        new.append({"url": terminal_url.rstrip("/"), "path": "" if mcp else "openapi.json", "type": "mcp" if mcp else "openapi",
                    "auth_type": "none", "key": "", "config": {"enable": True},
                    "info": {"id": "terminal", "name": "Terminal", "description": "Tu terminal (cada comando te pide permiso)"}})
        say("  Terminal: conectada (cada comando te pide permiso; los peligrosos, webllm no los deja pedir)")
    ids = {c["info"]["id"] for c in new}
    kept = [c for c in current if ((c.get("info") or {}).get("id")) not in ids]
    if new:
        ow.call("POST", "/api/v1/configs/tool_servers", json={"TOOL_SERVER_CONNECTIONS": [*kept, *new]})
    return sorted(ids)


CANDIDATES = ("http://127.0.0.1:8080", "http://127.0.0.1:3000", "http://127.0.0.1:8081")


def find_openwebui() -> str | None:
    """The first address on this PC that answers like Open WebUI (its /api/version)."""
    for url in CANDIDATES:
        try:
            if "version" in httpx.get(f"{url}/api/version", timeout=2).json():
                return url
        except (httpx.HTTPError, ValueError):
            continue
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pone webllm dentro de Open WebUI.")
    ap.add_argument("--openwebui", default="")
    ap.add_argument("--clave", required=True, help="clave de API de Open WebUI (de un administrador)")
    ap.add_argument("--webllm", default="http://127.0.0.1:20130")
    ap.add_argument("--webllm-token", default="")
    ap.add_argument("--data", default=str(ROOT / "data"))
    ap.add_argument("--github", action="store_true", help="conecta el servidor MCP oficial de GitHub")
    ap.add_argument("--terminal", default="", help="dirección del MCP de tu terminal (mcpo)")
    ap.add_argument("--solo-conectores", action="store_true")
    a = ap.parse_args(argv)
    if a.clave.strip().startswith(("github_pat_", "ghp_", "gho_", "ghu_", "ghs_")):  # never printed back
        print("Eso que has pegado es tu token de GitHub, no la clave de Open WebUI. No se ha enviado a ningún sitio.\n"
              "Primero va la clave de Open WebUI (en Open WebUI: tu nombre → Ajustes → Cuenta → Claves de la API);\n"
              "el token de GitHub se pide justo después.")
        return 1
    github_token = None
    if a.github:
        github_token = os.environ.get("WEBLLM_GITHUB_TOKEN", "").strip() or getpass.getpass(
            "Pega tu token de GitHub (no se verá) y pulsa Enter: ").strip()
        if not github_token:
            print("No has pegado ningún token de GitHub. Mira los pasos en docs\\F9-acciones.md.")
            return 1
    if not a.openwebui:
        a.openwebui = find_openwebui() or ""
        if not a.openwebui:
            print("No encuentro Open WebUI en este PC: no está abierto, o no está instalado.\n"
                  "Ábrelo y vuelve a ejecutar esto. Si no lo tienes, cómo instalarlo: docs\\F1-cara.md, «Para ti».")
            return 1
        print(f"Open WebUI encontrado en {a.openwebui}")
    ow = OpenWebUI(a.openwebui, a.clave)
    try:
        if not a.solo_conectores:
            token = a.webllm_token or (Path(a.data) / "state" / "bridge_token").read_text(encoding="utf-8").strip()
            print("Poniendo webllm dentro de Open WebUI…")
            install(ow, a.webllm, token)
        if github_token or a.terminal:
            print("Conectando herramientas…")
            connect_tools(ow, github_token=github_token, terminal_url=a.terminal or None)
    except httpx.HTTPError as exc:
        print(f"No pude hablar con Open WebUI en {a.openwebui}: ¿está abierto? ({exc})")
        return 1
    print("Listo. En Open WebUI, elige arriba una IA de webllm y pregunta."
          + (" Las herramientas se encienden en el «+» de la caja de texto." if github_token or a.terminal else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
