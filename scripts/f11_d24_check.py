"""Run the six bounded D24 checks without performing destructive actions."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from webllm_agent.workshop_windows import WindowsJob, command_refusal, preflight


def line(ok: bool, text: str) -> None:
    print(("BIEN  " if ok else "FALLO ") + text)
    if not ok:
        raise SystemExit(1)


def protected_write(path: Path) -> int:
    code = "from pathlib import Path; Path(%r).write_text('webllm-f11-probe')" % str(path)
    with WindowsJob(memory_bytes=128 * 1024**2, cpu_percent=25) as job:
        job.start([sys.executable, "-c", code], cwd=Path(tempfile.gettempdir()))
        return job.wait(poll_seconds=0.05)


def main() -> int:
    preflight()
    windows_probe = Path(os.environ["SystemRoot"]) / "webllm-f11-probe.txt"
    program_probe = Path(os.environ["ProgramFiles"]) / "webllm-f11-probe.txt"
    line(protected_write(windows_probe) != 0 and not windows_probe.exists(), "1/6 Windows rechazo una escritura sin administrador")
    line(protected_write(program_probe) != 0 and not program_probe.exists(), "2/6 Archivos de programa rechazo una escritura sin administrador")
    line(command_refusal("shutdown /s /t 0") is not None, "3/6 apagar el PC se deniega antes de ejecutar")
    line(command_refusal("runas /user:Administrador cmd") is not None, "4/6 pedir administrador se deniega antes de ejecutar")
    try:
        preflight(minimum_free_bytes=10**30)
    except Exception as exc:
        line("espacio" in str(exc).lower() or "10 GB" in str(exc), "5/6 poco espacio impide arrancar")
    else:
        line(False, "5/6 poco espacio impide arrancar")
    code = "x=[]\nwhile True: x.append(bytearray(8*1024*1024))"
    with WindowsJob(memory_bytes=128 * 1024**2, cpu_percent=25) as job:
        job.start([sys.executable, "-c", code], cwd=Path(tempfile.gettempdir()))
        rc = job.wait(poll_seconds=0.05)
    line(rc != 0, "6/6 el tope de memoria paro el proceso")
    print("D24: 6/6 BIEN; no se ejecuto ninguna orden destructiva.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
