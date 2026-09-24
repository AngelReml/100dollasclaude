"""`webllm` command-line entry point.

Subcommands:
    ask "<prompt>" --to todas|<name>|<model-id>   send to all providers or one
    journal verify [RUN_ID] [--all]               check the hash chain of runs
    status                                        providers, models, guard state
    guard clear <name>                            lift a cooldown after fixing a session
    config                                        print the resolved configuration
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .. import __version__
from ..broadcaster import (
    GatewayError, TargetError, broadcast, new_run_id, render, resolve_targets, verify_run, write_run,
)
from ..bridge import SITES, call_admin, load_token
from ..bridge import serve as serve_bridge
from ..config import AppConfig, ConfigError, load_config
from ..guard import Guard
from ..omniroute import OmniRouteKeyMissing, load_api_key


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="webllm",
        description="Send one prompt to your AI providers through OmniRoute.",
    )
    p.add_argument("--version", action="version", version=f"webllm-agent {__version__}")
    p.add_argument("--data-dir", type=Path, default=None,
                   help="Override the runtime data directory (default: ./data in the project root)")
    sub = p.add_subparsers(dest="command", required=False)

    ask = sub.add_parser("ask", help="Send a prompt to all providers or to one")
    ask.add_argument("prompt", nargs="?", help="The prompt text (or use --file)")
    ask.add_argument("--to", default="todas", help="todas | a provider name from data/config.yaml | a model id")
    ask.add_argument("--file", type=Path, help="Read the prompt from this UTF-8 file")
    ask.add_argument("--timeout", type=float, default=None, help="Per-provider timeout in seconds")

    j = sub.add_parser("journal", help="Journal tools")
    jsub = j.add_subparsers(dest="journal_command", required=True)
    v = jsub.add_parser("verify", help="Recompute the hash chain of a run's journal")
    v.add_argument("run", nargs="?", help="Run id or path to a run folder / journal.jsonl (default: latest)")
    v.add_argument("--all", action="store_true", help="Verify every run under data/runs")

    sub.add_parser("status", help="Show providers, models and account-guard state")

    g = sub.add_parser("guard", help="Account guard tools")
    gsub = g.add_subparsers(dest="guard_command", required=True)
    gc = gsub.add_parser("clear", help="Lift the cooldown of a provider (after fixing its session)")
    gc.add_argument("name")

    sub.add_parser("config", help="Print the resolved configuration and exit")

    pu = sub.add_parser("puente", help="Bridge to the AI chats open in your Chrome")
    pu.add_argument("accion", nargs="?", default="arrancar",
                    choices=["arrancar", "reanudar", "diagnosticar", "estado"])
    pu.add_argument("sitio", nargs="?", help="qwen | deepseek | zai | meta")

    sub.add_parser("probar", help="Check everything for real and say BIEN / MAL per item")
    return p


def _guard(cfg: AppConfig) -> Guard:
    return Guard(cfg.paths.state_dir / "guard.json", cfg.guard)


def _cmd_ask(cfg: AppConfig, args: argparse.Namespace) -> int:
    if args.file:
        prompt = args.file.read_text(encoding="utf-8")
    elif args.prompt:
        prompt = args.prompt
    elif sys.stdin.isatty():
        prompt, args.to = _ask_interactively(cfg, args.to)
    else:
        print("Falta el prompt: webllm ask \"tu pregunta\" --to todas", file=sys.stderr)
        return 2
    if not prompt.strip():
        print("El prompt está vacío.", file=sys.stderr)
        return 2
    try:
        targets = resolve_targets(cfg, args.to)
        api_key = load_api_key()
    except (TargetError, OmniRouteKeyMissing) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    names = ", ".join(t.name for t in targets)
    print(f"Enviando a: {names}", flush=True)
    bridge_key = load_token(cfg.paths.state_dir) if any(t.gateway == "bridge" for t in targets) else None
    try:
        outcomes = asyncio.run(broadcast(cfg, prompt, targets, api_key=api_key, guard=_guard(cfg),
                                         timeout_s=args.timeout, notify=lambda m: print(m, flush=True),
                                         bridge_key=bridge_key))
    except GatewayError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    run_id = new_run_id()
    write_run(cfg.paths.runs_dir, run_id, prompt, outcomes)
    print(render(outcomes, run_id))
    return 0 if any(o.result.ok for o in outcomes) else 1


def _ask_interactively(cfg: AppConfig, default_to: str) -> tuple[str, str]:
    """Prompt for the question and the destination (used by preguntar.cmd)."""
    print("Escribe tu pregunta. Para terminar, deja una línea vacía y pulsa Enter:")
    lines: list[str] = []
    while True:
        line = input()
        if not line and lines:
            break
        lines.append(line)
    names = ["todas", *[p.name for p in cfg.enabled_providers]]
    to = input(f"¿A quién? ({' / '.join(names)}) [Enter = {default_to}]: ").strip() or default_to
    return "\n".join(lines), to


def _resolve_run_dir(cfg: AppConfig, run: str | None) -> Path | None:
    if run:
        p = Path(run)
        if p.name == "journal.jsonl":
            return p.parent
        if p.is_dir():
            return p
        return cfg.paths.runs_dir / run
    runs = sorted(d for d in cfg.paths.runs_dir.iterdir() if (d / "journal.jsonl").exists())
    return runs[-1] if runs else None


def _cmd_journal_verify(cfg: AppConfig, args: argparse.Namespace) -> int:
    if args.all:
        dirs = sorted(d for d in cfg.paths.runs_dir.iterdir() if (d / "journal.jsonl").exists())
    else:
        d = _resolve_run_dir(cfg, args.run)
        dirs = [d] if d else []
    if not dirs:
        print("No hay registros que verificar.", file=sys.stderr)
        return 2
    bad = 0
    for d in dirs:
        res = verify_run(d)
        if res.ok:
            print(f"OK      {d.name}: {res.lines} líneas, cadena intacta")
        else:
            bad += 1
            print(f"ROTO    {d.name}: primera línea mala = {res.first_bad_line} ({res.reason})")
    return 1 if bad else 0


def _cmd_puente(cfg: AppConfig, args: argparse.Namespace) -> int:
    if args.accion == "arrancar":
        serve_bridge(cfg, cfg.bridge_port, cfg.bridge_timeout_s)
        return 0
    token = load_token(cfg.paths.state_dir)
    try:
        if args.accion == "reanudar":
            # Pauses live in a file, so this works even with the bridge stopped.
            g = Guard(cfg.paths.state_dir / "bridge_guard.json", cfg.guard)
            cleared = [s for s in ([args.sitio] if args.sitio else list(SITES)) if g.clear(s)]
            print("Reanudado: " + (", ".join(cleared) if cleared else "no había nada en pausa."))
            return 0
        elif args.accion == "diagnosticar":
            if args.sitio not in SITES:
                print("Indica el sitio: " + ", ".join(SITES), file=sys.stderr)
                return 2
            code, body = asyncio.run(call_admin(cfg.bridge_port, token, "/admin/diagnose", {"site": args.sitio}))
            print(body.get("text") if isinstance(body, dict) and body.get("ok") else body)
        else:
            import httpx
            r = httpx.get(f"http://127.0.0.1:{cfg.bridge_port}/status",
                          headers={"Authorization": f"Bearer {token}"}, timeout=10)
            code, body = r.status_code, r.json()
            print(json.dumps(body, indent=2, ensure_ascii=False))
    except Exception as exc:  # bridge not running
        print(f"El puente no responde ({type(exc).__name__}). Haz doble clic en 2 - PROBAR TODO (lo enciende solo)", file=sys.stderr)
        return 3
    return 0 if code == 200 else 1


def _cmd_status(cfg: AppConfig) -> int:
    state = _guard(cfg).status()
    bridge_state = Guard(cfg.paths.state_dir / "bridge_guard.json", cfg.guard).status()
    now = datetime.now().timestamp()
    print("Proveedores (en orden de prioridad):")
    for p in cfg.providers.values():
        st = bridge_state.get(p.model.split("/", 1)[-1], {}) if p.gateway == "bridge" else state.get(p.name, {})
        flags = []
        if not p.enabled:
            flags.append("desactivado")
        if p.guarded or p.gateway == "bridge":
            until = st.get("cooldown_until")
            if until and until > now:
                flags.append(f"EN PAUSA hasta {datetime.fromtimestamp(until):%d/%m %H:%M} ({st.get('cooldown_reason', '')})")
            if st.get("day") == datetime.now().strftime("%Y-%m-%d"):
                flags.append(f"hoy {st.get('count_today', 0)}/{cfg.guard.daily_cap}")
        fb = f"  respaldo: {', '.join(p.fallback_models)}" if p.fallback_models else ""
        print(f"  {p.name:<10} {p.kind:<4} {p.model}{fb}  {'; '.join(flags)}")
    return 0


def _cmd_config(cfg: AppConfig) -> int:
    out = {
        "version": __version__,
        "data_dir": str(cfg.paths.data_dir),
        "base_url": cfg.base_url,
        "providers": {
            name: {"model": p.model, "kind": p.kind, "enabled": p.enabled, "timeout_s": p.timeout_s,
                   "fallback_models": list(p.fallback_models)}
            for name, p in cfg.providers.items()
        },
        "guard": vars(cfg.guard),
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.data_dir)
    except ConfigError as exc:
        print(f"Configuración inválida: {exc}", file=sys.stderr)
        return 2
    if args.command == "ask":
        return _cmd_ask(cfg, args)
    if args.command == "journal":
        return _cmd_journal_verify(cfg, args)
    if args.command == "status":
        return _cmd_status(cfg)
    if args.command == "guard":
        cleared = _guard(cfg).clear(args.name)
        print(f"{args.name}: pausa levantada." if cleared else f"{args.name}: no estaba en pausa.")
        return 0
    if args.command == "config":
        return _cmd_config(cfg)
    if args.command == "puente":
        return _cmd_puente(cfg, args)
    if args.command == "probar":
        from ..selftest import run as run_selftest
        return run_selftest(cfg)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
