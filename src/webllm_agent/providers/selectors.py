"""Selector resolution — versioned YAML files + priority-ordered candidate list.

Each provider has its own YAML under `providers/selectors/<provider>/v<n>.yaml`.
The current schema version is selected via `current` (a YAML key pointing at
the version to use). Each logical "slot" (composer, send_button, ...) carries
an ordered list of selector candidates.

The resolver tries candidates in order; the first one that returns ≥1 element
is the winner. The result is cached per (provider, slot, page_url_signature)
for the lifetime of the BrowserContext.

Hierarchy of preference (encoded in YAML `priority` field, lower wins):
    1. data-testid
    2. aria-label / role
    3. visible text
    4. CSS class / structure

If a slot's selector stops working (zero matches, or the action fails),
the resolver marks the candidate as `broken` for this run and falls through.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from ..observability.logging import get_logger

log = get_logger("providers.selectors")


class SelectorError(RuntimeError):
    """Raised when no candidate for a slot resolves to anything."""


@dataclass
class SlotSpec:
    """One logical UI slot (e.g. composer, send button)."""

    name: str
    candidates: list[dict[str, Any]] = field(default_factory=list)

    def sorted(self) -> list[dict[str, Any]]:
        return sorted(self.candidates, key=lambda c: int(c.get("priority", 99)))


@dataclass
class ProviderSelectors:
    """All slots for one provider version."""

    version: int
    home_url: str
    slots: dict[str, SlotSpec] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class SelectorResolver:
    """Loads selector YAMLs and resolves them against a Playwright page.

    Lifecycle:
        resolver = SelectorResolver(providers_dir)
        specs = resolver.load("claude")
        selector_str = resolver.resolve(page, specs.slots["composer"])
    """

    def __init__(self, providers_dir: Path) -> None:
        self._dir = providers_dir
        self._cache: dict[str, ProviderSelectors] = {}

    def load(self, provider: str, *, version: int | None = None) -> ProviderSelectors:
        """Load selector YAML for `provider`.

        If `version` is None, reads `providers/selectors/<provider>/current.yaml`
        (a tiny pointer file: `version: 2`). Otherwise loads `v<n>.yaml`.
        """
        key = f"{provider}:{version or 'current'}"
        if key in self._cache:
            return self._cache[key]

        prov_dir = self._dir / provider
        if not prov_dir.is_dir():
            raise SelectorError(f"no selectors directory for provider {provider!r}")

        if version is None:
            current_file = prov_dir / "current.yaml"
            if current_file.exists():
                with current_file.open("r", encoding="utf-8") as fh:
                    pointer = yaml.safe_load(fh) or {}
                version = int(pointer.get("version", 1))
            else:
                version = 1

        slot_file = prov_dir / f"v{version}.yaml"
        if not slot_file.exists():
            raise SelectorError(f"selector file not found: {slot_file}")

        with slot_file.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise SelectorError(f"selector YAML {slot_file} must be a mapping")

        slots: dict[str, SlotSpec] = {}
        for slot_name, slot_data in (data.get("slots") or {}).items():
            if not isinstance(slot_data, dict):
                continue
            candidates = slot_data.get("candidates") or []
            if not isinstance(candidates, list):
                continue
            slots[slot_name] = SlotSpec(name=slot_name, candidates=list(candidates))

        specs = ProviderSelectors(
            version=int(data.get("version", version)),
            home_url=str(data.get("home_url", "")),
            slots=slots,
            metadata={k: v for k, v in data.items() if k not in {"version", "slots", "home_url"}},
        )
        self._cache[key] = specs
        log.info("loaded selectors provider=%s version=%s slots=%s", provider, specs.version, list(specs.slots))
        return specs

    async def resolve(
        self,
        page: Any,  # playwright.async_api.Page — typing kept loose to avoid import cycle
        slot: SlotSpec,
        *,
        timeout_ms: int = 5000,
    ) -> str:
        """Return the first selector string that finds ≥1 element on the page.

        Raises SelectorError if every candidate fails.
        """
        for cand in slot.sorted():
            sel = self._render(cand)
            if not sel:
                continue
            try:
                await page.wait_for_selector(sel, state="attached", timeout=timeout_ms)
                log.debug("selector slot=%s matched %r (priority=%s)", slot.name, sel, cand.get("priority"))
                return sel
            except Exception:  # noqa: BLE001 — Playwright raises a variety of types
                log.debug("selector slot=%s miss %r", slot.name, sel)
        raise SelectorError(f"no candidate for slot {slot.name!r} matched")

    def _render(self, candidate: dict[str, Any]) -> str:
        """Convert a YAML candidate dict into a Playwright selector string."""
        kind = candidate.get("kind", "css")
        value = candidate.get("value") or candidate.get("selector")
        if not value:
            return ""
        if kind == "css":
            return str(value)
        if kind == "text":
            # Wrap in :has-text() for Playwright
            return f':text("{value}")'
        if kind == "role":
            return f'role={value}'
        if kind == "testid":
            return f'[data-testid="{value}"]'
        if kind == "aria":
            return f'[aria-label*="{value}" i]'
        return str(value)

    def all_candidates(self, slot: SlotSpec) -> Iterable[str]:
        """Yield every candidate selector (for diagnostics)."""
        for c in slot.sorted():
            yield self._render(c)
