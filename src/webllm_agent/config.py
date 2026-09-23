"""Configuration loading and runtime paths.

Single source of truth for:
- where runtime data lives (runs, state, logs)
- the OmniRoute endpoint
- the provider names used by ``webllm ask --to`` and the OmniRoute model
  each one maps to, in priority order
- the account-guard limits for web providers

Loaded from ``data/config.yaml`` (created with the defaults below on first
run). Environment variables override file values where noted.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Project root resolution: this file lives in <root>/src/webllm_agent/config.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


class ConfigError(ValueError):
    """data/config.yaml is invalid."""


@dataclass(frozen=True)
class Paths:
    """Filesystem layout for runtime data."""

    data_dir: Path
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
            state_dir=data_dir / "state",
            runs_dir=data_dir / "runs",
            logs_dir=data_dir / "logs",
            screenshots_dir=data_dir / "screenshots",
            dumps_dir=data_dir / "dumps",
            config_file=data_dir / "config.yaml",
        )

    def ensure(self) -> None:
        """Create the directories the broadcaster writes to."""
        for p in (self.data_dir, self.state_dir, self.runs_dir, self.logs_dir):
            p.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    # "web" = driven through a browser session cookie (account guard applies);
    # "api" = an API key or keyless API.
    kind: str = "api"
    enabled: bool = True
    timeout_s: float = 180.0
    # Tried in order when the primary model fails (not after a guard trip).
    fallback_models: tuple[str, ...] = ()
    # The dashboard step Iván must redo when this provider's session expires.
    relogin_hint: str = ""

    @property
    def guarded(self) -> bool:
        return self.kind == "web"


@dataclass(frozen=True)
class GuardConfig:
    min_spacing_s: float = 20.0
    daily_cap: int = 150
    cooldown_hours: float = 6.0


@dataclass(frozen=True)
class AppConfig:
    paths: Paths
    base_url: str
    providers: dict[str, ProviderConfig] = field(default_factory=dict)  # priority order
    guard: GuardConfig = field(default_factory=GuardConfig)
    # Claude / ChatGPT / Codex are excluded from this tool: model ids starting
    # with one of these prefixes, or containing one of these substrings, or with
    # no "provider/" prefix at all, are refused.
    blocked_model_prefixes: tuple[str, ...] = ()
    blocked_model_substrings: tuple[str, ...] = ()
    # Model ids that belong to guarded web providers even when passed raw to --to.
    web_model_prefixes: tuple[str, ...] = ()

    def provider(self, name: str) -> ProviderConfig:
        return self.providers[name]

    @property
    def enabled_providers(self) -> list[ProviderConfig]:
        return [p for p in self.providers.values() if p.enabled]


DEFAULT_CONFIG: dict[str, Any] = {
    "omniroute": {"base_url": "http://127.0.0.1:20128/v1"},
    # Order = priority (output order and "--to todas"). Web providers stay
    # disabled until their session is pasted in the OmniRoute dashboard.
    "providers": {
        "qwen": {
            "model": "qwen-web/qwen3.8-max",
            "kind": "web",
            "enabled": False,
            "timeout_s": 240,
            "relogin_hint": "Panel OmniRoute > Providers > Qwen Web: pega de nuevo la cabecera Cookie completa de chat.qwen.ai",
        },
        "deepseek": {
            "model": "ds-web/deepseek-v4-pro",
            "kind": "web",
            "enabled": False,
            "timeout_s": 240,
            "relogin_hint": "Panel OmniRoute > Providers > DeepSeek Web: pega de nuevo el userToken de chat.deepseek.com",
        },
        "zai": {
            "model": "zai/glm-4.7-flash",
            "kind": "api",
            "enabled": False,
            "timeout_s": 180,
            "fallback_models": ["deepseek/deepseek-v4-flash"],
        },
        "meta": {
            "model": "ms-web/muse-spark",
            "kind": "web",
            "enabled": False,
            "timeout_s": 240,
            "relogin_hint": "Panel OmniRoute > Providers > Muse Spark Web: pega de nuevo ecto_1_sess y el token ecto1: de meta.ai",
        },
        "groq": {"model": "groq/openai/gpt-oss-120b", "kind": "api", "enabled": True, "timeout_s": 120},
        "nemotron": {"model": "openrouter/nvidia/nemotron-3-super-120b-a12b:free", "kind": "api",
                     "enabled": True, "timeout_s": 180},
        # OpenRouter's free GLM pool answered 429 model_cooldown on 2026-09-24.
        "glm-or": {"model": "openrouter/z-ai/glm-5.2:free", "kind": "api", "enabled": False, "timeout_s": 180},
    },
    "guard": {"min_spacing_s": 20, "daily_cap": 150, "cooldown_hours": 6},
    "blocked_model_prefixes": ["codex/", "cx/", "cxa/", "cc/", "cgpt", "gpt-"],
    "blocked_model_substrings": ["claude", "anthropic", "chatgpt", "codex"],
    "web_model_prefixes": [
        "qwen-web/", "deepseek-web/", "ds-web/", "muse-spark-web/", "ms-web/", "zai-web/", "zw/",
    ],
}


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def _coerce_providers(raw: Any) -> dict[str, ProviderConfig]:
    if not isinstance(raw, dict):
        raise ConfigError("'providers' must be a mapping of name -> settings")
    out: dict[str, ProviderConfig] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict) or not spec.get("model"):
            raise ConfigError(f"provider {name!r} needs at least a 'model'")
        kind = str(spec.get("kind", "api"))
        if kind not in ("api", "web"):
            raise ConfigError(f"provider {name!r}: kind must be 'api' or 'web'")
        out[str(name)] = ProviderConfig(
            name=str(name),
            model=str(spec["model"]),
            kind=kind,
            enabled=bool(spec.get("enabled", True)),
            timeout_s=float(spec.get("timeout_s", 180.0)),
            fallback_models=_as_tuple(spec.get("fallback_models")),
            relogin_hint=str(spec.get("relogin_hint", "")),
        )
    return out


def is_blocked_model(cfg: AppConfig, model: str) -> bool:
    """True when the model id is excluded (see AppConfig.blocked_model_*)."""
    m = model.strip().lower()
    if "/" not in m:
        return True
    if any(m.startswith(p.lower()) for p in cfg.blocked_model_prefixes):
        return True
    return any(s in m for s in cfg.blocked_model_substrings)


def load_config(data_dir: Path | None = None) -> AppConfig:
    """Load config from ``data/config.yaml``, creating it on first run.

    Resolution order (later overrides earlier):
      1. DEFAULT_CONFIG (only when the file has no such top-level key)
      2. data/config.yaml
      3. OMNIROUTE_BASE_URL environment variable
    """
    data_dir = (data_dir or DEFAULT_DATA_DIR).resolve()
    paths = Paths.from_data_dir(data_dir)
    paths.ensure()
    write_default_config(paths)

    merged: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
    with paths.config_file.open("r", encoding="utf-8") as fh:
        on_disk = yaml.safe_load(fh) or {}
    if not isinstance(on_disk, dict):
        raise ConfigError(f"{paths.config_file} must contain a mapping")
    merged.update(on_disk)

    base_url = os.getenv("OMNIROUTE_BASE_URL") or (merged.get("omniroute") or {}).get("base_url")
    guard_raw = merged.get("guard") or {}
    return AppConfig(
        paths=paths,
        base_url=str(base_url).rstrip("/"),
        providers=_coerce_providers(merged.get("providers")),
        guard=GuardConfig(
            min_spacing_s=float(guard_raw.get("min_spacing_s", 20)),
            daily_cap=int(guard_raw.get("daily_cap", 150)),
            cooldown_hours=float(guard_raw.get("cooldown_hours", 6)),
        ),
        blocked_model_prefixes=_as_tuple(merged.get("blocked_model_prefixes")),
        blocked_model_substrings=tuple(s.lower() for s in _as_tuple(merged.get("blocked_model_substrings"))),
        web_model_prefixes=_as_tuple(merged.get("web_model_prefixes")),
    )


def write_default_config(paths: Paths) -> None:
    """Write the default config file if it doesn't already exist."""
    if paths.config_file.exists():
        return
    paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    with paths.config_file.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(DEFAULT_CONFIG, fh, sort_keys=False, allow_unicode=True)
