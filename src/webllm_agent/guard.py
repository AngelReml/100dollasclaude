"""Account guard for web (session-cookie) providers.

Rules, per guarded provider:
- at most one request in flight (a lock file, so it holds across processes);
- a minimum spacing between requests (waits the remainder);
- a daily cap (local calendar day);
- on HTTP 401/403/429, or a body that looks like a challenge or login wall,
  the provider goes into COOLDOWN for ``cooldown_hours`` and is skipped until
  then. It is never retried through during the cooldown.

State lives in ``data/state/guard.json`` so it survives restarts. Nothing
here tries to evade bot detection: it only slows down and stops.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .client import ChatResult
from .config import GuardConfig, ProviderConfig

CHALLENGE_MARKERS = (
    "just a moment", "cf-chl", "challenge-platform", "captcha", "verify you are human",
    "are you a robot", "unusual traffic", "attention required", "human verification",
)
LOGIN_MARKERS = (
    "please log in", "please login", "sign in to continue", "log in to continue",
    "login required", "not logged in", "session expired", "session has expired",
    "token expired", "invalid token", "cookie expired", "unauthorized",
)

RATE_LIMIT = "rate_limit"
CHALLENGE = "challenge"
SESSION = "session"


class GuardBlocked(RuntimeError):
    """The guard refuses to send to this provider right now."""

    def __init__(self, reason: str, message_es: str) -> None:
        super().__init__(message_es)
        self.reason = reason  # cooldown | daily_cap | busy
        self.message_es = message_es


@dataclass
class Permit:
    provider: str
    lock_path: Path


def classify_trip(result: ChatResult) -> str | None:
    """Return RATE_LIMIT / CHALLENGE / SESSION if this result must trip the guard."""
    body = (result.body_excerpt or "").lower()
    if result.http_status == 429:
        return RATE_LIMIT
    if result.http_status in (401, 403):
        return CHALLENGE if any(m in body for m in CHALLENGE_MARKERS) else SESSION
    if result.http_status is not None and result.http_status != 200:
        if any(m in body for m in CHALLENGE_MARKERS):
            return CHALLENGE
        if any(m in body for m in LOGIN_MARKERS):
            return SESSION
        return None
    if result.ok:
        # A 200 whose "answer" is really an HTML challenge / login page.
        text = result.text.lstrip().lower()
        if text.startswith(("<!doctype html", "<html")):
            if any(m in text for m in CHALLENGE_MARKERS):
                return CHALLENGE
            if any(m in text for m in LOGIN_MARKERS):
                return SESSION
    return None


class Guard:
    def __init__(
        self,
        state_file: Path,
        cfg: GuardConfig,
        *,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], "asyncio.Future"] = asyncio.sleep,
        lock_wait_s: float = 60.0,
        stale_lock_s: float = 900.0,
    ) -> None:
        self.state_file = state_file
        self.lock_dir = state_file.parent / "locks"
        self.cfg = cfg
        self.clock = clock
        self.sleep = sleep
        self.lock_wait_s = lock_wait_s
        self.stale_lock_s = stale_lock_s

    # ------------------------------------------------------------------ state

    def _load(self) -> dict:
        if not self.state_file.exists():
            return {"version": 1, "providers": {}}
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A corrupt state file must not silently lift a cooldown: keep the
            # evidence and refuse to guess.
            raise RuntimeError(f"guard state is unreadable: {self.state_file}")
        data.setdefault("providers", {})
        return data

    def _save(self, data: dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.state_file)

    def _today(self) -> str:
        return datetime.fromtimestamp(self.clock()).strftime("%Y-%m-%d")

    @staticmethod
    def _fmt(ts: float) -> str:
        return datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")

    # ------------------------------------------------------------------- lock

    def _try_lock(self, name: str) -> Path | None:
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        path = self.lock_dir / f"{name}.lock"
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - path.stat().st_mtime
            except FileNotFoundError:
                return self._try_lock(name)
            if age > self.stale_lock_s:  # left behind by a crashed run
                path.unlink(missing_ok=True)
                return self._try_lock(name)
            return None
        with os.fdopen(fd, "w") as fh:
            fh.write(f"{os.getpid()} {time.time()}\n")
        return path

    # ----------------------------------------------------------------- public

    def check(self, provider: ProviderConfig) -> None:
        """Raise GuardBlocked if the provider is in cooldown or over its daily cap."""
        st = self._load()["providers"].get(provider.name, {})
        until = st.get("cooldown_until")
        if until and until > self.clock():
            raise GuardBlocked(
                "cooldown",
                f"{provider.name}: en pausa de protección hasta el {self._fmt(until)} "
                f"({st.get('cooldown_reason', '')}). No se envía nada.",
            )
        if st.get("day") == self._today() and st.get("count_today", 0) >= self.cfg.daily_cap:
            raise GuardBlocked(
                "daily_cap",
                f"{provider.name}: tope diario alcanzado ({self.cfg.daily_cap} envíos). Vuelve mañana.",
            )

    async def acquire(self, provider: ProviderConfig, notify: Callable[[str], None] = print) -> Permit:
        """Wait for the provider's slot; count the request; return a Permit to release()."""
        self.check(provider)
        waited = 0.0
        lock = self._try_lock(provider.name)
        while lock is None:
            if waited >= self.lock_wait_s:
                raise GuardBlocked("busy", f"{provider.name}: ya hay otro envío en curso a este proveedor; se salta.")
            await self.sleep(1.0)
            waited += 1.0
            lock = self._try_lock(provider.name)
        try:
            self.check(provider)  # state may have changed while waiting
            data = self._load()
            st = data["providers"].setdefault(provider.name, {})
            last = st.get("last_request_ts")
            if last is not None:
                gap = self.cfg.min_spacing_s - (self.clock() - last)
                if gap > 0:
                    notify(f"{provider.name}: espero {gap:.0f} s entre envíos (protección de cuenta)")
                    await self.sleep(gap)
            data = self._load()
            st = data["providers"].setdefault(provider.name, {})
            if st.get("day") != self._today():
                st["day"], st["count_today"] = self._today(), 0
            st["count_today"] = st.get("count_today", 0) + 1
            st["last_request_ts"] = self.clock()
            self._save(data)
        except BaseException:
            lock.unlink(missing_ok=True)
            raise
        return Permit(provider.name, lock)

    def release(self, permit: Permit) -> None:
        permit.lock_path.unlink(missing_ok=True)

    def report(self, provider: ProviderConfig, result: ChatResult) -> str | None:
        """Trip the cooldown if the result demands it; return a Spanish notice or None."""
        kind = classify_trip(result)
        if kind is None:
            return None
        until = self.clock() + self.cfg.cooldown_hours * 3600
        reason = {
            RATE_LIMIT: "demasiadas peticiones (HTTP 429)",
            CHALLENGE: "la web pidió verificación humana",
            SESSION: f"sesión caducada o no autorizada (HTTP {result.http_status})",
        }[kind]
        data = self._load()
        st = data["providers"].setdefault(provider.name, {})
        st["cooldown_until"] = until
        st["cooldown_reason"] = reason
        st["last_trip_http_status"] = result.http_status
        self._save(data)
        msg = (
            f"AVISO {provider.name}: {reason}. Lo dejo en pausa hasta el {self._fmt(until)} "
            f"y no lo reintento."
        )
        if kind == SESSION and provider.relogin_hint:
            msg += f" Para arreglarlo: {provider.relogin_hint}; luego ejecuta: webllm guard clear {provider.name}"
        elif kind == CHALLENGE:
            msg += f" Abre la web de {provider.name} en tu navegador normal y úsala a mano un rato antes de volver."
        return msg

    def clear(self, name: str) -> bool:
        data = self._load()
        st = data["providers"].get(name)
        if not st or not st.get("cooldown_until"):
            return False
        st["cooldown_until"] = None
        st["cooldown_reason"] = ""
        self._save(data)
        return True

    def status(self) -> dict:
        return self._load()["providers"]
