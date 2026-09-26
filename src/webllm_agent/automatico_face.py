"""PLAN-v5 F8: "webllm · Automático" in Open WebUI, and what the app shows of it.

A question to "Automático" is read with the written rules (automatico.py) and then goes, as it came, through the
same path as if Iván had picked that AI himself (guard, budget, journal, vault, "Parar"): the only differences are
the answer's first line (what it chose and why, D21.3) and a line in the journal. Nothing is sent to a second AI
if the chosen one fails: the error says what happened, like any other. An idea to evaluate goes to the Committee,
which shows its plan first; while a plan waits in this conversation, "adelante", "cancela" and the like go to it.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from aiohttp import web

from . import automatico, committee, committee_face
from .appapi import RECENT_S, site_of
from .broadcaster import new_run_id

if TYPE_CHECKING:
    from .config import AppConfig, ProviderConfig
    from .gateway import Gateway

RECENT_WORDS = {"saturada": "saturada", "sin_sesion": "sin sesión"}


def recent_of(api: Any):
    """An AI that failed a moment ago (saturated, no session): skipped for a while (RECENT_S), and said."""
    def recent(p: "ProviderConfig") -> str | None:
        hit = api.recent.get(p.name)
        if not hit:
            return None
        state, _detail, when = hit
        ago = time.time() - when
        if ago > RECENT_S:
            return None
        return f"falló hace {max(1, round(ago / 60))} min ({RECENT_WORDS.get(state, state)})"
    return recent


async def decide(bridge: Any, cfg: "AppConfig", question: str, files: list[dict[str, Any]],
                 previous: str | None = None) -> automatico.Choice:
    api = bridge.app_api
    table, models = automatico.load_table(), automatico.load_models()
    reading = automatico.classify(table, question, files, previous)
    ready = await committee_face.readiness(bridge, cfg, who="Automático")
    return automatico.choose(
        cfg, table, models, reading, ready=ready, recent=recent_of(api),
        card=lambda p: api.ficha_view(p, site_of(p)) if site_of(p) else None,
        catalog_name=lambda key: (api.catalog.get(key).name if api.catalog.get(key) else None), files=files)


async def handle(gw: "Gateway", request: web.Request, body: dict[str, Any]) -> web.StreamResponse:
    from .gateway import Reply, _inline_images, _last_user_text, decode_files
    ext = body.get("webllm") if isinstance(body.get("webllm"), dict) else {}
    cfg = await gw.bridge.app_api._cfg()
    chat_id = str(ext.get("chat_id") or "")[:100] or "sin-chat"
    messages = body.get("messages") if isinstance(body.get("messages"), list) else []
    last = _last_user_text(messages)
    pending = committee.load_pending(cfg.paths, chat_id)
    if pending is not None and committee.reply_kind(last)[0] != "problem":  # "adelante", "cancela", "con 3"…
        return await committee_face.handle(gw, request, {**body, "model": committee.MODEL_ID})
    files = decode_files([*(ext.get("files") or []), *_inline_images(messages)])  # RequestError: said by the gateway
    table = automatico.load_table()
    choice = await decide(gw.bridge, cfg, last, files, automatico.previous_type(table, messages))
    line = automatico.route_line(choice)
    if pending is not None and committee.drop_pending(cfg.paths, chat_id):  # a new question: the waiting plan goes
        line += " El plan del Comité que esperaba tu «adelante» se ha descartado."
    if choice.committee:
        return await committee_face.handle(gw, request, {**body, "model": committee.MODEL_ID}, prefix=line)
    if choice.provider is None:  # nobody can take it now: nothing is sent, and it says what to do
        reply = Reply(request, bool(body.get("stream")), new_run_id(), automatico.MODEL_ID)
        await reply.open()
        return await gw._finish_text(reply, automatico.nobody_text(choice))
    journal = {"tipo": choice.reading.type, "por_que": choice.reading.why_text(), "paso": choice.reading.step,
               "eligio": choice.provider.name, "saltadas": [list(x) for x in choice.skipped]}
    forward = {**body, "model": choice.provider.name}  # the gateway keeps Automático's first lines away from the AI
    return await gw.answer(request, forward, route={"line": line, "journal": journal})


# ---------------------------------------------------------------------------------------------- the app

async def view(bridge: Any, cfg: "AppConfig") -> dict[str, Any]:
    """The table as it is now: every type with its list and, for each AI, whether it is available and why not."""
    api = bridge.app_api
    table, models = automatico.load_table(), automatico.load_models()
    state = automatico.load_state(cfg.paths)
    ready = await committee_face.readiness(bridge, cfg, who="Automático")
    recent = recent_of(api)
    from .catalog import eligible_for_auto
    from .committee import resolve
    from .config import is_blocked_model
    tipos = []
    for t in table.tipos.values():
        rows = []
        for name in t.route:
            if name == automatico.COMMITTEE:
                rows.append({"key": name, "label": committee.LABEL, "state": "comite", "why": t.sin_reserva, "added": False})
                continue
            p = resolve(cfg, name)
            label = p.display if p else automatico.label_of(name, models, lambda k: api.catalog.get(k).name if api.catalog.get(k) else None)
            if p is None:
                why = "sin configurar" if name in models else "sin conectar"
            elif not p.enabled:
                why = "está apagada"
            elif is_blocked_model(cfg, p.model):
                why = "no está permitida"
            elif not eligible_for_auto(p):
                why = "puede usar lo que escribes para entrenar" if p.gateway == "omniroute" else "no es privada"
            else:
                why = ready(p, 1) or recent(p)
            rows.append({"key": name, "label": label, "state": "lista" if why is None else "no", "why": why or "",
                         "added": name in t.añadidas, "api": name in models})
        chosen = next((r for r in rows if r["state"] in ("lista", "comite")), None)
        tipos.append({"key": t.key, "name": t.name, "rows": rows, "now": chosen["label"] if chosen else None})
    fichas = []
    for key, m in models.items():
        p = cfg.providers.get(key)
        on = state["activos"].get(key)
        fichas.append({**m.public(), "configurada": p is not None, "model": p.model if p else None,
                       "desde_omniroute": bool(on), "cuando": (on or {}).get("when"),
                       "privada": automatico.private_of(models, state, key),
                       "decidido_por_ti": key in state["privacidad"]})
    return {"checked": table.checked, "fuente": table.fuente, "reglas": table.steps(), "tipos": tipos, "fichas": fichas,
            "pruebas": automatico.load_tests(cfg.paths)["preguntas"]}


async def try_questions(bridge: Any, cfg: "AppConfig", questions: list[str]) -> list[dict[str, Any]]:
    """Iván's test (PLAN-v5 F8, "10 preguntas de prueba"): what Automático would choose for each question, with
    the reasons. Nothing is sent to any AI."""
    out = []
    for q in questions[:20]:
        text = str(q or "").strip()[:4000]
        if not text:
            continue
        c = await decide(bridge, cfg, text, [])
        out.append({"texto": text, "tipo": c.reading.name, "por_que": c.reading.why_text(),
                    "elegida": c.label or "nadie disponible", "saltadas": [list(x) for x in c.skipped],
                    "linea": automatico.route_line(c) if (c.provider or c.committee) else automatico.nobody_text(c)})
    return out


__all__ = ["decide", "handle", "recent_of", "try_questions", "view"]
