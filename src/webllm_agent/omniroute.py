"""OmniRoute connection settings.

The API key is read at runtime from OmniRoute's own `.env`
(``~/.omniroute/.env``) and is never written anywhere else. Use
:func:`mask` whenever a key has to appear in output.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:20128/v1"
DEFAULT_ENV_FILE = Path.home() / ".omniroute" / ".env"


class OmniRouteKeyMissing(RuntimeError):
    """OMNIROUTE_API_KEY is not set and not present in OmniRoute's .env."""


def read_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file (comments and blanks ignored)."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_api_key(env_file: Path | None = None) -> str:
    """Return the OmniRoute API key: process env first, then OmniRoute's .env."""
    if key := os.getenv("OMNIROUTE_API_KEY"):
        return key
    key = read_env_file(env_file or DEFAULT_ENV_FILE).get("OMNIROUTE_API_KEY", "")
    if not key:
        raise OmniRouteKeyMissing(
            f"OMNIROUTE_API_KEY not found in environment or {env_file or DEFAULT_ENV_FILE}"
        )
    return key


def base_url() -> str:
    return os.getenv("OMNIROUTE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def mask(secret: str) -> str:
    """Render a secret as its first 4 characters plus ``***``."""
    return (secret[:4] + "***") if secret else "<empty>"
