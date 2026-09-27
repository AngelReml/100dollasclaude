"""Windows process boundary for the F11 code workshop.

This is the process boundary, not the approval policy. OpenCode tool approvals
and the command guard must be active before an agent is launched through it.
"""

from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
from pathlib import Path


MIN_C_FREE_BYTES = 10 * 1024**3
DEFAULT_JOB_MEMORY_BYTES = 2 * 1024**3
DEFAULT_CPU_PERCENT = 50


class WorkshopSafetyError(RuntimeError):
    pass


FORBIDDEN_COMMANDS = (
    (r"\b(runas|sudo|gsudo|psexec)\b|-verb\s+runas", "pide permisos de administrador"),
    (r"\b(shutdown|logoff|stop-computer|restart-computer|reboot|poweroff|halt)\b", "apaga, reinicia o cierra la sesion"),
    (r"\b(diskpart|bcdedit|bootrec|format-volume|clear-disk|remove-partition|initialize-disk|mkfs)\b|\bformat\s+[a-z]:|\bcipher\s+/w|\bdd\s+if=", "toca discos o el arranque"),
    (r"\brm\s+(-\w*r\w*f|-\w*f\w*r)|\b(rd|rmdir)\s+/s\b|\bdel\s+(/\w\s+)*/s\b|remove-item\b[^\n]*-recurse", "borra carpetas enteras"),
    (r"\breg(\.exe)?\s+(delete|add|import)\b|hklm:|hkey_local_machine", "cambia el registro del equipo"),
    (r"\b(taskkill|stop-process|pkill|killall)\b|\bkill\s+-9\b", "cierra programas"),
    (r"set-mppreference|enablelua|consentpromptbehavior|advfirewall\s+set|netsh\s+firewall|disable-computerrestore|vssadmin", "apaga una proteccion de Windows"),
    (r"\b(icacls|takeown|cacls)\b", "cambia permisos de archivos"),
)


def command_refusal(command: str) -> str | None:
    """Return the D24 refusal reason for a dangerous shell command."""
    for pattern, reason in FORBIDDEN_COMMANDS:
        if re.search(pattern, command, re.IGNORECASE):
            return reason
    return None


def preflight(*, minimum_free_bytes: int = MIN_C_FREE_BYTES) -> None:
    """Fail closed before launching any workshop process."""
    if os.name != "nt":
        raise WorkshopSafetyError("El taller F11 solo está disponible en Windows.")
    if ctypes.windll.shell32.IsUserAnAdmin():
        raise WorkshopSafetyError("No abras el taller como administrador.")

    import winreg

    key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as policy:
            enabled = winreg.QueryValueEx(policy, "EnableLUA")[0]
            prompt = winreg.QueryValueEx(policy, "ConsentPromptBehaviorAdmin")[0]
    except OSError as exc:
        raise WorkshopSafetyError("No pude comprobar el Control de cuentas de Windows.") from exc
    if enabled != 1 or prompt == 0:
        raise WorkshopSafetyError("Activa el Control de cuentas de Windows; no uses 'No notificarme nunca'.")

    system_drive = Path(os.environ.get("SystemDrive", "C:") + "\\")
    try:
        free = shutil.disk_usage(system_drive).free
    except OSError as exc:
        raise WorkshopSafetyError("No pude comprobar el espacio libre de C:.") from exc
    if free < minimum_free_bytes:
        raise WorkshopSafetyError("El taller se detiene: quedan menos de 10 GB libres en C:.")


class WindowsJob:
    """Own an unelevated process tree with hard memory/CPU caps."""

    def __init__(self, *, memory_bytes: int = DEFAULT_JOB_MEMORY_BYTES,
                 cpu_percent: int = DEFAULT_CPU_PERCENT):
        if os.name != "nt":
            raise WorkshopSafetyError("Los Job Objects requieren Windows.")
        if memory_bytes <= 0 or not 1 <= cpu_percent <= 100:
            raise ValueError("Límites de Job Object inválidos.")
        import win32job

        self._job = win32job.CreateJobObject(None, "")
        self._process = None
        self._thread = None
        try:
            limits = win32job.QueryInformationJobObject(self._job, win32job.JobObjectExtendedLimitInformation)
            limits["BasicLimitInformation"]["LimitFlags"] = (
                win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | win32job.JOB_OBJECT_LIMIT_JOB_MEMORY
            )
            limits["JobMemoryLimit"] = memory_bytes
            win32job.SetInformationJobObject(self._job, win32job.JobObjectExtendedLimitInformation, limits)

            class CpuRate(ctypes.Structure):
                _fields_ = [("ControlFlags", ctypes.c_uint32), ("CpuRate", ctypes.c_uint32)]

            cpu = CpuRate(0x1 | 0x4, cpu_percent * 100)  # ENABLE | HARD_CAP, in 1/100 percent units
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            set_info = kernel32.SetInformationJobObject
            set_info.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
            set_info.restype = ctypes.c_int
            if not set_info(int(self._job), 15, ctypes.byref(cpu), ctypes.sizeof(cpu)):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.close()
            raise

    def start(self, argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
        """Assign while suspended, so the child cannot run before limits apply."""
        if self._process is not None:
            raise WorkshopSafetyError("Este Job Object ya tiene un proceso principal.")
        if not argv or not cwd.is_dir():
            raise ValueError("Comando o carpeta de trabajo inválidos.")
        preflight()
        import win32api
        import win32job
        import win32process

        command = subprocess.list2cmdline(argv)
        process, thread, pid, _ = win32process.CreateProcess(
            None, command, None, None, False, win32process.CREATE_SUSPENDED,
            env or os.environ.copy(), str(cwd), win32process.STARTUPINFO(),
        )
        try:
            win32job.AssignProcessToJobObject(self._job, process)
            win32process.ResumeThread(thread)
        except BaseException:
            win32process.TerminateProcess(process, 1)
            win32api.CloseHandle(thread)
            win32api.CloseHandle(process)
            raise
        self._process, self._thread = process, thread
        return pid

    def wait(self, *, poll_seconds: float = 1.0) -> int:
        """Keep checking C: while the entire child tree is alive."""
        if self._process is None:
            raise WorkshopSafetyError("No hay proceso del taller en marcha.")
        import win32event
        import win32process

        try:
            while win32event.WaitForSingleObject(self._process, int(poll_seconds * 1000)) == win32event.WAIT_TIMEOUT:
                preflight()
            return win32process.GetExitCodeProcess(self._process)
        except BaseException:
            self.stop()
            raise

    def stop(self) -> None:
        if self._job is not None:
            import win32job

            win32job.TerminateJobObject(self._job, 1)

    def close(self) -> None:
        import win32api

        for name in ("_thread", "_process", "_job"):
            handle = getattr(self, name, None)
            if handle is not None:
                win32api.CloseHandle(handle)
                setattr(self, name, None)

    def __enter__(self) -> WindowsJob:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
