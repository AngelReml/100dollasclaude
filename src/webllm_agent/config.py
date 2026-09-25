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
import json
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


# Human names for the default providers (data/config.yaml can set "label").
DEFAULT_LABELS = {
    "qwen": "Qwen", "deepseek": "DeepSeek", "zai-chat": "z.ai (chat)", "meta": "Meta AI",
    "zai": "z.ai", "groq": "groq", "nemotron": "Nemotron",
}


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    # "browser" = a chat page in your Chrome, driven by the extension through
    #             the local bridge (the bridge applies the account guard);
    # "web"     = OmniRoute cookie provider (webllm's own guard applies);
    # "api"     = an API key or keyless API.
    kind: str = "api"
    # Which local endpoint serves it: "omniroute" (:20128) or "bridge" (:20130).
    gateway: str = "omniroute"
    enabled: bool = True
    timeout_s: float = 180.0
    # Tried in order when the primary model fails (not after a guard trip).
    fallback_models: tuple[str, ...] = ()
    # The dashboard step Iván must redo when this provider's session expires.
    relogin_hint: str = ""
    # Name shown to Iván (default: DEFAULT_LABELS, else the provider name).
    label: str = ""
    # gateway "local" only: the server's own address and the model id it knows.
    base_url: str = ""
    remote_model: str = ""
    # A chat site Iván added from the app ("+ Añadir otra IA"): its address.
    url: str = ""
    custom: bool = False

    @property
    def guarded(self) -> bool:
        return self.kind == "web"

    @property
    def display(self) -> str:
        return self.label or DEFAULT_LABELS.get(self.name, self.name)


@dataclass(frozen=True)
class LocalServer:
    """An AI program on this PC with an OpenAI-style API (see local.py)."""

    key: str
    name: str
    url: str
    start: tuple[str, ...] = ()  # command that starts it; default: found for LM Studio / Ollama


DEFAULT_LOCAL_SERVERS = (
    LocalServer("lmstudio", "LM Studio", "http://127.0.0.1:1234/v1"),
    LocalServer("ollama", "Ollama", "http://127.0.0.1:11434/v1"),
)


@dataclass(frozen=True)
class GuardConfig:
    min_spacing_s: float = 20.0
    daily_cap: int = 150
    cooldown_hours: float = 6.0


@dataclass(frozen=True)
class AppConfig:
    paths: Paths
    base_url: str
    bridge_port: int = 20130
    bridge_timeout_s: float = 300.0
    providers: dict[str, ProviderConfig] = field(default_factory=dict)  # priority order
    guard: GuardConfig = field(default_factory=GuardConfig)
    # Claude / ChatGPT / Codex are excluded from this tool: model ids starting
    # with one of these prefixes, or containing one of these substrings, or with
    # no "provider/" prefix at all, are refused.
    blocked_model_prefixes: tuple[str, ...] = ()
    blocked_model_substrings: tuple[str, ...] = ()
    # Model ids that belong to guarded web providers even when passed raw to --to.
    web_model_prefixes: tuple[str, ...] = ()
    # AI programs on this PC whose models show as "En tu PC" (load_config adds LM Studio and Ollama).
    local_servers: tuple[LocalServer, ...] = ()

    def provider(self, name: str) -> ProviderConfig:
        return self.providers[name]

    @property
    def bridge_url(self) -> str:
        return f"http://127.0.0.1:{self.bridge_port}/v1"

    @property
    def enabled_providers(self) -> list[ProviderConfig]:
        return [p for p in self.providers.values() if p.enabled]


DEFAULT_CONFIG: dict[str, Any] = {
    "omniroute": {"base_url": "http://127.0.0.1:20128/v1"},
    "bridge": {"port": 20130, "timeout_s": 300},
    # Order = priority (output order and "--to todas").
    # browser = the chat pages in your Chrome (extension + bridge);
    # api = through OmniRoute.
    "providers": {
        "qwen": {"model": "browser/qwen", "kind": "browser", "gateway": "bridge", "timeout_s": 420},
        "deepseek": {"model": "browser/deepseek", "kind": "browser", "gateway": "bridge", "timeout_s": 420},
        "zai-chat": {"model": "browser/zai", "kind": "browser", "gateway": "bridge", "timeout_s": 420},
        "meta": {"model": "browser/meta", "kind": "browser", "gateway": "bridge", "timeout_s": 420},
        "zai": {"model": "zai/glm-4.7-flash", "kind": "api", "enabled": True, "timeout_s": 180},
        "groq": {"model": "groq/openai/gpt-oss-120b", "kind": "api", "enabled": True, "timeout_s": 120},
        "nemotron": {"model": "openrouter/nvidia/nemotron-3-super-120b-a12b:free", "kind": "api",
                     "enabled": True, "timeout_s": 180},
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
        if kind not in ("api", "web", "browser"):
            raise ConfigError(f"provider {name!r}: kind must be 'api', 'web' or 'browser'")
        gateway = str(spec.get("gateway", "bridge" if kind == "browser" else "omniroute"))
        if gateway not in ("omniroute", "bridge"):
            raise ConfigError(f"provider {name!r}: gateway must be 'omniroute' or 'bridge'")
        out[str(name)] = ProviderConfig(
            name=str(name),
            model=str(spec["model"]),
            kind=kind,
            gateway=gateway,
            enabled=bool(spec.get("enabled", True)),
            timeout_s=float(spec.get("timeout_s", 180.0)),
            fallback_models=_as_tuple(spec.get("fallback_models")),
            relogin_hint=str(spec.get("relogin_hint", "")),
            label=str(spec.get("label", "")),
        )
    return out


def _coerce_local_servers(raw: Any) -> tuple[LocalServer, ...]:
    servers = {s.key: s for s in DEFAULT_LOCAL_SERVERS}
    if raw is None:
        return tuple(servers.values())
    if not isinstance(raw, list):
        raise ConfigError("'local_servers' must be a list of {key, name, url, start}")
    for spec in raw:
        if not isinstance(spec, dict) or not spec.get("key"):
            raise ConfigError("each local server needs a 'key'")
        key = str(spec["key"])
        if spec.get("enabled") is False:  # e.g. {key: ollama, enabled: false}
            servers.pop(key, None)
            continue
        if not spec.get("url"):
            raise ConfigError(f"local server {key!r} needs a 'url'")
        servers[key] = LocalServer(key=key, name=str(spec.get("name") or key), url=str(spec["url"]).rstrip("/"),
                                   start=_as_tuple(spec.get("start")))
    return tuple(servers.values())


CUSTOM_AIS_FILE = "custom_ais.json"
# One message to a chat in the browser never waits longer than this, even while Iván solves
# verifications (the extension waits 5 minutes for each one; see bridge.py).
JOB_HARD_CAP_S = 30 * 60.0


def _with_custom(configured: dict[str, ProviderConfig], paths: Paths) -> dict[str, ProviderConfig]:
    """Configured providers first (priority order), then the sites added from the app."""
    extra = {k: v for k, v in load_custom_ais(paths).items() if k not in configured}
    return {**configured, **extra}


def load_custom_ais(paths: Paths) -> dict[str, ProviderConfig]:
    """Chat sites added from the app. They live in data/state/ (not in git) so ACTUALIZAR never conflicts."""
    path = paths.state_dir / CUSTOM_AIS_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, ProviderConfig] = {}
    for key, spec in (raw.items() if isinstance(raw, dict) else []):
        if isinstance(spec, dict) and spec.get("url"):
            out[str(key)] = custom_provider(str(key), str(spec.get("name") or key), str(spec["url"]))
    return out


def custom_provider(key: str, name: str, url: str) -> ProviderConfig:
    return ProviderConfig(name=key, model=f"browser/{key}", kind="browser", gateway="bridge", timeout_s=420.0,
                          label=name, url=url, custom=True)


def save_custom_ai(paths: Paths, key: str, name: str, url: str) -> None:
    path = paths.state_dir / CUSTOM_AIS_FILE
    data = {k: {"name": p.label, "url": p.url} for k, p in load_custom_ais(paths).items()}
    data[key] = {"name": name, "url": url}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def remove_custom_ai(paths: Paths, key: str) -> bool:
    current = load_custom_ais(paths)
    if key not in current:
        return False
    data = {k: {"name": p.label, "url": p.url} for k, p in current.items() if k != key}
    (paths.state_dir / CUSTOM_AIS_FILE).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


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
    bridge_raw = merged.get("bridge") or {}
    return AppConfig(
        paths=paths,
        base_url=str(base_url).rstrip("/"),
        bridge_port=int(bridge_raw.get("port", 20130)),
        bridge_timeout_s=float(bridge_raw.get("timeout_s", 300)),
        providers=_with_custom(_coerce_providers(merged.get("providers")), paths),
        guard=GuardConfig(
            min_spacing_s=float(guard_raw.get("min_spacing_s", 20)),
            daily_cap=int(guard_raw.get("daily_cap", 150)),
            cooldown_hours=float(guard_raw.get("cooldown_hours", 6)),
        ),
        blocked_model_prefixes=_as_tuple(merged.get("blocked_model_prefixes")),
        blocked_model_substrings=tuple(s.lower() for s in _as_tuple(merged.get("blocked_model_substrings"))),
        web_model_prefixes=_as_tuple(merged.get("web_model_prefixes")),
        local_servers=_coerce_local_servers(merged.get("local_servers")),
    )


def write_default_config(paths: Paths) -> None:
    """Write the default config file if it doesn't already exist."""
    if paths.config_file.exists():
        return
    paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    with paths.config_file.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(DEFAULT_CONFIG, fh, sort_keys=False, allow_unicode=True)
