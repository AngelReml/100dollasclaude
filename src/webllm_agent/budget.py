"""A daily cap per AI by API (PLAN-v5 D9): a runaway loop, a bug or a forgotten job cannot use up a
free quota. The chat sites have their own guard (guard.py: spacing, daily cap, pauses); this is for the
AIs reached through OmniRoute. The models on this PC have no quota and are not capped unless a
provider sets ``daily_cap`` itself.

    data/config.yaml → guard: {api_daily_cap: 300}   (every API AI)
                        providers: {zai: {daily_cap: 50}}   (one AI)
"""

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path
from typing import Callable

from .config import ProviderConfig

_LOCK = threading.Lock()


class Budget:
    def __init__(self, path: Path, default_cap: int, today: Callable[[], str] = lambda: date.today().isoformat()) -> None:
        self.path, self.default_cap, self.today = path, default_cap, today

    def cap(self, p: ProviderConfig) -> int | None:
        if p.daily_cap is not None:
            return p.daily_cap
        return self.default_cap if p.gateway == "omniroute" else None

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def used(self, name: str) -> int:
        with _LOCK:
            return int(self._read().get(self.today(), {}).get(name, 0))

    def take(self, p: ProviderConfig) -> bool:
        """Count one call to ``p`` today; False (nothing counted) when its cap is reached."""
        cap = self.cap(p)
        if cap is None:
            return True
        with _LOCK:
            data = self._read()
            day = self.today()
            counts = data.get(day, {}) if isinstance(data.get(day), dict) else {}
            if int(counts.get(p.name, 0)) >= cap:
                return False
            counts[p.name] = int(counts.get(p.name, 0)) + 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({day: counts}, indent=1), encoding="utf-8")  # older days dropped
            return True

    def notice(self, p: ProviderConfig) -> str:
        return f"{p.display} ha llegado a su tope diario ({self.cap(p)} preguntas); mañana vuelve sola."


def budget_for(cfg) -> Budget:  # cfg: AppConfig (not imported: config imports nothing from here)
    return Budget(cfg.paths.state_dir / "api_budget.json", cfg.guard.api_daily_cap)


__all__ = ["Budget", "budget_for"]
