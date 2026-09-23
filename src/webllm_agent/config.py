"""Configuration loading and runtime paths.

Single source of truth for:
- where runtime data lives (browser profiles, runs, logs, state)
- which provider adapters are enabled
- global timeouts and limits

Loaded from `data/config.yaml` (auto-created on first run with safe defaults).
Environment variables override file values so users can tune behaviour
without editing files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Project root resolution: this file lives in <root>/src/webllm_agent/config.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


@dataclass(frozen=True)
class Paths:
    """Filesystem layout for runtime data."""

    data_dir: Path
    browser_profiles_dir: Path
    state_dir: Path
    runs_dir: Path
    logs_dir: Path
    screenshots_dir: Path
    dumps_dir: Path
    config_file: Path

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> "Paths":
        return cls(
            data_dir=data_dir,
            browser_profiles_dir=data_dir / "browser_profiles",
            state_dir=data_dir / "state",
            runs_dir=data_dir / "runs",
            logs_dir=data_dir / "logs",
            screenshots_dir=data_dir / "screenshots",
            dumps_dir=data_dir / "dumps",
            config_file=data_dir / "config.yaml",
        )

    def ensure(self) -> None:
        """Create every directory if it doesn't exist."""
        for p in (
            self.data_dir,
            self.browser_profiles_dir,
            self.state_dir,
            self.runs_dir,
            self.logs_dir,
            self.screenshots_dir,
            self.dumps_dir,
        ):
            p.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    enabled: bool = True
    # Hard cap on concurrent browser contexts in this provider.
    max_concurrency: int = 1


@dataclass(frozen=True)
class AppConfig:
    paths: Paths
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    default_provider: str = "claude"
    headless: bool = False  # Visible browser by default so the user can log in.
    debug: bool = False
    generation_timeout_s: float = 120.0
    response_idle_settle_ms: int = 1500
    # Which Chromium-family channel to launch. "chrome" uses the system Google
    # Chrome (real fingerprint, better vs anti-bot). "msedge" uses system Edge.
    # None falls back to Playwright's bundled Chromium.
    browser_channel: str | None = "chrome"
    # If set, BrowserManager will `connect_over_cdp(cdp_url)` instead of
    # launching a fresh browser. This uses the user's existing Chrome
    # instance (with all cookies/sessions). Requires Chrome to be started
    # with `--remote-debugging-port=<port>`.
    cdp_url: str | None = None
    request_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.7977.83 Safari/537.36"
    )

    def provider(self, name: str) -> ProviderConfig:
        return self.providers[name]


DEFAULT_CONFIG: dict[str, Any] = {
    "default_provider": "claude",
    "headless": False,
    "debug": False,
    "generation_timeout_s": 120.0,
    "response_idle_settle_ms": 1500,
    "browser_channel": "chrome",
    "cdp_url": None,
    "providers": {
        "claude": {"enabled": True, "max_concurrency": 1},
        "chatgpt": {"enabled": False, "max_concurrency": 1},
        "gemini": {"enabled": False, "max_concurrency": 1},
        "grok": {"enabled": False, "max_concurrency": 1},
    },
}


def _coerce_providers(raw: dict[str, Any]) -> dict[str, ProviderConfig]:
    out: dict[str, ProviderConfig] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        out[name] = ProviderConfig(
            name=name,
            enabled=bool(spec.get("enabled", True)),
            max_concurrency=int(spec.get("max_concurrency", 1)),
        )
    return out


def load_config(data_dir: Path | None = None) -> AppConfig:
    """Load config from `data/config.yaml`, creating it on first run.

    Resolution order (later overrides earlier):
      1. DEFAULT_CONFIG
      2. data/config.yaml
      3. Environment variables
    """
    data_dir = (data_dir or DEFAULT_DATA_DIR).resolve()
    paths = Paths.from_data_dir(data_dir)
    paths.ensure()
    cfg_file = paths.config_file

    merged: dict[str, Any] = {k: v for k, v in DEFAULT_CONFIG.items()}
    if cfg_file.exists():
        with cfg_file.open("r", encoding="utf-8") as fh:
            on_disk = yaml.safe_load(fh) or {}
        if isinstance(on_disk, dict):
            for key, value in on_disk.items():
                merged[key] = value

    # Env overrides
    if env_default := os.getenv("WEBLLM_PROVIDER"):
        merged["default_provider"] = env_default
    if env_headless := os.getenv("WEBLLM_HEADLESS"):
        merged["headless"] = env_headless.lower() in {"1", "true", "yes"}
    if env_debug := os.getenv("WEBLLM_DEBUG"):
        merged["debug"] = env_debug.lower() in {"1", "true", "yes"}
    if env_cdp := os.getenv("WEBLLM_CDP_URL"):
        merged["cdp_url"] = env_cdp

    providers_raw = merged.get("providers") or {}
    if not isinstance(providers_raw, dict):
        providers_raw = {}

    return AppConfig(
        paths=paths,
        providers=_coerce_providers(providers_raw),
        default_provider=str(merged.get("default_provider", "claude")),
        headless=bool(merged.get("headless", False)),
        debug=bool(merged.get("debug", False)),
        generation_timeout_s=float(merged.get("generation_timeout_s", 120.0)),
        response_idle_settle_ms=int(merged.get("response_idle_settle_ms", 1500)),
        browser_channel=_resolve_channel(merged.get("browser_channel")),
        cdp_url=_resolve_cdp_url(merged.get("cdp_url")),
    )


def _resolve_channel(value: Any) -> str | None:
    """Coerce the YAML value to a valid Playwright channel or None."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("", "none", "chromium", "bundled"):
        return None
    if s in ("chrome", "msedge", "chrome-beta", "msedge-beta", "msedge-dev"):
        return s
    # Unknown value → be conservative
    return None


def _resolve_cdp_url(value: Any) -> str | None:
    """Coerce the YAML value to a CDP URL or None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("none", "false", "0"):
        return None
    if not s.startswith(("http://", "https://", "ws://", "wss://")):
        s = "http://" + s
    return s.rstrip("/")


def write_default_config(paths: Paths) -> None:
    """Write the default config file if it doesn't already exist."""
    if paths.config_file.exists():
        return
    with paths.config_file.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(DEFAULT_CONFIG, fh, sort_keys=False, allow_unicode=True)
