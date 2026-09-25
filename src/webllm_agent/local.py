"""AI programs running on this PC (LM Studio, Ollama): their chat models become AIs "En tu PC".

- Known servers: LM Studio on :1234 and Ollama on :11434, plus any in data/config.yaml
  ``local_servers`` (``key``, ``name``, ``url``, optional ``start`` command).
- Models come from ``GET <url>/models``. Embedding models (id containing "embed") cannot chat
  and are left out, and so is anything the Claude/ChatGPT exclusion refuses.
- The models last seen are kept in data/state/local_models.json, so an AI still shows (as
  "apagada", with a button that starts its program) while that program is off.
- No account guard (there is no account), but one call at a time per server: the PC is one.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from .config import AppConfig, LocalServer, ProviderConfig, is_blocked_model

STATE_FILE = "local_models.json"
LOCAL_TIMEOUT_S = 600.0  # a big model loading for the first time can take minutes

_locks: dict[tuple[int, str], asyncio.Lock] = {}


def server_lock(key: str) -> asyncio.Lock:
    """One call at a time per local server, across every run in this process."""
    loop = id(asyncio.get_running_loop())
    return _locks.setdefault((loop, key), asyncio.Lock())


def provider_name(server_key: str, model: str) -> str:
    return f"{server_key}:{model}"


def start_command(server: LocalServer) -> list[str] | None:
    """How to start this server on this PC, or None if its program is not installed."""
    if server.start:
        return list(server.start)
    if server.key == "lmstudio":
        exe = Path.home() / ".lmstudio" / "bin" / ("lms.exe" if os.name == "nt" else "lms")
        found = str(exe) if exe.is_file() else shutil.which("lms")
        return [found, "server", "start"] if found else None
    if server.key == "ollama":
        exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        found = shutil.which("ollama") or (str(exe) if exe.is_file() else None)
        return [found, "serve"] if found else None
    return None


def launch_detached(command: list[str]) -> None:
    """Start a background program without tying it to this process (Windows: minimized window)."""
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", "start", "", "/min", *command],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)


@dataclass
class ServerStatus:
    server: LocalServer
    up: bool
    models: list[str]
    installed: bool


class LocalModels:
    """Discovers the local servers (cached for ``ttl`` seconds) and turns their models into providers."""

    def __init__(self, *, ttl: float = 10.0, launcher: Callable[[list[str]], None] | None = launch_detached,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl = ttl
        self.launcher = launcher
        self.clock = clock
        self._statuses: list[ServerStatus] = []
        self._when = -1e9
        self._last_start: dict[str, float] = {}

    def _state_path(self, cfg: AppConfig) -> Path:
        return cfg.paths.state_dir / STATE_FILE

    def _known(self, cfg: AppConfig) -> dict[str, list[str]]:
        try:
            data = json.loads(self._state_path(cfg).read_text(encoding="utf-8"))
            return {k: [str(m) for m in v] for k, v in data.items() if isinstance(v, list)}
        except (OSError, ValueError, AttributeError):
            return {}

    def _chat_models(self, cfg: AppConfig, server: LocalServer, ids: list[str]) -> list[str]:
        return [m for m in ids if "embed" not in m.lower() and not is_blocked_model(cfg, f"{server.key}/{m}")]

    async def refresh(self, cfg: AppConfig, force: bool = False) -> list[ServerStatus]:
        if not force and self.clock() - self._when < self.ttl:
            return self._statuses
        known = self._known(cfg)

        async def probe(client: httpx.AsyncClient, server: LocalServer) -> ServerStatus:
            try:
                r = await client.get(f"{server.url.rstrip('/')}/models", timeout=2.0)
                ids = [str(m["id"]) for m in r.json().get("data", []) if isinstance(m, dict) and m.get("id")]
                if r.status_code == 200:
                    return ServerStatus(server, True, self._chat_models(cfg, server, ids),
                                        start_command(server) is not None)
            except (httpx.HTTPError, ValueError, AttributeError, TypeError):
                pass
            return ServerStatus(server, False, known.get(server.key, []), start_command(server) is not None)

        async with httpx.AsyncClient() as client:
            statuses = list(await asyncio.gather(*(probe(client, s) for s in cfg.local_servers)))
        seen = {st.server.key: st.models for st in statuses if st.up}
        if seen and any(known.get(k) != v for k, v in seen.items()):
            cfg.paths.state_dir.mkdir(parents=True, exist_ok=True)
            self._state_path(cfg).write_text(json.dumps({**known, **seen}, indent=2), encoding="utf-8")
        self._statuses, self._when = statuses, self.clock()
        return statuses

    def providers(self) -> dict[str, ProviderConfig]:
        out: dict[str, ProviderConfig] = {}
        for st in self._statuses:
            for model in st.models:
                name = provider_name(st.server.key, model)
                out[name] = ProviderConfig(
                    name=name, model=f"{st.server.key}/{model}", kind="local", gateway="local",
                    timeout_s=LOCAL_TIMEOUT_S, label=f"{st.server.name} · {model}",
                    base_url=st.server.url, remote_model=model,
                )
        return out

    def with_providers(self, cfg: AppConfig) -> AppConfig:
        """``cfg`` plus the local models found by the last refresh (listed after the configured AIs)."""
        return dataclasses.replace(cfg, providers={**cfg.providers, **self.providers()})

    def status_of(self, key: str) -> ServerStatus | None:
        return next((st for st in self._statuses if st.server.key == key), None)

    def start(self, cfg: AppConfig, key: str) -> str:
        """Start a server's program. Returns "started", "recent" (asked less than 30 s ago) or "not_installed"."""
        server = next((s for s in cfg.local_servers if s.key == key), None)
        command = start_command(server) if server else None
        if command is None or self.launcher is None:
            return "not_installed"
        if self.clock() - self._last_start.get(key, -1e9) < 30:
            return "recent"
        self._last_start[key] = self.clock()
        self.launcher(command)
        self._when = -1e9  # look again on the next status request
        return "started"


def label_for(name: str) -> str:
    """Human name for a local AI that is no longer listed (old history entries)."""
    key, _, model = name.partition(":")
    server = {"lmstudio": "LM Studio", "ollama": "Ollama"}.get(key, key)
    return f"{server} · {model}" if model else name


__all__ = ["LocalModels", "ServerStatus", "server_lock", "start_command", "launch_detached", "label_for",
           "provider_name", "LOCAL_TIMEOUT_S"]
