"""Webs that repair themselves (PLAN-v5 D17, F6), layer 3: when a chat page changes and webllm cannot find its
text box or read its answer, an AI by API looks at the page's x-ray and points at the right element.

- The x-ray (driver.js ``xray``) is numbered candidates with what the SITE wrote on them: tags, classes, short
  labels of its controls, sizes and positions. Never the text of the conversation (an answer is only its length,
  plus "this is / comes after your message"), never a password field, never what was typed.
- The AI answers with candidate NUMBERS only, in JSON. Anything else (code, selectors, prose, numbers out of
  range, a button where a text box is asked) is rejected: nothing an AI writes is ever run or used as a selector.
  The selectors come from the page itself (the x-ray's own ``sel`` / ``general``), which the AI never sees.
- The chosen elements are tried on the page as it is, sending nothing (driver.js ``tryPatch``); only then are
  they kept as a patch of that site, dated and marked "by an AI", which Iván can undo in the site's card.
- Which AI helps, and whether this happens at all, is Iván's setting (``data/state/reparar.json``); every
  repair, kept or not, is written to ``data/state/reparaciones.jsonl``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import AppConfig, Paths, ProviderConfig

SETTINGS = "reparar.json"
LOG = "reparaciones.jsonl"
# What can be repaired, the kind of candidate each needs, and what it is, for the AI.
ROLES: dict[str, tuple[str, str]] = {
    "input": ("box", "the text box where the user types the message to the AI"),
    "send": ("button", "the button that sends the typed message"),
    "answer": ("block", "the AI's last answer: a whole message written by the AI, after the user's message "
                        "(never the user's own message, never a toolbar)"),
    "copy": ("button", "the button that copies the AI's last answer"),
}
# Preferred helpers, strongest first among the free API ones; any other private API/local AI is a fallback.
PREFERRED = ("zai", "groq", "nemotron")
SYSTEM = (
    "You help a browser extension find elements on a chat web page that changed its design. You get a numbered "
    "list of candidate elements (only their tags, classes, short labels of controls, sizes and positions; the "
    "conversation's text is not included). For each asked role, answer with the NUMBER of the candidate that is "
    "that element, or null if none is. Answer ONLY with one JSON object like {\"input\": 3}, no code, no "
    "selectors, no explanation."
)


class Rejected(ValueError):
    """The AI's answer is not a list of candidate numbers for the asked roles: nothing of it is used."""


def settings(paths: "Paths") -> dict[str, Any]:
    try:
        data = json.loads((paths.state_dir / SETTINGS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {"enabled": bool(data.get("enabled", True)), "ai": str(data.get("ai") or "")}


def configure(paths: "Paths", enabled: bool, ai: str = "") -> dict[str, Any]:
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    (paths.state_dir / SETTINGS).write_text(json.dumps({"enabled": bool(enabled), "ai": ai}), encoding="utf-8")
    return settings(paths)


def helpers(cfg: "AppConfig") -> list["ProviderConfig"]:
    """The AIs that may look at an x-ray: by API or on this PC (never a web chat: it would spend a message and
    wait its turn), private, and not a blocked one."""
    from .config import is_blocked_model
    ok = [p for p in cfg.providers.values()
          if p.gateway in ("omniroute", "local") and p.private and not is_blocked_model(cfg, p.model)]
    order = {name: i for i, name in enumerate(PREFERRED)}
    return sorted(ok, key=lambda p: (p.gateway == "local", order.get(p.name, len(order)), p.name))


def helper(cfg: "AppConfig") -> "ProviderConfig | None":
    chosen = settings(cfg.paths)["ai"]
    options = helpers(cfg)
    return next((p for p in options if p.name == chosen), None) or (options[0] if options else None)


def for_ai(xray: dict[str, Any]) -> list[dict[str, Any]]:
    """The candidates as the AI sees them: without webllm's own selectors (the AI answers with numbers)."""
    out = []
    for c in (xray or {}).get("candidates") or []:
        if isinstance(c, dict):
            out.append({k: v for k, v in c.items() if k not in ("sel", "general") and v not in (None, "")})
    return out


def prompt(xray: dict[str, Any], roles: list[str]) -> str:
    asked = {r: ROLES[r][1] for r in roles}
    return (f"{SYSTEM}\n\nRoles to find:\n{json.dumps(asked, indent=1)}\n\n"
            f"Page: {str((xray or {}).get('url') or '')[:200]}\n"
            f"Candidates:\n{json.dumps(for_ai(xray), ensure_ascii=False)}\n\n"
            f"Answer with JSON only, keys {json.dumps(roles)}.")


def parse(text: str, xray: dict[str, Any], roles: list[str]) -> dict[str, dict[str, Any]]:
    """The AI's answer, strictly: one JSON object (a ```json fence around it is tolerated), only the asked roles,
    each an integer that names a candidate of the right kind, or null. Returns role -> candidate."""
    raw = (text or "").strip()
    fence = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", raw, flags=re.S)
    if fence:
        raw = fence.group(1)
    if len(raw) > 2000:
        raise Rejected("answer too long")
    try:
        data = json.loads(raw)
    except ValueError:
        raise Rejected("not JSON") from None
    if not isinstance(data, dict):
        raise Rejected("not a JSON object")
    extra = set(data) - set(roles)
    if extra:
        raise Rejected(f"roles not asked: {sorted(extra)}")
    candidates = [c for c in (xray or {}).get("candidates") or [] if isinstance(c, dict)]
    out: dict[str, dict[str, Any]] = {}
    for role, value in data.items():
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise Rejected(f"{role}: not a candidate number ({str(value)[:60]!r})")
        if not 0 <= value < len(candidates):
            raise Rejected(f"{role}: no candidate {value}")
        c = candidates[value]
        if c.get("kind") != ROLES[role][0]:
            raise Rejected(f"{role}: candidate {value} is a {c.get('kind')}, not a {ROLES[role][0]}")
        if role == "answer" and c.get("is_your_message"):
            raise Rejected("answer: that is the user's own message")
        out[role] = c
    return out


def to_patch(chosen: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Selectors the PAGE wrote for the chosen candidates (an answer's finds the next answers too)."""
    patch = {}
    for role, c in chosen.items():
        sel = str(c.get("general") if role == "answer" else c.get("sel") or "")
        if sel and len(sel) < 300:
            patch[role] = [sel]
    return patch


def record(paths: "Paths", entry: dict[str, Any]) -> dict[str, Any]:
    """Every repair, kept or not: what failed, which AI, what it answered, what the page said."""
    entry = {"when": datetime.now().isoformat(timespec="seconds"), **entry}
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    with (paths.state_dir / LOG).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def history(paths: "Paths", site: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    try:
        lines = (paths.state_dir / LOG).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            x = json.loads(line)
        except ValueError:
            continue
        if site is None or x.get("site") == site:
            out.append(x)
        if len(out) >= limit:
            break
    return out


__all__ = ["LOG", "PREFERRED", "ROLES", "Rejected", "configure", "for_ai", "helper", "helpers", "history", "parse",
           "prompt", "record", "settings", "to_patch"]
