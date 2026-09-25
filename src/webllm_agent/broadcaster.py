"""`webllm ask`: send one prompt to one or all providers through OmniRoute.

- Different providers run concurrently; targets that share an upstream
  (same model-id prefix) run one after another.
- Web providers go through the account guard (see guard.py).
- One failure never hides the others: every target gets its own section.
- Every run leaves data/runs/<run_id>/ with prompt.txt, one response file per
  target, a hash-chained journal.jsonl and run.json (line count + last hash,
  so a truncated journal is also detected).
"""

from __future__ import annotations

import asyncio
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

from . import journal
from .client import OK, TRANSPARENT_HEADERS, ChatResult, auth_headers, chat
from .config import AppConfig, ProviderConfig, is_blocked_model
from .guard import Guard, GuardBlocked

SKIPPED = "skipped"

STATUS_ES = {
    "ok": "OK",
    "http_error": "FALLO",
    "timeout": "TIEMPO AGOTADO",
    "malformed": "RESPUESTA ROTA",
    "connection_error": "SIN CONEXIÓN",
    SKIPPED: "SALTADO",
}


class TargetError(ValueError):
    """--to names nothing usable."""


class GatewayError(RuntimeError):
    """OmniRoute is down or rejects our key."""


@dataclass
class Outcome:
    target: ProviderConfig
    result: ChatResult
    notices: list[str] = field(default_factory=list)
    tried_models: list[str] = field(default_factory=list)


def resolve_targets(cfg: AppConfig, to: str) -> list[ProviderConfig]:
    """Map --to (todas | provider name | raw model id) to provider configs, priority order."""
    key = to.strip()
    if key.lower() in ("todas", "todos", "all"):
        targets = cfg.enabled_providers
        if not targets:
            raise TargetError("No hay ningún proveedor activado en data/config.yaml (enabled: true).")
    elif key in cfg.providers:
        targets = [cfg.providers[key]]
        if not targets[0].enabled:
            raise TargetError(f"'{key}' está desactivado en data/config.yaml (enabled: false).")
    elif "/" in key:
        if key.startswith("browser/"):
            targets = [ProviderConfig(name=key, model=key, kind="browser", gateway="bridge")]
        else:
            kind = "web" if key.startswith(cfg.web_model_prefixes) else "api"
            targets = [ProviderConfig(name=key, model=key, kind=kind)]
    else:
        names = ", ".join(["todas", *cfg.providers])
        raise TargetError(f"No conozco '{key}'. Usa uno de: {names}, o un id de modelo 'proveedor/modelo'.")
    for t in targets:
        for model in (t.model, *t.fallback_models):
            if is_blocked_model(cfg, model):
                raise TargetError(f"El modelo '{model}' está excluido de esta herramienta (Claude/ChatGPT/Codex).")
    return targets


def upstream_key(model: str) -> str:
    return model.split("/", 1)[0].lower()


def new_run_id() -> str:
    return f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


async def check_gateway(client: httpx.AsyncClient, base_url: str, api_key: str) -> None:
    """Fail fast (before touching any guarded provider) if OmniRoute is down or rejects the key."""
    try:
        r = await client.get(f"{base_url}/models", headers=auth_headers(api_key), timeout=15)
    except httpx.HTTPError as exc:
        raise GatewayError(
            f"OmniRoute no responde en {base_url} ({type(exc).__name__}). "
            "Haz doble clic en PREGUNTAR o en 2 - PROBAR TODO (lo encienden solos)."
        ) from exc
    if r.status_code in (401, 403):
        raise GatewayError("OmniRoute rechaza la clave (OMNIROUTE_API_KEY en ~/.omniroute/.env).")
    if r.status_code != 200:
        raise GatewayError(f"OmniRoute respondió HTTP {r.status_code} a /models.")


async def _run_target(
    t: ProviderConfig,
    *,
    prompt: str,
    client: httpx.AsyncClient,
    cfg: AppConfig,
    api_key: str,
    guard: Guard,
    timeout_s: float | None,
    notify: Callable[[str], None],
    bridge_key: str | None = None,
) -> Outcome:
    base_url, key = (cfg.bridge_url, bridge_key or "") if t.gateway == "bridge" else (cfg.base_url, api_key)
    permit = None
    if t.guarded:
        try:
            permit = await guard.acquire(t, notify=notify)
        except GuardBlocked as blocked:
            return Outcome(t, ChatResult(SKIPPED, model=t.model, error=blocked.reason), [blocked.message_es])
    outcome = Outcome(t, ChatResult(SKIPPED, model=t.model))
    try:
        for model in (t.model, *t.fallback_models):
            outcome.tried_models.append(model)
            res = await chat(client, base_url=base_url, api_key=key, model=model,
                             prompt=prompt, timeout_s=timeout_s or t.timeout_s)
            outcome.result = res
            if t.guarded:
                notice = guard.report(t, res)
                if notice:
                    outcome.notices.append(notice)
                    break  # never retry through a tripped web provider
            if res.ok:
                break
    finally:
        if permit is not None:
            guard.release(permit)
    if len(outcome.tried_models) > 1 and outcome.result.ok:
        outcome.notices.append(f"{t.name}: respondió el respaldo {outcome.tried_models[-1]}")
    return outcome


async def broadcast(
    cfg: AppConfig,
    prompt: str,
    targets: list[ProviderConfig],
    *,
    api_key: str,
    guard: Guard,
    timeout_s: float | None = None,
    notify: Callable[[str], None] = print,
    transport: httpx.AsyncBaseTransport | None = None,
    bridge_key: str | None = None,
) -> list[Outcome]:
    """Send ``prompt`` to every target and return outcomes in target (priority) order."""
    groups: dict[str, list[int]] = {}
    for i, t in enumerate(targets):
        groups.setdefault(upstream_key(t.model), []).append(i)
    outcomes: list[Outcome | None] = [None] * len(targets)

    async with httpx.AsyncClient(transport=transport) as client:
        if any(t.gateway == "omniroute" for t in targets):
            await check_gateway(client, cfg.base_url, api_key)

        async def run_group(indexes: list[int]) -> None:
            for i in indexes:  # sequential within one upstream
                outcomes[i] = await _run_target(targets[i], prompt=prompt, client=client, cfg=cfg,
                                                api_key=api_key, guard=guard, timeout_s=timeout_s,
                                                notify=notify, bridge_key=bridge_key)

        await asyncio.gather(*(run_group(ix) for ix in groups.values()))
    return [o for o in outcomes if o is not None]


def write_run(runs_dir: Path, run_id: str, prompt: str, outcomes: list[Outcome]) -> Path:
    """Persist prompt, responses and the chained journal for one run."""
    run_dir = runs_dir / run_id
    (run_dir / "responses").mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8", newline="")
    jpath = run_dir / journal.JOURNAL_NAME
    prompt_sha = journal.sha256_text(prompt)
    last = None
    for n, o in enumerate(outcomes, start=1):
        r = o.result
        resp_file = None
        if r.ok:
            resp_file = f"responses/{n:02d}-{_safe(o.target.name)}.md"
            (run_dir / resp_file).write_text(r.text, encoding="utf-8", newline="")
        last = journal.append(jpath, {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "run_id": run_id,
            "provider": o.target.name,
            "model": r.model or o.target.model,
            "requested_models": o.tried_models or [o.target.model],
            "upstream": r.upstream_provider,
            "prompt_sha256": prompt_sha,
            "response_sha256": journal.sha256_text(r.text) if r.ok else None,
            "response_file": resp_file,
            "status": r.status,
            "http_status": r.http_status,
            "latency_s": round(r.latency_s, 3),
            "error": r.error,
            "notices": o.notices,
        })
    manifest = {"run_id": run_id, "lines": len(outcomes), "last_hash": last["hash"] if last else journal.GENESIS}
    (run_dir / "run.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return run_dir


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)[:60]


def verify_run(run_dir: Path) -> journal.VerifyResult:
    """Chain check + manifest (truncation) + response files match their hashes."""
    jpath = run_dir / journal.JOURNAL_NAME
    if not jpath.exists():
        return journal.VerifyResult(False, 0, None, "journal.jsonl not found")
    res = journal.verify(jpath)
    if not res.ok:
        return res
    lines = [json.loads(x) for x in jpath.read_text(encoding="utf-8").splitlines() if x.strip()]
    manifest_path = run_dir / "run.json"
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        if m.get("lines") != len(lines) or m.get("last_hash") != (lines[-1]["hash"] if lines else journal.GENESIS):
            return journal.VerifyResult(False, len(lines), min(len(lines), int(m.get("lines", 0))) + 1,
                                        "journal does not match run.json (lines removed or appended)")
    for n, line in enumerate(lines, start=1):
        if line.get("response_file"):
            f = run_dir / line["response_file"]
            if not f.exists() or journal.sha256_text(f.read_bytes().decode("utf-8")) != line["response_sha256"]:
                return journal.VerifyResult(False, len(lines), n, f"{line['response_file']} does not match response_sha256")
    return res


def render(outcomes: list[Outcome], run_id: str | None = None) -> str:
    """Plain-text report: one headed section per target, in priority order."""
    out: list[str] = []
    total = len(outcomes)
    for n, o in enumerate(outcomes, start=1):
        r = o.result
        status = STATUS_ES.get(r.status, r.status.upper())
        if r.http_status and r.status != OK:
            status += f" (HTTP {r.http_status})"
        head = f" {n}/{total} · {o.target.name} · {r.model or o.target.model} · {status} · {r.latency_s:.2f} s "
        out.append("═" * 3 + head + "═" * max(3, 76 - len(head)))
        if r.ok:
            out.append(r.text.rstrip())
        elif r.error:
            out.append(f"[{r.error}]")
            if r.body_excerpt:
                out.append(f"[respuesta: {r.body_excerpt[:200]}]")
        for notice in o.notices:
            out.append(f">> {notice}")
        out.append("")
    ok = sum(o.result.ok for o in outcomes)
    out.append(f"Resumen: {ok}/{total} respondieron." + (f"  Registro: data/runs/{run_id}/" if run_id else ""))
    return "\n".join(out)


__all__ = [
    "Outcome", "TargetError", "GatewayError", "resolve_targets", "broadcast", "write_run",
    "verify_run", "render", "new_run_id", "TRANSPARENT_HEADERS",
]
