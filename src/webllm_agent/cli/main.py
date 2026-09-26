"""`webllm` command-line entry point.

Subcommands:
    ask "<prompt>" --to todas|<name>|<model-id>   send to all providers or one
    cadena prueba|consejo|reparto|debate|cadena|archivo ...   run a chain of AIs
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
from .. import flows, vault
from ..config import AppConfig, ConfigError, load_config
from ..flows import FlowError
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

    ca = sub.add_parser("cadena", help="Run a chain of AIs where later steps use earlier answers")
    ca.add_argument("plantilla", choices=["prueba", "consejo", "reparto", "debate", "cadena", "archivo"],
                    help="prueba = example 'Reparto + integración' with 2 Chrome chats and 1 API AI")
    ca.add_argument("--pregunta", help="consejo / debate: the question")
    ca.add_argument("--ias", help="consejo: comma-separated AI names (default: every Chrome chat)")
    ca.add_argument("--juez", help="consejo: the judge (default: the first API AI)")
    ca.add_argument("--objetivo", help="reparto: the overall goal")
    ca.add_argument("--encargo", action="append", default=[], metavar="IA=TEXTO", help="reparto: one task per AI")
    ca.add_argument("--integra", help="reparto: the AI that joins the parts (default: the first API AI)")
    ca.add_argument("--a", help="debate: the AI that answers and corrects")
    ca.add_argument("--b", help="debate: the AI that looks for flaws")
    ca.add_argument("--vueltas", type=int, default=1, help="debate: rounds (1-5)")
    ca.add_argument("--entrada", help="cadena: the starting text")
    ca.add_argument("--eslabon", action="append", default=[], metavar="IA=INSTRUCCION",
                    help="cadena: one link per AI, in order")
    ca.add_argument("--ruta", type=Path, help="archivo: a chain saved as JSON")
    ca.add_argument("--gasto", action="store_true", help="only show how many messages each AI would get")
    ca.add_argument("--si", action="store_true", help="do not ask before sending")
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
    vault.export_run(cfg.paths, write_run(cfg.paths.runs_dir, run_id, prompt, outcomes),
                     labels={p.name: p.display for p in cfg.providers.values()})
    print(render(outcomes, run_id))
    vault.flush(30)  # this program ends now: the memory's writer must finish first
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


PROVEN_CHATS = ("zai-chat", "deepseek")


def _pairs(items: list[str], what: str) -> list[tuple[str, str]]:
    out = []
    for item in items:
        ai, sep, text = item.partition("=")
        if not sep or not ai.strip() or not text.strip():
            raise FlowError(f"Cada {what} va así: nombre-de-IA=texto (me llegó «{item}»).")
        out.append((ai.strip(), text.strip()))
    return out


def _build_flow(cfg: AppConfig, args: argparse.Namespace) -> flows.Flow:
    chats = [p.name for p in cfg.enabled_providers if p.kind == "browser"]
    apis = [p.name for p in cfg.enabled_providers if p.kind == "api"]
    if args.plantilla in ("prueba", "consejo", "reparto") and not (args.juez or args.integra) and not apis:
        raise FlowError("No hay ninguna IA por API activada para unir o juzgar (mira data/config.yaml).")
    if args.plantilla == "prueba":
        # Chats Iván has already seen answer in his Chrome (docs/ESTADO.md, 24-sep-2026) go first.
        chats.sort(key=lambda name: name not in PROVEN_CHATS)
        if len(chats) < 2:
            raise FlowError("La prueba necesita 2 chats de Chrome activados en data/config.yaml.")
        return flows.split_and_merge(cfg, "Comparar el café y el té para alguien que quiere dormir mejor. "
                                          "Respuestas cortas: máximo 120 palabras por parte.", [
            (chats[0], "Qué efectos tiene el café en el sueño y cuánto es razonable tomar."),
            (chats[1], "Qué efectos tiene el té (verde y negro) en el sueño y cuánto es razonable tomar."),
        ], apis[0])
    if args.plantilla == "consejo":
        council = [x.strip() for x in args.ias.split(",")] if args.ias else chats
        if not args.pregunta or len(council) < 2:
            raise FlowError("Consejo: pon --pregunta y al menos 2 IAs en --ias.")
        return flows.council_and_judge(cfg, args.pregunta, council, args.juez or apis[0])
    if args.plantilla == "reparto":
        if not args.objetivo or len(args.encargo) < 2:
            raise FlowError("Reparto: pon --objetivo y al menos 2 --encargo IA=texto.")
        return flows.split_and_merge(cfg, args.objetivo, _pairs(args.encargo, "encargo"), args.integra or apis[0])
    if args.plantilla == "debate":
        if not (args.pregunta and args.a and args.b):
            raise FlowError("Debate: pon --pregunta, --a y --b.")
        return flows.debate(cfg, args.pregunta, args.a, args.b, args.vueltas)
    if args.plantilla == "cadena":
        if not args.entrada or not args.eslabon:
            raise FlowError("Cadena: pon --entrada y al menos un --eslabon IA=instrucción.")
        return flows.chain(cfg, args.entrada, _pairs(args.eslabon, "eslabón"))
    if not args.ruta:
        raise FlowError("Archivo: pon --ruta con el archivo .json de la cadena.")
    return flows.load_flow(args.ruta)


def _print_event(ev: dict) -> None:
    kind = ev["type"]
    if kind == "step_start":
        print(f"\n>> {ev['title']}", flush=True)
    elif kind == "target_start":
        print(f"   {ev['label']} está escribiendo...", flush=True)
    elif kind == "target_wait":
        print(f"   {ev['label']} falló ({ev['error']}). Espero {ev['seconds']:.0f} s y lo reintento una vez.", flush=True)
    elif kind == "target_fallback":
        print(f"   {ev['label']} falló ({ev['error']}). Se lo pido a {ev['provider_label']}.", flush=True)
    elif kind == "target_done":
        if ev["ok"]:
            who = ev["provider_label"] if ev["provider"] == ev["target"] else f"{ev['provider_label']} (en lugar de {ev['label']})"
            print(f"   [OK] {who} respondió en {ev['seconds']} s", flush=True)
        else:
            print(f"   [FALLO] {ev['label']}: {ev['error']}", flush=True)
        for notice in ev.get("notices") or []:
            print(f"   >> {notice}", flush=True)
    elif kind == "step_done" and ev["status"] == "skipped":
        print(f"   (paso «{ev['step']}» sin hacer: la cadena se paró antes)", flush=True)


def _cmd_cadena(cfg: AppConfig, args: argparse.Namespace) -> int:
    try:
        flow = _build_flow(cfg, args)
        estimate = flows.estimate_messages(cfg, flow)
    except FlowError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    label = {p.name: p.display for p in cfg.providers.values()}
    spend = ", ".join(f"{label.get(n, n)} {c}" for n, c in estimate["normal"].items())
    print(f"Cadena «{flow.name}», {len(flow.steps)} pasos. Mensajes que gastará: {spend}.")
    extra = {n: c - estimate["normal"].get(n, 0) for n, c in estimate["worst"].items()
             if c > estimate["normal"].get(n, 0)}
    if extra:
        print("Si algo falla, como mucho: " + ", ".join(f"{label.get(n, n)} +{c}" for n, c in extra.items()) + ".")
    if args.gasto:
        return 0
    if not args.si and sys.stdin.isatty():
        if input("Pulsa Enter para empezar (o escribe n y Enter para cancelar): ").strip().lower() in ("n", "no"):
            print("Cancelado. No se ha enviado nada.")
            return 0
    try:
        api_key = load_api_key()
    except OmniRouteKeyMissing:
        api_key = ""
    bridge_key = load_token(cfg.paths.state_dir)
    try:
        run = asyncio.run(flows.run_flow(cfg, flow, api_key=api_key, guard=_guard(cfg), bridge_key=bridge_key,
                                         emit=_print_event))
    except (FlowError, GatewayError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    last = run.steps[flow.steps[-1].id]
    print()
    if last.answers:
        print("=" * 30 + f" RESULTADO FINAL ({flow.steps[-1].title or flow.steps[-1].id}) " + "=" * 30)
        print(flows.combined_answer(cfg, last).rstrip())
    verdict = {"ok": "todo bien", "partial": "terminada, pero alguna IA no respondió",
               "stopped": "PARADA: un paso se quedó sin ninguna respuesta"}[run.status]
    print(f"\nCadena {verdict}.")
    print(f"Registro: data/runs/{run.run_id}/  ·  Candado: "
          + ("VERDE (nadie lo ha tocado)" if run.verified else "ROJO (el registro no cuadra)"))
    vault.flush(30)  # this program ends now: the memory's writer must finish first
    return 0 if run.status == "ok" and run.verified else 1


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
    if args.command == "cadena":
        return _cmd_cadena(cfg, args)
    if args.command == "probar":
        from ..selftest import run as run_selftest
        return run_selftest(cfg)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
