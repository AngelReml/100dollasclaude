"""The web chats webllm knows (PLAN-v5 F3): catalog.yaml (in git) + what Iván did with each one.

States (data/state/catalog_state.json, never in git):
    sin_conectar   not tried, or Iván did not log in within the time he had
    conectada      the "pong" test answered through the guard; it is one of his AIs (custom_ais.json)
    no_funciona    webllm cannot use it yet: the reason in Spanish + the page diagnosis (for F6)
    no_la_quiero   Iván unchecked it in "Conectar varias" (he can still connect it)
The built-in chats (Qwen, DeepSeek, z.ai, Meta: selectors in extension/sites.js) are in the catalog too;
they are configured in data/config.yaml and "Conectar" for them is the session check (PLAN-v3 3b).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from .config import Paths, ProviderConfig

CATALOG_FILE = Path(__file__).with_name("catalog.yaml")
STATE_FILE = "catalog_state.json"
STATES = ("sin_conectar", "conectada", "no_funciona", "no_la_quiero")
GROUPS = ("tuyas", "1", "2")
ACCOUNTS = ("si", "no", "opcional", "desconocido")
KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class CatalogAI:
    key: str
    name: str
    by: str
    url: str
    group: str
    purpose: str
    family: str
    tags: tuple[str, ...]
    account: str
    private: bool
    builtin: bool = False
    daily_cap: int | None = None
    note: str = ""
    may_fail: str = ""
    # The order of its models (PLAN-v5 F4): [{"match": name fragment, "rank": 1 = strongest}], with where
    # that order comes from and when. A model the table does not know is "nuevo, sin datos".
    models: tuple[dict[str, Any], ...] = ()
    models_source: str = ""
    models_checked: str = ""

    def public(self) -> dict[str, Any]:
        return {"key": self.key, "name": self.name, "by": self.by, "url": self.url, "group": self.group,
                "purpose": self.purpose, "family": self.family, "tags": list(self.tags), "account": self.account,
                "private": self.private, "builtin": self.builtin, "daily_cap": self.daily_cap, "note": self.note,
                "may_fail": self.may_fail, "models": list(self.models), "models_source": self.models_source,
                "models_checked": self.models_checked}


@dataclass(frozen=True)
class Catalog:
    checked: str
    ais: tuple[CatalogAI, ...]

    def get(self, key: str) -> CatalogAI | None:
        return next((a for a in self.ais if a.key == key), None)

    def by_host(self, host: str) -> CatalogAI | None:
        from urllib.parse import urlsplit
        return next((a for a in self.ais if (urlsplit(a.url).hostname or "") == host.lower()), None)


def load(path: Path = CATALOG_FILE) -> Catalog:
    """Read and check the catalog; a broken catalog is a programming error (CatalogError), never silent."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ais, seen = [], set()
    for spec in raw.get("ais") or []:
        try:
            ai = CatalogAI(
                key=str(spec["key"]), name=str(spec["name"]), by=str(spec.get("by") or ""), url=str(spec["url"]),
                group=str(spec["group"]), purpose=str(spec.get("purpose") or ""), family=str(spec.get("family") or ""),
                tags=tuple(str(t) for t in spec.get("tags") or ()), account=str(spec.get("account") or "desconocido"),
                private=bool(spec.get("private", True)), builtin=bool(spec.get("builtin", False)),
                daily_cap=int(spec["daily_cap"]) if spec.get("daily_cap") is not None else None,
                note=str(spec.get("note") or ""), may_fail=str(spec.get("may_fail") or ""),
                models=tuple({"match": str(m["match"]), "rank": int(m["rank"])} for m in spec.get("models") or []),
                models_source=str(spec.get("models_source") or ""), models_checked=str(spec.get("models_checked") or ""))
        except (KeyError, TypeError, ValueError) as exc:
            raise CatalogError(f"catalog entry {spec!r}: {exc}") from exc
        if not KEY.match(ai.key) or ai.key in seen:
            raise CatalogError(f"catalog key {ai.key!r} is not valid or is repeated")
        if ai.group not in GROUPS or ai.account not in ACCOUNTS:
            raise CatalogError(f"catalog entry {ai.key}: group {ai.group!r} / account {ai.account!r}")
        seen.add(ai.key)
        ais.append(ai)
    return Catalog(checked=str(raw.get("checked") or ""), ais=tuple(ais))


# ------------------------------------------------------------------ state

def load_state(paths: "Paths") -> dict[str, dict[str, Any]]:
    try:
        data = json.loads((paths.state_dir / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict) and v.get("state") in STATES} if isinstance(data, dict) else {}


def save_state(paths: "Paths", key: str, state: str, *, reason: str = "", message: str = "", detail: str = "") -> None:
    if state not in STATES:
        raise ValueError(state)
    data = load_state(paths)
    data[key] = {"state": state, "reason": reason, "message": message, "detail": detail[:20000],
                 "when": time.strftime("%Y-%m-%d %H:%M")}
    path = paths.state_dir / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ who may use what

def eligible_for_auto(p: "ProviderConfig") -> bool:
    """May "Automático" (F8) or the Committee (F7) pick this AI on their own? Never one that is not private
    (Arena publishes what you write; Google AI Studio may use it): those only when Iván picks them."""
    return p.private and p.enabled


__all__ = ["CATALOG_FILE", "Catalog", "CatalogAI", "CatalogError", "STATES", "eligible_for_auto", "load",
           "load_state", "save_state"]
