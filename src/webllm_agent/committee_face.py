"""The Committee in Open WebUI (PLAN-v5 D4, F7): the model "webllm · Comité" of the gateway.

Iván writes the idea; webllm answers with the plan (who, which role, how many messages of each account, how long)
and sends NOTHING. "adelante" runs exactly that plan (if who is available changed meanwhile, the new plan is shown
again: nothing changes silently, D21); "cancela" drops it; "con 3" / "con 5" / "sin pensar" / "con pensar" redo it.
While it runs, what each AI is doing goes to the folded thinking block; the answer is the fusion document, and the
last chunk says who took part, with what, and what it spent.
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import TYPE_CHECKING, Any

from aiohttp import web

from . import committee, problems
from .broadcaster import new_run_id
from .flows import OK, STOPPED
from .guard import Guard
from .omniroute import load_api_key

if TYPE_CHECKING:
    from .config import AppConfig, ProviderConfig
    from .gateway import Gateway, Reply


def model_entry(cfg: "AppConfig") -> dict[str, Any]:
    """How the Committee shows in Open WebUI's selector."""
    st = committee.settings(cfg.paths)
    return {"id": committee.MODEL_ID, "object": "model", "owned_by": "webllm", "name": committee.LABEL,
            "webllm": {"kind": "comite", "label": committee.LABEL,
                       "card": (f"Evalúa una idea con {st['number']} IAs, cada una con un rol (arquitecto, abogado del "
                                "diablo, seguridad…); la más potente disponible junta sus veredictos en un documento. "
                                "Primero te dice quién participa y cuánto gasta de cada cuenta: no envía nada hasta que "
                                "escribas «adelante».")}}


async def readiness(bridge: Any, cfg: "AppConfig"):
    """``ready(p, messages)``: why an AI cannot take ``messages`` more right now, or None. "Disponible" (PLAN-v5
    section 6) = ready, not paused, under its cap for the day and fine in its last check."""
    from .appapi import site_of
    api = bridge.app_api
    chrome = bridge.connected.is_set()
    omni = await api._omniroute_up()
    revision = (api._read_revision().get("sites") or {})
    now = time.time()

    def ready(p: "ProviderConfig", need: int) -> str | None:
        site = site_of(p)
        guard, key = api._guard_for(p)
        st = guard.status().get(key, {})
        if (st.get("cooldown_until") or 0) > now:
            return "está en pausa"
        today, cap = api.usage(cfg, p)
        if cap is not None and today + need > cap:
            return f"le quedan {max(0, cap - today)} mensajes hoy y el Comité puede gastar {need}"
        if site and not chrome:
            return "Chrome no está conectado"
        state = (revision.get(site) or {}).get("state") if site else None
        if state not in (None, "bien", "reparada"):
            return f"en su última comprobación: {state.replace('_', ' ')}"
        if p.gateway == "omniroute" and not omni:
            return "OmniRoute está apagado"
        if p.gateway == "local":
            server = api.local.status_of(p.model.split("/", 1)[0])
            if server is None or not server.up:
                return "su programa del PC está apagado"
        return None
    return ready


async def plan_for(bridge: Any, cfg: "AppConfig", problem: str, *, number: int | None = None, think: bool | None = None,
                   files: list[dict[str, Any]] | None = None) -> committee.Plan:
    from .appapi import site_of
    api = bridge.app_api
    st = committee.settings(cfg.paths)
    ready = await readiness(bridge, cfg)
    return committee.make_plan(
        cfg, problem, number=number or st["number"], think=st["think"] if think is None else think,
        parallel_web=st["parallel_web"], participants=st["participants"], fusion=st["fusion"], roles=st["roles"],
        ready=ready, card=lambda p: api.ficha_view(p, site_of(p)) if site_of(p) else None,
        catalog_family=lambda site: (api.catalog.get(site).family if api.catalog.get(site) else None),
        catalog_name=lambda key: (api.catalog.get(key).name if api.catalog.get(key) else None),
        files=[{k: f[k] for k in ("name", "mime", "size", "sha256")} for f in files or []],
        spacing_s=float(cfg.guard.min_spacing_s))


NOTES = {
    "rol": "{seat} ({role}): recibe su rol…",
    "rol_otra_vez": "{seat} no respondió «CONFIRMO: {role}». Se lo pido otra vez, más corto.",
    "confirmado": "{seat} confirmó su rol: {role}. Ahora recibe el problema…",
    "formato": "El veredicto de {seat} no tiene el formato pedido: le pido que lo rehaga.",
    "fallo": "{seat} ({role}) no entra: {why}. No quedan reservas.",
}


def note(ev: dict[str, Any]) -> str | None:
    t = ev.get("type")
    if t == "seat":
        what = ev.get("what")
        if what == "veredicto":
            conf = f", confianza {ev['confidence']}" if ev.get("confidence") else ""
            return f"{ev['seat']} ({ev['role']}): {ev['value']}{conf}."
        tpl = NOTES.get(str(what))
        return tpl.format(seat=ev.get("seat"), role=ev.get("role"), why=ev.get("why", "")) if tpl else None
    if t == "reserve":
        return f"{ev['out']} no entra ({ev['why']}); ocupa su sitio {ev['in']}, con el mismo rol ({ev['role']})."
    if t == "count":
        return f"Recuento: {ev['text']}."
    if t == "fusion":
        return f"Escribe el documento de fusión {ev['by']}" + (" (también participó en el Comité)…" if ev.get("took_part") else "…")
    if t == "fusion_again":
        return f"Al documento le faltan apartados ({', '.join(ev.get('missing') or [])}): se lo pido otra vez."
    return None


async def handle(gw: "Gateway", request: web.Request, body: dict[str, Any]) -> web.StreamResponse:
    """One message to "webllm · Comité"."""
    from .gateway import RequestError, Reply, _inline_images, _last_user_text, decode_files
    ext = body.get("webllm") if isinstance(body.get("webllm"), dict) else {}
    if ext.get("task"):  # Open WebUI's own background jobs never reach the Committee's AIs
        return gw._error(400, "task_for_web_chat", problems.problem_text("task_for_web_chat", committee.LABEL))
    cfg = await gw.bridge.app_api._cfg()
    paths = cfg.paths
    chat_id = str(ext.get("chat_id") or "")[:100] or "sin-chat"
    messages = body.get("messages") if isinstance(body.get("messages"), list) else []
    last = _last_user_text(messages)
    kind, opts = committee.reply_kind(last)
    pending = committee.load_pending(paths, chat_id)
    stream = bool(body.get("stream"))
    reply = Reply(request, stream, new_run_id(), committee.MODEL_ID)

    async def say(text: str) -> web.StreamResponse:
        await reply.open()
        return await gw._finish_text(reply, text)

    if kind == "cancel":
        had = committee.drop_pending(paths, chat_id)
        return await say("Cancelado: no se ha enviado nada a ninguna IA." if had else
                         "No había ningún Comité esperando. Escribe la idea o el problema que quieres evaluar.")
    if kind == "go":
        if pending is None:
            return await say("No hay ningún Comité esperando tu «adelante». Escribe primero la idea o el problema.")
        plan, files = pending
        try:
            fresh = await plan_for(gw.bridge, cfg, plan.problem, number=plan.number, think=plan.think, files=files)
        except committee.CommitteeError as exc:
            committee.drop_pending(paths, chat_id)
            return await say(f"Desde el plan ha cambiado quién está disponible, y ahora no se puede: {exc}")
        if not fresh.same_people(plan):
            committee.save_pending(paths, chat_id, fresh, files)
            return await say("Desde el plan ha cambiado quién está disponible, así que no he lanzado nada. "
                             "Este es el plan de ahora:\n\n" + committee.plan_text(fresh))
        committee.drop_pending(paths, chat_id)
        return await run(gw, request, reply, cfg, plan, files, ext, chat_id)
    if kind in ("options", "unclear") and pending is not None:
        plan, files = pending
        if kind == "unclear":
            return await say("Para lanzar el Comité escribe **adelante**; para no hacerlo, **cancela**. "
                             "Si quieres evaluar otra cosa, escribe la idea entera.")
        try:
            fresh = await plan_for(gw.bridge, cfg, plan.problem, number=opts.get("number", plan.number),
                                   think=opts.get("think", plan.think), files=files)
        except committee.CommitteeError as exc:
            return await say(str(exc))
        committee.save_pending(paths, chat_id, fresh, files)
        return await say(committee.plan_text(fresh))
    # a problem to evaluate: the plan, and nothing sent
    try:
        files = decode_files([*(ext.get("files") or []), *_inline_images(messages)])
    except RequestError as exc:
        return gw._error(exc.status, exc.code, exc.message)
    kept = [{"name": f["name"], "mime": f["mime"], "size": f["size"], "sha256": f["sha256"],
             "data": base64.b64encode(f["bytes"]).decode("ascii")} for f in files]
    try:
        plan = await plan_for(gw.bridge, cfg, last, files=kept)
    except committee.CommitteeError as exc:
        return await say(str(exc))
    committee.save_pending(paths, chat_id, plan, kept)
    return await say(committee.plan_text(plan))


async def run(gw: "Gateway", request: web.Request, reply: "Reply", cfg: "AppConfig", plan: committee.Plan,
              files: list[dict[str, Any]], ext: dict[str, Any], chat_id: str) -> web.StreamResponse:
    """"adelante": the Committee runs; its notes go to the thinking block, the document is the answer."""
    from .appapi import site_of
    await reply.open()
    stop = asyncio.Event()
    gw.committees[reply.run_id] = stop
    try:
        api_key = load_api_key()
    except Exception:  # noqa: BLE001 - no key: the calls by API say so
        api_key = ""
    guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)

    async def emit(ev: dict[str, Any]) -> None:
        text = note(ev)
        if text:
            await reply.say(text)

    await reply.say(f"Comité de {plan.number}: " + ", ".join(f"{s.label} ({s.role['name']})" for s in plan.seats) + ".")
    work = asyncio.create_task(committee.run(
        cfg, plan, api_key=api_key, guard=guard, bridge_key=gw.bridge.token, emit=emit, stop=stop, run_id=reply.run_id,
        files=files or None, chat_id=chat_id if chat_id != "sin-chat" else "",
        message_id=str(ext.get("message_id") or "")[:100],
        project=str(ext.get("project") or "")[:80] or None, title=str(ext.get("title") or "")[:120] or None))
    sites = {site_of(cfg.providers[s.provider]) for s in [*plan.seats, *plan.reserves, *plan.fusion]
             if s.provider in cfg.providers} - {None}

    async def watch() -> None:
        """The face went away (its stop button): stop. A chat waiting for Iván: say so."""
        last = None
        while not work.done():
            if reply.gone():
                stop_committee(gw, reply.run_id)
                return
            waiting = next(((s, k) for s in sites if (k := gw.bridge.waiting.get(s))), None)
            if waiting != last:
                if waiting and waiting[1] in problems.WAITING_SHORT:
                    label = next((p.display for p in cfg.providers.values() if site_of(p) == waiting[0]), waiting[0])
                    await reply.say(problems.WAITING_SHORT[waiting[1]].format(ai=label))
                last = waiting
            await asyncio.sleep(0.5)

    watcher = asyncio.create_task(watch())
    beat = asyncio.create_task(reply.heartbeat())
    try:
        result = await asyncio.shield(work)
    except asyncio.CancelledError:
        if not work.done():
            stop_committee(gw, reply.run_id)
            raise
        result = work.result()
    except Exception as exc:  # noqa: BLE001 - said to Iván and logged; never a cut stream
        gw.bridge.log(f"Comité {reply.run_id}: falló por dentro: {type(exc).__name__}: {exc}")
        return await reply.error("committee_failed", "El Comité falló por dentro y se ha parado (el detalle está en el "
                                 "registro de webllm). Lo que respondieron hasta ese momento queda en tu historial.")
    finally:
        watcher.cancel()
        beat.cancel()
        gw.committees.pop(reply.run_id, None)
        gw.bridge.stopped.discard(reply.run_id)

    reply.avisos.extend(used_avisos(cfg, plan, result))
    if result.status == STOPPED:
        return await reply.error("cancelled", "Lo has parado tú. Lo que respondieron hasta ese momento queda en tu historial.")
    if result.status != OK:
        valid = [m for m in result.members if m.status in ("valid", "uncounted")]
        why = "; ".join(f"{m.seat.label}: {m.why}" for m in result.members if m.status == "failed")
        if result.tally is None:
            text = (f"El Comité no ha podido terminar: solo {len(valid)} IA{'s' if len(valid) != 1 else ''} "
                    f"dieron un veredicto válido y hacen falta 3.")
        else:
            text = "El Comité dio sus veredictos, pero ninguna IA de la lista de fusión pudo escribir el documento."
        return await reply.error("committee_failed", text + (f" Qué pasó: {why}." if why else "") +
                                 " Todo queda en tu historial; puedes lanzarlo otra vez.")
    return await gw._finish_text(reply, committee.chat_document(plan, result))


def used_avisos(cfg: "AppConfig", plan: committee.Plan, result: committee.Result) -> list[str]:
    """What was really used and spent (D21): each AI, its role, the model its page said, and its messages."""
    out = []
    parts = []
    for m in result.members:
        state = {"valid": "", "uncounted": ", su veredicto no cuenta", "failed": f", no entró: {m.why}"}.get(m.status, "")
        model = f", con {m.model_used}" if m.model_used else ""
        if "pensar" in m.modes_used:
            model += " y «pensar»" if model else ", con «pensar»"
        unit = "mensaje" if m.seat.kind == "web" else "llamada"
        parts.append(f"{m.seat.label} ({m.role['name']}{model}{state}): {m.messages} {unit}{'s' if m.messages != 1 else ''}")
    if parts:
        out.append("Participaron: " + "; ".join(parts) + ".")
    if result.fusion_by:
        out.append(f"Documento de fusión: {result.fusion_by.label}.")
    if result.vault_path:
        out.append(f"Guardado en tu memoria: Comités/{result.vault_path.name}, con el anexo de cada veredicto.")
    return out


def stop_committee(gw: "Gateway", run_id: str) -> bool:
    """"Parar": nothing more is sent, and the chat that is writing is told to stop."""
    stop = gw.committees.get(run_id)
    if stop is None:
        return False
    stop.set()
    gw.bridge.stop(run_id)
    for site, (_, tag) in list(gw.bridge.jobs.items()):
        if tag == run_id:
            gw.bridge.cancel(site, tag=run_id)
    return True


__all__ = ["handle", "model_entry", "plan_for", "readiness", "stop_committee"]
