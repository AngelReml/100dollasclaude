"""`webllm` command-line entry point.

Phase 0 subcommands:
    doctor               smoke-test the BrowserManager (open Chromium, close cleanly)
    --version            print version

Phase 1 subcommands (added when the vertical slice lands):
    login <provider>     open the persistent profile so the user can authenticate
    chat [provider]      send a single message and print the response
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from .. import __version__
from ..browser.manager import BrowserError, BrowserManager
from ..config import AppConfig, load_config, write_default_config
from ..observability.logging import get_logger, setup_logging

log = get_logger("cli")


# ----------------------------------------------------------------------- helpers

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="webllm",
        description=(
            "Local coding-agent runtime whose LLM transport is a web UI. "
            "BrowserManager + Provider adapters + Agent Engine."
        ),
    )
    p.add_argument("--version", action="version", version=f"webllm-agent {__version__}")
    p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the runtime data directory (default: ./data in the project root)",
    )
    p.add_argument("--debug", action="store_true", help="Verbose logging + debug artefacts")
    p.add_argument(
        "--headless",
        action="store_true",
        help="Launch the browser headless (default: visible so you can log in)",
    )
    p.add_argument(
        "--cdp-url",
        default=None,
        help=(
            "Connect to an existing Chrome over CDP instead of launching a new "
            "browser (e.g. http://localhost:9222). Requires Chrome to have been "
            "started with --remote-debugging-port=9222."
        ),
    )

    sub = p.add_subparsers(dest="command", required=False)

    sub.add_parser(
        "doctor",
        help="Phase 0 smoke-test: open a Chromium context, close cleanly",
    )

    sub.add_parser(
        "config",
        help="Print the resolved configuration and exit",
    )

    login = sub.add_parser(
        "login",
        help="Open the persistent browser for a provider so you can log in",
    )
    login.add_argument("provider", help="Provider name (e.g. claude, chatgpt, gemini, grok)")

    chat = sub.add_parser(
        "chat",
        help="Phase 1 vertical slice: send a single message and print the response",
    )
    chat.add_argument("message", nargs="+", help="Message to send (joined with spaces)")
    chat.add_argument(
        "--provider",
        default=None,
        help="Provider name (default: config default_provider)",
    )
    chat.add_argument(
        "--new",
        action="store_true",
        help="Force a new conversation instead of resuming the last one",
    )

    return p


def _resolve_config(args: argparse.Namespace) -> AppConfig:
    cfg = load_config(args.data_dir)
    if args.debug:
        # Mutate a frozen dataclass via object.__setattr__ (we own this AppConfig instance).
        object.__setattr__(cfg, "debug", True)
    if args.headless:
        object.__setattr__(cfg, "headless", True)
    if args.cdp_url:
        object.__setattr__(cfg, "cdp_url", args.cdp_url)
    write_default_config(cfg.paths)
    return cfg


# --------------------------------------------------------------------- commands

async def _cmd_doctor(cfg: AppConfig) -> int:
    """Phase 0 acceptance test.

    Boots a Chromium context, opens a tab pointing at about:blank,
    asserts the browser is alive, then closes everything cleanly.
    """
    log.info("doctor: launching browser manager")
    bm = BrowserManager(cfg)
    try:
        await bm.start()
        page = await bm.get_page("claude")
        await page.goto("about:blank")
        title = await page.title()
        log.info("doctor: page title = %r", title)
        ctx = await bm.get_context("claude")
        log.info(
            "doctor: persistent profile at %s — OK",
            cfg.paths.browser_profiles_dir / "claude",
        )
        log.info("doctor: contexts open = %d", len(ctx.pages))
        log.info("doctor: PASS")
        return 0
    except BrowserError as exc:
        log.error("doctor: FAIL — %s", exc)
        return 1
    finally:
        await bm.close()


def _cmd_config(cfg: AppConfig) -> int:
    out = {
        "version": __version__,
        "data_dir": str(cfg.paths.data_dir),
        "browser_profiles_dir": str(cfg.paths.browser_profiles_dir),
        "default_provider": cfg.default_provider,
        "headless": cfg.headless,
        "debug": cfg.debug,
        "providers": {
            name: {"enabled": p.enabled, "max_concurrency": p.max_concurrency}
            for name, p in cfg.providers.items()
        },
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


async def _cmd_login(cfg: AppConfig, provider: str) -> int:
    """Open the persistent browser at the provider's home URL.

    The user logs in manually; the session is persisted in the
    provider-specific Chromium profile. Subsequent runs reuse it.
    """
    from ..conversations.manager import ConversationManager
    from ..providers.claude import ClaudeProvider

    if provider not in cfg.providers:
        log.error(
            "unknown provider %r. Available: %s",
            provider,
            ", ".join(sorted(cfg.providers)),
        )
        return 2
    bm = BrowserManager(cfg)
    convs = ConversationManager(cfg.paths.state_dir)
    provider_impl = ClaudeProvider(cfg, bm, convs)
    try:
        await bm.start()
        await provider_impl.login_interactive(provider)
        log.info("login: profile saved for provider=%s", provider)
        return 0
    except BrowserError as exc:
        log.error("login: FAIL — %s", exc)
        return 1
    finally:
        await bm.close()


async def _cmd_chat(cfg: AppConfig, message_parts: Sequence[str], provider: str | None, new: bool) -> int:
    """Phase 1 vertical slice: CLI → Backend → ClaudeProvider → Browser → CLI."""
    from ..backend.webllm_backend import WebLLMBackend
    from ..providers.base import SessionExpired, ProviderError

    provider_name = provider or cfg.default_provider
    prompt = " ".join(message_parts).strip()
    if not prompt:
        log.error("chat: empty message")
        return 2

    bm = BrowserManager(cfg)
    backend = WebLLMBackend(cfg, bm)
    try:
        await bm.start()
        resp = await backend.ask(
            prompt=prompt,
            provider=provider_name,
            new_chat=new,
        )
        print()
        print(resp.text)
        print()
        log.info("chat: response ready (provider=%s, model=%s)", resp.provider, resp.model)
        return 0
    except SessionExpired:
        log.error(
            "chat: %s session expired or never logged in. "
            "Run: webllm login %s",
            provider_name,
            provider_name,
        )
        return 3
    except ProviderError as exc:
        log.error("chat: provider error — %s", exc)
        return 1
    except BrowserError as exc:
        log.error("chat: browser error — %s", exc)
        return 1
    finally:
        await bm.close()


# ----------------------------------------------------------------------- entry

def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cfg = _resolve_config(args)
    setup_logging(cfg.paths, debug=cfg.debug)

    cmd = args.command
    if cmd is None or cmd == "doctor":
        return asyncio.run(_cmd_doctor(cfg))
    if cmd == "config":
        return _cmd_config(cfg)
    if cmd == "login":
        return asyncio.run(_cmd_login(cfg, args.provider))
    if cmd == "chat":
        return asyncio.run(
            _cmd_chat(cfg, args.message, args.provider, args.new)
        )
    parser.error(f"unknown command: {cmd}")
    return 2  # unreachable


if __name__ == "__main__":
    raise SystemExit(main())
