"""Plain-Spanish entry point for the F11 code workshop on Windows."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .omniroute import load_api_key
from .workshop_windows import WindowsJob, WorkshopSafetyError, preflight


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "workshop" / "opencode.json"


def _run_git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return done.stdout.strip()


def _opencode() -> Path:
    found = shutil.which("opencode") or shutil.which("opencode.exe")
    if found:
        return Path(found)
    appdata = Path(os.environ.get("APPDATA", ""))
    candidate = appdata / "npm" / "node_modules" / "@opencode" / "cli" / "bin" / "opencode.exe"
    if candidate.is_file():
        return candidate
    raise WorkshopSafetyError("OpenCode v2 no esta instalado. Ejecuta npm install -g @opencode/cli.")


def _worktree(repo: Path) -> tuple[Path, str]:
    repo = Path(_run_git(repo, "rev-parse", "--show-toplevel"))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    branch = f"webllm/f11-{stamp}"
    target = repo.parent / f"{repo.name}-webllm-{stamp}"
    _run_git(repo, "worktree", "add", "-b", branch, str(target), "HEAD")
    return target, branch


def _is_linked_worktree(path: Path) -> bool:
    top = Path(_run_git(path, "rev-parse", "--show-toplevel")).resolve()
    common = Path(_run_git(path, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = (top / common).resolve()
    return common != (top / ".git").resolve()


def prepare(repo: Path) -> int:
    preflight()
    worktree, branch = _worktree(repo.resolve())
    print(f"Taller preparado en: {worktree}")
    print(f"Rama aislada: {branch}")
    print("El proyecto original no se modifica. Abre el taller con esa carpeta.")
    return 0


def new(repo: Path) -> int:
    preflight()
    worktree, branch = _worktree(repo.resolve())
    print(f"Rama aislada preparada: {branch}")
    print(f"Carpeta del taller: {worktree}")
    return start(worktree)


def start(worktree: Path) -> int:
    preflight()
    worktree = worktree.resolve()
    if not _is_linked_worktree(worktree):
        raise WorkshopSafetyError("Por seguridad, F11 solo arranca dentro de un git worktree aislado.")
    executable = _opencode()
    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = str(CONFIG)
    env["OMNIROUTE_API_KEY"] = load_api_key()
    print("Taller F11: empieza en taller-plan; cambia a taller-build solo cuando apruebes el plan.")
    print("Cada cambio y cada comando te pediran permiso. Ctrl+C ejecuta Parar todo.")
    with WindowsJob() as job:
        job.start([str(executable), "--standalone", str(worktree)], cwd=worktree, env=env)
        try:
            return job.wait(poll_seconds=1.0)
        except KeyboardInterrupt:
            print("Parando todo el arbol de procesos del taller...")
            job.stop()
            return 130


def status(path: Path) -> int:
    preflight()
    executable = _opencode()
    version = subprocess.run(
        [str(executable), "--version"], check=True, text=True, capture_output=True
    ).stdout.strip()
    free_gb = shutil.disk_usage(Path(os.environ.get("SystemDrive", "C:") + "\\")).free / 1024**3
    print(json.dumps({
        "preflight": "bien",
        "opencode": version,
        "config": str(CONFIG),
        "espacio_libre_c_gb": round(free_gb, 1),
        "worktree": _is_linked_worktree(path.resolve()) if (path / ".git").exists() else False,
    }, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Taller de codigo F11 protegido para Windows")
    sub = result.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("preparar", help="crear rama y worktree aislados")
    prep.add_argument("repo", type=Path)
    fresh = sub.add_parser("nuevo", help="crear el worktree y abrir el taller")
    fresh.add_argument("repo", type=Path)
    launch = sub.add_parser("abrir", help="abrir OpenCode dentro del worktree")
    launch.add_argument("worktree", type=Path)
    check = sub.add_parser("comprobar", help="comprobar las puertas de seguridad")
    check.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "preparar":
            return prepare(args.repo)
        if args.command == "nuevo":
            return new(args.repo)
        if args.command == "abrir":
            return start(args.worktree)
        return status(args.path)
    except (WorkshopSafetyError, subprocess.CalledProcessError, OSError, ValueError) as exc:
        print(f"NO SE ABRE EL TALLER: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
