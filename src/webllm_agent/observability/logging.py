"""Logging setup.

Single `setup_logging(paths, level, debug)` call from the CLI / main entry points.
Uses `rich` for pretty console output when available; falls back to plain stdout.
File handler always emits plain text (rich console + plain file = both readable).
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from ..config import Paths

_DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    paths: Paths,
    *,
    level: int = logging.INFO,
    debug: bool = False,
    log_file_name: str = "webllm.log",
) -> logging.Logger:
    """Configure root logger + a `webllm_agent` namespace logger.

    Idempotent: subsequent calls only update the level, they don't duplicate handlers.
    """
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    effective_level = logging.DEBUG if debug else level

    root = logging.getLogger()
    root.setLevel(effective_level)
    # Strip pre-existing handlers (e.g. basicConfig from a parent test runner)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(_DEFAULT_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(effective_level)
    root.addHandler(console)

    log_path = paths.logs_dir / log_file_name
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(effective_level)
    root.addHandler(file_handler)

    # Quiet down chatty third-party loggers unless DEBUG is on
    if not debug:
        for noisy in ("asyncio", "playwright", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    log = logging.getLogger("webllm_agent")
    log.debug("logging initialized at %s (level=%s)", log_path, logging.getLevelName(effective_level))
    return log


def get_logger(name: str) -> logging.Logger:
    """Namespace logger under `webllm_agent.<name>`."""
    return logging.getLogger(f"webllm_agent.{name}")


def log_path(paths: Paths, name: str = "webllm.log") -> Path:
    return paths.logs_dir / name
