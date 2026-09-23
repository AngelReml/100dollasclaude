"""`webllm` command-line entry point.

Subcommands:
    config      print the resolved configuration and exit
    --version   print version
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .. import __version__
from ..config import AppConfig, load_config


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="webllm",
        description="Send one prompt to your AI providers through OmniRoute.",
    )
    p.add_argument("--version", action="version", version=f"webllm-agent {__version__}")
    p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the runtime data directory (default: ./data in the project root)",
    )
    sub = p.add_subparsers(dest="command", required=False)
    sub.add_parser("config", help="Print the resolved configuration and exit")
    return p


def _cmd_config(cfg: AppConfig) -> int:
    out = {
        "version": __version__,
        "data_dir": str(cfg.paths.data_dir),
        "default_provider": cfg.default_provider,
        "providers": {
            name: {"enabled": p.enabled, "max_concurrency": p.max_concurrency}
            for name, p in cfg.providers.items()
        },
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(args.data_dir)
    if args.command == "config":
        return _cmd_config(cfg)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
