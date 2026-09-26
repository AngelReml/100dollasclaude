"""Chain engine ("Mesa de IAs"): several AI steps where later steps use earlier answers.

A flow is a list of steps. Each step sends one message to one or more AIs.
The message is a template: ``{{pregunta}}`` inserts an input, ``{{paso}}`` or
``{{paso.respuesta}}`` inserts the answer(s) of step ``paso`` and
``{{paso.qwen}}`` the answer of one AI in that step. Substitution is a single
pass: text coming from an input or an answer is never re-read as a template.

- Steps run as soon as the steps they use are done, so independent steps run
  in parallel. Calls to the same upstream (same model-id prefix) never overlap.
- Every call goes through the existing account protection: the bridge guards
  the Chrome chats, the broadcaster guard the OmniRoute cookie providers.
- When an AI fails, the step's ``on_error`` decides: ``stop`` (default),
  ``wait`` (retry once after ``wait_s`` if the failure is temporary, never after
  an account limit or a verification) or ``fallback`` (ask the step's
  ``fallback`` AIs instead). A step with no answer at all stops the flow;
  a step where only some AIs answered lets it continue.
- Answers are untrusted text: they are only inserted into later messages,
  never executed.
- Every call is written to data/runs/<run_id>/journal.jsonl as it finishes
  (hash chain, see journal.py), with the exact message and answer in files, so
  :func:`broadcaster.verify_run` checks a flow run like any other run.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from . import journal
from .broadcaster import (
    GatewayError, Outcome, TargetError, _run_target, _safe, check_gateway, new_run_id,
    resolve_targets, upstream_key, verify_run,
)
from .client import CANCELLED, CONNECTION_ERROR, TIMEOUT, ChatResult
from .config import AppConfig, ProviderConfig
from .guard import Guard

ON_ERROR = ("stop", "wait", "fallback")
MAX_STEPS = 40
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)(?:\.([A-Za-z0-9_\-]+))?\s*\}\}")
STEP_ID = re.compile(r"^[A-Za-z0-9_]{1,40}$")
RETRYABLE_HTTP = (502, 503, 504)

# Step / flow states.
OK = "ok"
PARTIAL = "partial"
FAILED = "failed"
SKIPPED = "skipped"
STOPPED = "stopped"

Emit = Callable[[dict[str, Any]], "Awaitable[None] | None"]


class FlowError(ValueError):
    """The flow definition is not valid (message in Spanish, shown to Iván)."""


@dataclass(frozen=True)
class Step:
    id: str
    to: tuple[str, ...]
    message: str
    title: str = ""
    on_error: str = "stop"
    fallback: tuple[str, ...] = ()
    wait_s: float = 60.0
    after: tuple[str, ...] = ()


@dataclass(frozen=True)
class Flow:
    name: str
    steps: tuple[Step, ...]
    inputs: dict[str, str] = field(default_factory=dict)
    template: str = ""


@dataclass
class Answer:
    target: str               # the AI the step asked
    provider: str             # the AI that answered (differs after a fallback)
    ok: bool
    text: str = ""
    seconds: float = 0.0
    error: str = ""
    code: str = ""            # machine-readable reason when not ok (see error_code)
    notices: list[str] = field(default_factory=list)
    model: str = ""           # the model that answered, as its gateway reported it
    # A chat site (PLAN-v5 F4): what was really used on its page (model, modes, files with their sha256)
    # and what it produced (downloads saved in data/descargas/, or links).
    used: dict[str, Any] = field(default_factory=dict)
    downloads: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StepResult:
    status: str = SKIPPED
    message: str = ""
    answers: dict[str, Answer] = field(default_factory=dict)


@dataclass
class FlowRun:
    run_id: str
    run_dir: Path
    status: str
    steps: dict[str, StepResult]
    verified: bool


# --------------------------------------------------------------- definition

def _as_names(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def flow_from_dict(data: dict[str, Any]) -> Flow:
    """Build a Flow from its JSON form (see Flow / Step for the keys)."""
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
        raise FlowError("La cadena necesita una lista de pasos ('steps').")
    steps = []
    for n, s in enumerate(data["steps"], start=1):
        if not isinstance(s, dict):
            raise FlowError(f"El paso {n} no es válido.")
        steps.append(Step(
            id=str(s.get("id") or f"paso{n}"),
            to=_as_names(s.get("to")),
            message=str(s.get("message", "")),
            title=str(s.get("title", "")),
            on_error=str(s.get("on_error", "stop")),
            fallback=_as_names(s.get("fallback")),
            wait_s=float(s.get("wait_s", 60.0)),
            after=_as_names(s.get("after")),
        ))
    inputs = data.get("inputs") or {}
    if not isinstance(inputs, dict):
        raise FlowError("'inputs' tiene que ser una lista de nombre: texto.")
    return Flow(name=str(data.get("name") or "Cadena"), steps=tuple(steps),
                inputs={str(k): str(v) for k, v in inputs.items()}, template=str(data.get("template", "")))


def flow_to_dict(flow: Flow) -> dict[str, Any]:
    return {
        "name": flow.name,
        "template": flow.template,
        "inputs": dict(flow.inputs),
        "steps": [{"id": s.id, "title": s.title, "to": list(s.to), "message": s.message,
                   "on_error": s.on_error, "fallback": list(s.fallback), "wait_s": s.wait_s,
                   "after": list(s.after)} for s in flow.steps],
    }


def load_flow(path: Path) -> Flow:
    try:
        return flow_from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowError(f"No puedo leer la cadena {path}: {exc}") from exc


def dependencies(step: Step, step_ids: set[str]) -> list[str]:
    """Steps this step waits for: the ones its message uses, plus ``after``."""
    deps = [m.group(1) for m in PLACEHOLDER.finditer(step.message) if m.group(1) in step_ids]
    return list(dict.fromkeys([*deps, *step.after]))


def validate(cfg: AppConfig, flow: Flow) -> dict[str, list[ProviderConfig]]:
    """Check the flow; return every target and fallback name mapped to its provider(s)."""
    if not flow.steps:
        raise FlowError("La cadena no tiene pasos.")
    if len(flow.steps) > MAX_STEPS:
        raise FlowError(f"La cadena tiene {len(flow.steps)} pasos; el máximo es {MAX_STEPS}.")
    ids = [s.id for s in flow.steps]
    for sid in ids:
        if not STEP_ID.match(sid):
            raise FlowError(f"El nombre de paso «{sid}» solo puede llevar letras, números y _.")
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise FlowError(f"Hay dos pasos con el mismo nombre: {', '.join(sorted(dup))}.")
    clash = set(ids) & set(flow.inputs)
    if clash:
        raise FlowError(f"«{', '.join(sorted(clash))}» es a la vez un paso y un dato de entrada.")
    step_ids = set(ids)
    by_id = {s.id: s for s in flow.steps}
    resolved: dict[str, list[ProviderConfig]] = {}

    def resolve(name: str) -> None:
        if name.strip().lower() in ("todas", "todos", "all"):
            raise FlowError("En una cadena, nombra cada IA; «todas» no vale como destinatario.")
        if name not in resolved:
            try:
                resolved[name] = resolve_targets(cfg, name)
            except TargetError as exc:
                raise FlowError(str(exc)) from exc

    for s in flow.steps:
        label = s.title or s.id
        if not s.to:
            raise FlowError(f"El paso «{label}» no dice a qué IA va.")
        if len(set(s.to)) != len(s.to):
            raise FlowError(f"El paso «{label}» repite una IA.")
        if not s.message.strip():
            raise FlowError(f"El paso «{label}» no tiene mensaje.")
        if s.on_error not in ON_ERROR:
            raise FlowError(f"El paso «{label}»: «si falla» tiene que ser {', '.join(ON_ERROR)}.")
        if s.wait_s < 0 or s.wait_s > 3600:
            raise FlowError(f"El paso «{label}»: la espera tiene que estar entre 0 y 3600 s.")
        for name in (*s.to, *s.fallback):
            resolve(name)
        for m in PLACEHOLDER.finditer(s.message):
            ref, part = m.group(1), m.group(2)
            if ref in step_ids:
                if ref == s.id:
                    raise FlowError(f"El paso «{label}» no puede usar su propia respuesta.")
                if part not in (None, "respuesta") and part not in by_id[ref].to:
                    raise FlowError(f"El paso «{label}» usa {m.group(0)}, pero «{ref}» no pregunta a «{part}».")
            elif ref in flow.inputs:
                if part is not None:
                    raise FlowError(f"El paso «{label}» usa {m.group(0)}: un dato de entrada no tiene partes.")
            else:
                raise FlowError(f"El paso «{label}» usa {m.group(0)}, que no es ningún paso ni dato de entrada.")
        for dep in s.after:
            if dep not in step_ids or dep == s.id:
                raise FlowError(f"El paso «{label}» espera a «{dep}», que no existe.")
    _check_acyclic(flow, step_ids)
    return resolved


def _check_acyclic(flow: Flow, step_ids: set[str]) -> None:
    deps = {s.id: dependencies(s, step_ids) for s in flow.steps}
    state: dict[str, int] = {}

    def visit(sid: str, path: list[str]) -> None:
        if state.get(sid) == 2:
            return
        if state.get(sid) == 1:
            loop = " → ".join([*path[path.index(sid):], sid])
            raise FlowError(f"La cadena da vueltas sin fin: {loop}.")
        state[sid] = 1
        for d in deps[sid]:
            visit(d, [*path, sid])
        state[sid] = 2

    for sid in deps:
        visit(sid, [])


def estimate_messages(cfg: AppConfig, flow: Flow) -> dict[str, dict[str, int]]:
    """Messages each AI will receive: ``normal`` run and ``worst`` case (retries, fallbacks)."""
    validate(cfg, flow)
    normal: dict[str, int] = {}
    worst: dict[str, int] = {}
    for s in flow.steps:
        for name in s.to:
            normal[name] = normal.get(name, 0) + 1
            worst[name] = worst.get(name, 0) + (2 if s.on_error == "wait" else 1)
        if s.on_error == "fallback":
            for name in s.fallback:
                worst[name] = worst.get(name, 0) + len(s.to)
    return {"normal": normal, "worst": worst}


# ---------------------------------------------------------------- rendering

def _label(cfg: AppConfig, name: str) -> str:
    p = cfg.providers.get(name)
    return p.display if p else name


def combined_answer(cfg: AppConfig, result: StepResult) -> str:
    """All answers of a step, one block per AI (the text itself for a single AI)."""
    if len(result.answers) == 1:
        (a,) = result.answers.values()
        return a.text if a.ok else f"({_label(cfg, a.target)} no respondió)"
    blocks = []
    for a in result.answers.values():
        who = _label(cfg, a.provider)
        if a.provider != a.target:
            who += f" (en lugar de {_label(cfg, a.target)})"
        blocks.append(f"### {who}\n\n{a.text if a.ok else '(no respondió)'}")
    return "\n\n".join(blocks)


def render_message(cfg: AppConfig, template: str, inputs: dict[str, str], results: dict[str, StepResult]) -> str:
    def sub(m: re.Match) -> str:
        ref, part = m.group(1), m.group(2)
        if ref in results:
            res = results[ref]
            if part in (None, "respuesta"):
                return combined_answer(cfg, res)
            a = res.answers.get(part)
            if a is None or not a.ok:
                return f"({_label(cfg, part)} no respondió)"
            return a.text
        return inputs[ref]

    return PLACEHOLDER.sub(sub, template)


# ---------------------------------------------------------------- execution

def _retryable(outcome: Outcome) -> bool:
    r = outcome.result
    if r.status in (TIMEOUT, CONNECTION_ERROR):
        return True
    return r.http_status in RETRYABLE_HTTP


async def _emit(emit: Emit | None, event: dict[str, Any]) -> None:
    if emit is None:
        return
    res = emit(event)
    if inspect.isawaitable(res):
        await res


async def run_flow(
    cfg: AppConfig,
    flow: Flow,
    *,
    api_key: str,
    guard: Guard,
    bridge_key: str | None = None,
    emit: Emit | None = None,
    run_id: str | None = None,
    timeout_s: float | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    transport: httpx.AsyncBaseTransport | None = None,
    stop: asyncio.Event | None = None,
    bridge_extra: dict[str, Any] | None = None,
) -> FlowRun:
    """Run ``flow`` and return every step's result; raise FlowError / GatewayError before sending anything.

    ``stop`` is Iván's "parar": once set, a call in progress ends as "cancelled" at once (whoever sets it also
    tells the bridge, so a chat's job in Chrome stops too), nothing more is sent (no retry, no stand-in, no
    later step), and the run still closes its journal.
    ``bridge_extra`` goes to the chat sites asked (PLAN-v5 F4): {"model", "modes", "files"}."""
    stopping = stop.is_set if stop is not None else (lambda: False)
    resolved = validate(cfg, flow)
    run_id = run_id or new_run_id()
    run_dir = cfg.paths.runs_dir / run_id
    step_ids = {s.id for s in flow.steps}
    deps = {s.id: dependencies(s, step_ids) for s in flow.steps}
    results = {s.id: StepResult() for s in flow.steps}
    done = {s.id: asyncio.Event() for s in flow.steps}
    locks: dict[str, asyncio.Lock] = {}
    stopped = False
    counter = 0

    def log_call(step: Step, message_file: str, message_sha: str, outcome: Outcome, attempt: str,
                 target: str) -> Answer:
        nonlocal counter
        counter += 1
        return journal_call(run_dir, run_id, counter, step.id, message_file, message_sha, outcome, attempt, target)

    async with httpx.AsyncClient(transport=transport) as client:
        if any(p.gateway == "omniroute" for ps in resolved.values() for p in ps):
            await check_gateway(client, cfg.base_url, api_key)  # before anything is written or sent
        (run_dir / "messages").mkdir(parents=True, exist_ok=True)
        (run_dir / "responses").mkdir(parents=True, exist_ok=True)
        (run_dir / "flow.json").write_text(json.dumps(flow_to_dict(flow), indent=2, ensure_ascii=False),
                                           encoding="utf-8")
        await _emit(emit, {"type": "flow_start", "run_id": run_id, "name": flow.name, "template": flow.template,
                           "steps": [{"id": s.id, "title": s.title or s.id, "to": list(s.to),
                                      "labels": [_label(cfg, n) for n in s.to]} for s in flow.steps],
                           "estimate": estimate_messages(cfg, flow)})

        async def call(step: Step, provider: ProviderConfig, message: str, target: str) -> Outcome:
            lock = locks.setdefault(upstream_key(provider.model), asyncio.Lock())
            async with lock:
                if stopping():  # stopped while it was queued: never sent
                    return Outcome(target=provider, result=ChatResult(status=CANCELLED, error="lo has parado tú"))
                # Started only now: until here it was queued behind another call to the same place
                # (the app shows "En cola", not a clock that runs before anything was sent).
                await _emit(emit, {"type": "target_start", "step": step.id, "target": target,
                                   "label": _label(cfg, target), "provider": provider.name})
                work = asyncio.ensure_future(_run_target(
                    provider, prompt=message, client=client, cfg=cfg, api_key=api_key, guard=guard,
                    timeout_s=timeout_s, notify=lambda _m: None,  # guard waits show as "esperando"
                    bridge_key=bridge_key, run_tag=run_id, bridge_extra=bridge_extra))
                if stop is None:
                    return await work
                t0 = asyncio.get_running_loop().time()
                stopper = asyncio.ensure_future(stop.wait())
                try:
                    await asyncio.wait({work, stopper}, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    stopper.cancel()
                if work.done():
                    return work.result()
                work.cancel()
                await asyncio.gather(work, return_exceptions=True)
                return Outcome(target=provider, result=ChatResult(
                    status=CANCELLED, error="lo has parado tú", latency_s=asyncio.get_running_loop().time() - t0))

        async def ask(step: Step, target: str, message: str, message_file: str, message_sha: str) -> Answer:
            provider = resolved[target][0]
            outcome = await call(step, provider, message, target)
            answer = log_call(step, message_file, message_sha, outcome, "first", target)
            if not answer.ok and step.on_error == "wait" and _retryable(outcome) and not stopping():
                await _emit(emit, {"type": "target_wait", "step": step.id, "target": target,
                                   "label": _label(cfg, target), "seconds": step.wait_s, "error": answer.error})
                await sleep(step.wait_s)
                outcome = await call(step, provider, message, target)
                answer = log_call(step, message_file, message_sha, outcome, "retry", target)
            if not answer.ok and step.on_error == "fallback" and not stopping():
                for alt in step.fallback:
                    if alt in step.to or stopping():
                        continue
                    await _emit(emit, {"type": "target_fallback", "step": step.id, "target": target,
                                       "label": _label(cfg, target), "provider": alt,
                                       "provider_label": _label(cfg, alt), "error": answer.error})
                    outcome = await call(step, resolved[alt][0], message, target)
                    alt_answer = log_call(step, message_file, message_sha, outcome, "fallback", target)
                    if alt_answer.ok:
                        answer = alt_answer
                        break
            await _emit(emit, {"type": "target_done", "step": step.id, "target": target,
                               "label": _label(cfg, target), "provider": answer.provider,
                               "provider_label": _label(cfg, answer.provider), "ok": answer.ok,
                               "text": answer.text, "seconds": answer.seconds, "error": answer.error,
                               "code": answer.code, "notices": answer.notices, "model": answer.model,
                               "used": answer.used, "downloads": answer.downloads})
            return answer

        async def run_step(step: Step) -> None:
            nonlocal stopped
            try:
                for d in deps[step.id]:
                    await done[d].wait()
                res = results[step.id]
                if stopped or stopping() or any(results[d].status in (FAILED, SKIPPED) for d in deps[step.id]):
                    res.status = SKIPPED
                    await _emit(emit, {"type": "step_done", "step": step.id, "status": SKIPPED})
                    return
                message = render_message(cfg, step.message, flow.inputs, results)
                res.message = message
                message_file = f"messages/{_safe(step.id)}.md"
                (run_dir / message_file).write_text(message, encoding="utf-8", newline="")
                message_sha = journal.sha256_text(message)
                await _emit(emit, {"type": "step_start", "step": step.id, "title": step.title or step.id,
                                   "message": message})
                answers = await asyncio.gather(*(ask(step, t, message, message_file, message_sha) for t in step.to))
                res.answers = {a.target: a for a in answers}
                good = sum(a.ok for a in answers)
                res.status = OK if good == len(answers) else PARTIAL if good else FAILED
                if res.status == FAILED:
                    stopped = True
                await _emit(emit, {"type": "step_done", "step": step.id, "status": res.status})
            finally:
                done[step.id].set()

        await asyncio.gather(*(run_step(s) for s in flow.steps))

    statuses = [r.status for r in results.values()]
    status = STOPPED if (FAILED in statuses or SKIPPED in statuses) else PARTIAL if PARTIAL in statuses else OK
    verified = close_run(run_dir, run_id, flow.name, status, {sid: r.status for sid, r in results.items()})
    await _emit(emit, {"type": "flow_done", "run_id": run_id, "status": status, "verified": verified,
                       "steps": {sid: r.status for sid, r in results.items()}})
    return FlowRun(run_id=run_id, run_dir=run_dir, status=status, steps=results, verified=verified)


def journal_call(run_dir: Path, run_id: str, counter: int, step_id: str, message_file: str, message_sha: str,
                 outcome: Outcome, attempt: str, target: str, extra: dict[str, Any] | None = None) -> Answer:
    """Write one call's answer file and journal line; used by run_flow and by the gateway's direct calls."""
    r = outcome.result
    resp_file = None
    if r.ok:
        resp_file = f"responses/{counter:02d}-{_safe(step_id)}-{_safe(outcome.target.name)}.md"
        (run_dir / resp_file).write_text(r.text, encoding="utf-8", newline="")
    journal.append(run_dir / journal.JOURNAL_NAME, {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "run_id": run_id,
        "kind": "flow",
        "step": step_id,
        "attempt": attempt,
        "target": target,
        "provider": outcome.target.name,
        "model": r.model or outcome.target.model,
        "requested_models": outcome.tried_models or [outcome.target.model],
        "upstream": r.upstream_provider,
        "prompt_sha256": message_sha,
        "message_file": message_file,
        "response_sha256": journal.sha256_text(r.text) if r.ok else None,
        "response_file": resp_file,
        "status": r.status,
        "http_status": r.http_status,
        "latency_s": round(r.latency_s, 3),
        "error": r.error,
        "code": error_code(r),
        "notices": outcome.notices,
        # what the chat's page really used and produced (the files by their sha256, never their content)
        **({"used": used} if (used := (r.webllm or {}).get("used")) else {}),
        **({"downloads": made} if (made := (r.webllm or {}).get("downloads")) else {}),
        **(extra or {}),
    })
    return Answer(target=target, provider=outcome.target.name, ok=r.ok, text=r.text if r.ok else "",
                  seconds=round(r.latency_s, 1), error=_error_text(r), code=error_code(r),
                  notices=list(outcome.notices), model=r.model or outcome.target.model,
                  used=dict((r.webllm or {}).get("used") or {}), downloads=list((r.webllm or {}).get("downloads") or []))


def close_run(run_dir: Path, run_id: str, name: str, status: str, steps: dict[str, str]) -> bool:
    """The run's last journal line and its manifest (against truncation); True when it verifies."""
    jpath = run_dir / journal.JOURNAL_NAME
    last = journal.append(jpath, {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "run_id": run_id, "kind": "flow_end", "name": name, "status": status, "steps": steps,
    })
    lines = sum(1 for x in jpath.read_text(encoding="utf-8").splitlines() if x.strip())
    (run_dir / "run.json").write_text(json.dumps({"run_id": run_id, "kind": "flow", "lines": lines,
                                                  "last_hash": last["hash"]}, indent=2), encoding="utf-8")
    return verify_run(run_dir).ok


def start_run(run_dir: Path, flow: Flow, step: Step, message: str) -> tuple[str, str]:
    """For a call made outside run_flow: the run's folders, flow.json and the message; (file, sha256)."""
    (run_dir / "messages").mkdir(parents=True, exist_ok=True)
    (run_dir / "responses").mkdir(parents=True, exist_ok=True)
    (run_dir / "flow.json").write_text(json.dumps(flow_to_dict(flow), indent=2, ensure_ascii=False), encoding="utf-8")
    message_file = f"messages/{_safe(step.id)}.md"
    (run_dir / message_file).write_text(message, encoding="utf-8", newline="")
    return message_file, journal.sha256_text(message)


def error_code(r: ChatResult) -> str:
    """Why a call failed, as a short code the app turns into "what happened + what to do + button".

    Chrome chats: the bridge's own code (login_required, paused, site_busy, bridge_unavailable, ...).
    Skipped by the guard: cooldown, daily_cap, busy. API AIs: rate_limited, unauthorized, overloaded,
    timeout, unreachable (OmniRoute off), malformed. Anything else: error.
    """
    if r.ok:
        return ""
    if r.status == "skipped":
        return r.error or "cooldown"
    if r.status == CANCELLED:
        return "cancelled"
    code: Any = None
    message = ""
    try:
        err = json.loads(r.body_excerpt or "")["error"]
        if isinstance(err, dict):
            code, message = err.get("code"), str(err.get("message") or "")
    except (ValueError, KeyError, TypeError):
        pass
    # Only webllm's own codes pass through; a provider's code is its own vocabulary (OpenRouter
    # sends the HTTP number, z.ai its own numbers) and is read like the HTTP status instead.
    if isinstance(code, str) and code in OWN_ERROR_CODES:
        return code
    number = int(code) if isinstance(code, int) or (isinstance(code, str) and code.isdigit()) else None
    status = number if number and 100 <= number <= 599 else r.http_status
    if r.status == TIMEOUT or status == 504:
        return "timeout"
    if r.status == CONNECTION_ERROR:
        return "unreachable"
    # "no credit" = money, not a pace limit: a 429 whose message also mentions credits
    # ("Rate limit exceeded: free-models-per-day. Add 10 credits...") is still a limit.
    if status == 402 or _CREDIT_TEXT.search(str(code or "")) or (status != 429 and _CREDIT_TEXT.search(message)):
        return "no_credit"
    if status == 429 or _RATE_TEXT.search(f"{code or ''} {message}"):
        return "rate_limited"
    if status in (401, 403):
        return "unauthorized"
    if status in (502, 503, 529) or _BUSY_TEXT.search(message):
        return "overloaded"
    if r.status == "malformed":
        return "malformed"
    return "error"


# Codes webllm itself puts in error.code (bridge, extension, app API): the app has a message for each.
OWN_ERROR_CODES = frozenset({
    "login_required", "banned", "rate_limited", "challenge", "timeout", "extension_disconnected",
    "site_busy", "not_sent", "paused", "bridge_unavailable", "unknown_site", "model_not_found",
    "empty_prompt", "no_input", "insert_failed", "send_failed", "empty_answer", "extension_error",
    "unauthorized", "unreachable", "cancelled",
    # PLAN-v5 F4: what Iván chose could not be put or confirmed on the page, so nothing was sent
    "not_confirmed", "model_not_in_page", "mode_not_in_page", "file_not_attached", "forbidden", "expensive_cap",
})
# Whole words: a "load balancer" is not a balance, and "insufficient context" is not money.
_CREDIT_TEXT = re.compile(r"insufficient[ _-]?(balance|credits?|funds|quota)|\bcredits?\b|\bbalance\b", re.I)
_RATE_TEXT = re.compile(r"rate.?limit|too many requests|quota|concurren", re.I)
_BUSY_TEXT = re.compile(r"overloaded|at capacity|temporarily unavailable", re.I)


def _error_text(r: ChatResult) -> str:
    """Short Spanish-ready error: the bridge's own message when there is one."""
    if r.ok:
        return ""
    try:
        err = json.loads(r.body_excerpt or "")["error"]
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str):
            return err
    except (ValueError, KeyError, TypeError):
        pass
    return r.error or r.status


# ---------------------------------------------------------------- templates

def _judge_fallback(cfg: AppConfig, judge: str, avoid: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Other API AIs that can stand in for an API judge / integrator (outsiders first)."""
    spare = [p.name for p in cfg.enabled_providers if p.kind == "api" and p.name != judge]
    return tuple(sorted(spare, key=lambda name: name in avoid))


def council_and_judge(cfg: AppConfig, question: str, council: list[str], judge: str) -> Flow:
    """Consejo + juez: the same question to several AIs, another compares and writes the best answer."""
    return Flow(
        name="Consejo + juez", template="consejo", inputs={"pregunta": question},
        steps=(
            Step(id="consejo", title="El consejo responde", to=tuple(council), message="{{pregunta}}",
                 on_error="wait"),
            Step(id="juez", title="El juez compara", to=(judge,), on_error="fallback",
                 fallback=_judge_fallback(cfg, judge, tuple(council)), message=(
                     "Varias IAs han respondido a la misma pregunta. Haz de juez.\n\n"
                     "PREGUNTA:\n{{pregunta}}\n\nRESPUESTAS:\n{{consejo.respuesta}}\n\n"
                     "1. Di en qué coinciden.\n"
                     "2. Di en qué no coinciden y quién tiene más razón en cada punto, y por qué.\n"
                     "3. Escribe la mejor respuesta final, completa, con lo bueno de cada una.\n"
                     "Responde en español.")),
        ),
    )


def split_and_merge(cfg: AppConfig, goal: str, parts: list[tuple[str, str]], merger: str) -> Flow:
    """Reparto + integración: a different task to each AI, another joins everything in one report."""
    inputs = {"objetivo": goal}
    steps = []
    merge_blocks = []
    for n, (ai, task) in enumerate(parts, start=1):
        inputs[f"encargo_{n}"] = task
        steps.append(Step(id=f"parte_{n}", title=f"Parte de {_label(cfg, ai)}", to=(ai,), on_error="wait",
                          message="Objetivo general: {{objetivo}}\n\nTu parte: {{encargo_%d}}" % n))
        merge_blocks.append(f"PARTE DE {_label(cfg, ai).upper()} ({{{{encargo_{n}}}}}):\n{{{{parte_{n}.respuesta}}}}")
    steps.append(Step(id="integracion", title="Se une todo", to=(merger,), on_error="fallback",
                      fallback=_judge_fallback(cfg, merger, tuple(ai for ai, _ in parts)), message=(
                          "Varias IAs han hecho cada una una parte de un trabajo. Únelas en un solo informe "
                          "claro y ordenado.\n\nOBJETIVO:\n{{objetivo}}\n\n" + "\n\n".join(merge_blocks) +
                          "\n\nEscribe el informe final sin repetir cosas y señala las contradicciones si las hay. "
                          "Responde en español.")))
    return Flow(name="Reparto + integración", template="reparto", inputs=inputs, steps=tuple(steps))


def debate(cfg: AppConfig, question: str, a: str, b: str, rounds: int = 1) -> Flow:
    """Debate: A answers, B looks for flaws, A corrects; ``rounds`` times."""
    if not 1 <= rounds <= 5:
        raise FlowError("El debate tiene que tener entre 1 y 5 vueltas.")
    la, lb = _label(cfg, a), _label(cfg, b)
    steps = [Step(id="a1", title=f"{la} responde", to=(a,), on_error="wait", message="{{pregunta}}")]
    for k in range(1, rounds + 1):
        steps.append(Step(id=f"b{k}", title=f"{lb} busca fallos (vuelta {k})", to=(b,), on_error="wait", message=(
            "Otra IA ha respondido a esta pregunta. Búscale fallos: errores, cosas que faltan y puntos débiles. "
            "Sé concreto.\n\nPREGUNTA:\n{{pregunta}}\n\nRESPUESTA:\n{{a%d.respuesta}}" % k)))
        steps.append(Step(id=f"a{k + 1}", title=f"{la} corrige (vuelta {k})", to=(a,), on_error="wait", message=(
            "Respondiste a esta pregunta y otra IA ha criticado tu respuesta. Acepta las críticas que tengan "
            "razón, rebate las que no y da la respuesta mejorada completa.\n\nPREGUNTA:\n{{pregunta}}\n\n"
            "TU RESPUESTA:\n{{a%d.respuesta}}\n\nCRÍTICA:\n{{b%d.respuesta}}" % (k, k))))
    return Flow(name="Debate", template="debate", inputs={"pregunta": question}, steps=tuple(steps))


def chain(cfg: AppConfig, start: str, links: list[tuple[str, str]]) -> Flow:
    """Cadena: what A says goes into B, what B says goes into C (for example idea → plan → review)."""
    if not links:
        raise FlowError("La cadena necesita al menos un eslabón.")
    inputs = {"entrada": start}
    steps = []
    for n, (ai, instruction) in enumerate(links, start=1):
        inputs[f"instruccion_{n}"] = instruction
        source = "{{entrada}}" if n == 1 else "{{eslabon_%d.respuesta}}" % (n - 1)
        steps.append(Step(id=f"eslabon_{n}", title=f"{n}. {_label(cfg, ai)}", to=(ai,), on_error="wait",
                          message="{{instruccion_%d}}\n\n%s" % (n, source)))
    return Flow(name="Cadena", template="cadena", inputs=inputs, steps=tuple(steps))


TEMPLATES = {
    "consejo": "Consejo + juez",
    "reparto": "Reparto + integración",
    "debate": "Debate",
    "cadena": "Cadena",
}


__all__ = [
    "Flow", "Step", "FlowRun", "StepResult", "Answer", "FlowError", "GatewayError", "flow_from_dict",
    "flow_to_dict", "load_flow", "validate", "estimate_messages", "render_message", "run_flow", "error_code",
    "council_and_judge", "split_and_merge", "debate", "chain", "TEMPLATES",
]
