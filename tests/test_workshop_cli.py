"""F11 worktree creation and OpenCode policy tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from webllm_agent import workshop_cli


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def test_prepare_creates_a_linked_worktree_on_a_webllm_branch(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    git(repo, "add", "README.md")
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=webllm-test", "-c", "user.email=test@example.invalid",
         "commit", "-m", "initial"],
        check=True,
        text=True,
        capture_output=True,
    )

    target, branch = workshop_cli._worktree(repo)

    assert target.is_dir()
    assert branch.startswith("webllm/f11-")
    assert workshop_cli._is_linked_worktree(target)
    assert git(target, "branch", "--show-current") == branch
    assert not workshop_cli._is_linked_worktree(repo)


def test_opencode_v2_policy_starts_in_plan_and_denies_d24_commands():
    config = json.loads(workshop_cli.CONFIG.read_text(encoding="utf-8"))
    assert config["default_agent"] == "taller-plan"
    assert config["agents"]["taller-plan"]["permissions"][0]["effect"] == "deny"
    rules = config["permissions"]
    assert {"action": "edit", "resource": "*", "effect": "ask"} in rules
    assert {"action": "shell", "resource": "*shutdown*", "effect": "deny"} in rules
    assert {"action": "shell", "resource": "*Remove-Item *-Recurse*", "effect": "deny"} in rules
    assert {"action": "websearch", "resource": "*", "effect": "deny"} in rules
