"""Each chat's card (PLAN-v5 F4, D22): what the extension discovered on its page (models, modes, "+" menu,
files), read-only, and which model is the strongest.

    data/state/fichas/<site>.json    the last discovery + Iván's own "este es el más potente"
    data/state/patches/<site>.json   where things are, as Iván showed them ("Enséñame dónde está")

The order of the models comes from catalog.yaml (`models`: name fragments with a rank, their source and
date). A model the table does not know is "nuevo, sin datos" and is never taken as the strongest on its
own (D21.3): only when Iván says so, or when the table is updated.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .catalog import CatalogAI
    from .config import Paths

TEACHABLE = {"model": "modelButton", "plus": "plusButton", "file": "fileInput"}


def norm(name: str) -> str:
    """"Qwen3.8-Max" and "qwen 3.8 max" are the same model name (= extension/common.js normName)."""
    s = unicodedata.normalize("NFKD", str(name or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9.぀-ヿ一-鿿]+", "", s)


def _path(paths: "Paths", folder: str, site: str):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", site):
        raise ValueError(site)
    return paths.state_dir / folder / f"{site}.json"


def _read(path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def load(paths: "Paths", site: str) -> dict[str, Any]:
    return _read(_path(paths, "fichas", site))


def save_discovery(paths: "Paths", site: str, card: dict[str, Any]) -> dict[str, Any]:
    """Keep what the page showed (names only: nothing of the conversation), and Iván's own choice."""
    old = load(paths, site)
    clean = {
        "when": time.strftime("%Y-%m-%d %H:%M"),
        "current_model": str(card.get("current_model") or "")[:80] or None,
        "model_button": bool(card.get("model_button")),
        "models": [str(m.get("name"))[:80] for m in card.get("models") or [] if isinstance(m, dict) and m.get("name")][:30],
        "modes": [{"name": str(m.get("name"))[:60], "on": bool(m.get("on")), "mode": m.get("mode")}
                  for m in card.get("modes") or [] if isinstance(m, dict) and m.get("name")][:20],
        "plus": [str(x)[:80] for x in card.get("plus") or []][:30],
        "files": [{"accept": str(f.get("accept") or "")[:200], "multiple": bool(f.get("multiple"))}
                  for f in card.get("files") or [] if isinstance(f, dict)][:5],
        "closed": bool(card.get("closed", True)),
        "strongest_by_ivan": old.get("strongest_by_ivan"),
        "use_page_model": bool(old.get("use_page_model")),
    }
    _write(_path(paths, "fichas", site), clean)
    return clean


def set_strongest(paths: "Paths", site: str, model: str | None, page: bool = False) -> dict[str, Any]:
    """Iván's choice: this model is the strongest; or None = back to the catalog's table; or page=True =
    never switch the model of this chat, use whatever its page has (a page where webllm cannot confirm the
    model it picks would otherwise send nothing, ever)."""
    card = load(paths, site)
    if model is not None and norm(model) not in {norm(m) for m in card.get("models") or []}:
        raise ValueError(model)
    card["strongest_by_ivan"] = None if page else model
    card["use_page_model"] = page
    _write(_path(paths, "fichas", site), card)
    return card


def rank(entry: "CatalogAI | None", card: dict[str, Any]) -> list[dict[str, Any]]:
    """The discovered models, strongest first: Iván's choice, then the catalog's table; unknown ones last,
    marked "nuevo, sin datos", never the strongest on their own."""
    table = [(norm(m["match"]), int(m["rank"])) for m in (entry.models if entry else ()) if m.get("match")]
    mine = norm(card.get("strongest_by_ivan") or "")
    out = []
    for i, name in enumerate(card.get("models") or []):
        n = norm(name)
        hits = [r for frag, r in table if frag and frag in n]
        out.append({"name": name, "slug": n, "rank": min(hits) if hits else None, "known": bool(hits) or n == mine,
                    "by_ivan": bool(mine) and n == mine, "order": i})
    out.sort(key=lambda m: (not m["by_ivan"], m["rank"] is None, m["rank"] or 0, m["order"]))
    top = out[0] if out else None
    # Two models with the same rank (the table says "Qwen 3.8", the page has "-Plus" and "-Max"): webllm
    # does not guess which one is stronger; Iván says it.
    tied = [m for m in out if top and not top["by_ivan"] and top["rank"] is not None and m["rank"] == top["rank"]]
    if top and (top["by_ivan"] or (top["rank"] is not None and len(tied) == 1)):
        top["strongest"] = True
    for m in out:
        m.setdefault("strongest", False)
        m["tie"] = len(tied) > 1 and m in tied
        del m["order"]
    return out


def strongest(entry: "CatalogAI | None", card: dict[str, Any]) -> str | None:
    if card.get("use_page_model"):
        return None
    ranked = rank(entry, card)
    return ranked[0]["name"] if ranked and ranked[0]["strongest"] else None


def load_patch(paths: "Paths", site: str) -> dict[str, list[str]]:
    return _read(_path(paths, "patches", site))


def forget_patch(paths: "Paths", site: str) -> bool:
    """Undo what Iván showed ("Olvidar lo que te enseñé"): the site goes back to its own and generic rules."""
    path = _path(paths, "patches", site)
    existed = path.exists()
    path.unlink(missing_ok=True)
    return existed


def teach(paths: "Paths", site: str, what: str, selector: str) -> dict[str, list[str]]:
    """Keep where Iván showed a thing is (first in the list, the old ones after, at most 5)."""
    key = TEACHABLE[what]
    if not selector or len(selector) > 300:
        raise ValueError(selector)
    patch = load_patch(paths, site)
    patch[key] = [selector, *[s for s in patch.get(key, []) if s != selector]][:5]
    _write(_path(paths, "patches", site), patch)
    return patch


__all__ = ["TEACHABLE", "forget_patch", "load", "load_patch", "norm", "rank", "save_discovery", "set_strongest", "strongest", "teach"]
