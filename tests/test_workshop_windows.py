"""The F11 process boundary uses harmless children; destructive cases need a VM."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

from webllm_agent import workshop_windows as workshop


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Job Object tests")


def test_preflight_rejects_low_disk(monkeypatch):
    monkeypatch.setattr(workshop.shutil, "disk_usage", lambda _path: SimpleNamespace(free=9 * 1024**3))
    with pytest.raises(workshop.WorkshopSafetyError, match="10 GB"):
        workshop.preflight()


def test_job_runs_unelevated_child(tmp_path):
    workshop.preflight()
    with workshop.WindowsJob(memory_bytes=256 * 1024**2, cpu_percent=25) as job:
        job.start([sys.executable, "-c", "raise SystemExit(7)"], cwd=tmp_path)
        assert job.wait(poll_seconds=0.05) == 7


def test_stop_terminates_child(tmp_path):
    workshop.preflight()
    with workshop.WindowsJob(memory_bytes=256 * 1024**2) as job:
        job.start([sys.executable, "-c", "import time; time.sleep(30)"], cwd=tmp_path)
        job.stop()
        assert job.wait(poll_seconds=0.05) != 0


@pytest.mark.parametrize("memory,cpu", [(0, 50), (1024, 0), (1024, 101)])
def test_invalid_limits_fail_closed(memory, cpu):
    with pytest.raises(ValueError):
        workshop.WindowsJob(memory_bytes=memory, cpu_percent=cpu)


@pytest.mark.parametrize(
    "command",
    [
        "shutdown /s /t 0",
        "runas /user:Administrator cmd",
        "diskpart /s wipe.txt",
        "Remove-Item C:\\data -Recurse -Force",
        "reg delete HKLM\\Software\\Example /f",
        "takeown /f C:\\Windows",
    ],
)
def test_d24_dangerous_commands_are_refused(command):
    assert workshop.command_refusal(command)


@pytest.mark.parametrize("command", ["git status --short", "python -m pytest -q", "npm test"])
def test_normal_project_commands_reach_the_approval_layer(command):
    assert workshop.command_refusal(command) is None
