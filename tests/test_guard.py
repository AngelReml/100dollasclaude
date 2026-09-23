"""Account-guard tests: every branch, plus persistence across restarts (no network)."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import GOOD_KEY, make_config
from webllm_agent.broadcaster import broadcast, render, resolve_targets
from webllm_agent.client import ChatResult
from webllm_agent.config import GuardConfig, ProviderConfig
from webllm_agent.guard import CHALLENGE, RATE_LIMIT, SESSION, Guard, GuardBlocked, classify_trip

ROOT = Path(__file__).resolve().parents[1]
WEB = dict(kind="web", relogin_hint="Panel OmniRoute > Providers > X: pega de nuevo la sesión")


class FakeTime:
    def __init__(self, start: float = 1_800_000_000.0):
        self.now = start
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.now += s


def make_guard(tmp_path, ft=None, **cfg):
    ft = ft or FakeTime()
    g = Guard(tmp_path / "state" / "guard.json", GuardConfig(**{"min_spacing_s": 20, "daily_cap": 150,
                                                               "cooldown_hours": 6, **cfg}),
              clock=ft.clock, sleep=ft.sleep, lock_wait_s=0)
    return g, ft


def acquire(g, p):
    permit = asyncio.run(g.acquire(p, notify=lambda m: None))
    g.release(permit)
    return permit


QWEN = ProviderConfig(name="qwen", model="qwen-web/qwen3.8-max", **WEB)


# ------------------------------------------------------------------ classification

@pytest.mark.parametrize("res,expected", [
    (ChatResult("http_error", http_status=429), RATE_LIMIT),
    (ChatResult("http_error", http_status=401, body_excerpt="token expired"), SESSION),
    (ChatResult("http_error", http_status=403, body_excerpt="<html>Just a moment...</html>"), CHALLENGE),
    (ChatResult("http_error", http_status=403, body_excerpt="forbidden"), SESSION),
    (ChatResult("http_error", http_status=502, body_excerpt="please verify you are human"), CHALLENGE),
    (ChatResult("http_error", http_status=502, body_excerpt="session expired"), SESSION),
    (ChatResult("http_error", http_status=500, body_excerpt="boom"), None),
    (ChatResult("ok", text="<!DOCTYPE html><html>Please log in</html>", http_status=200), SESSION),
    (ChatResult("ok", text="<html>captcha</html>", http_status=200), CHALLENGE),
    (ChatResult("ok", text="A captcha is a test that tells humans and bots apart.", http_status=200), None),
    (ChatResult("timeout"), None),
])
def test_classify_trip(res, expected):
    assert classify_trip(res) == expected


# ------------------------------------------------------------------ spacing / cap

def test_min_spacing_waits_the_remainder(tmp_path):
    g, ft = make_guard(tmp_path)
    acquire(g, QWEN)
    ft.now += 5
    acquire(g, QWEN)
    assert ft.slept == [pytest.approx(15.0)]


def test_no_wait_when_spacing_already_passed(tmp_path):
    g, ft = make_guard(tmp_path)
    acquire(g, QWEN)
    ft.now += 25
    acquire(g, QWEN)
    assert ft.slept == []


def test_daily_cap_blocks_and_resets_next_day(tmp_path):
    g, ft = make_guard(tmp_path, daily_cap=2, min_spacing_s=0)
    acquire(g, QWEN)
    acquire(g, QWEN)
    with pytest.raises(GuardBlocked) as e:
        acquire(g, QWEN)
    assert e.value.reason == "daily_cap" and "tope diario" in e.value.message_es
    ft.now += 24 * 3600
    acquire(g, QWEN)  # a new day


# ------------------------------------------------------------------ cooldown

def test_429_trips_cooldown_until_expiry(tmp_path):
    g, ft = make_guard(tmp_path)
    notice = g.report(QWEN, ChatResult("http_error", http_status=429))
    assert "429" in notice and "no lo reintento" in notice
    with pytest.raises(GuardBlocked) as e:
        acquire(g, QWEN)
    assert e.value.reason == "cooldown" and "pausa" in e.value.message_es
    ft.now += 6 * 3600 + 1
    acquire(g, QWEN)


def test_expired_session_notice_names_the_dashboard_step(tmp_path):
    g, _ = make_guard(tmp_path)
    notice = g.report(QWEN, ChatResult("http_error", http_status=401, body_excerpt="token expired"))
    assert "Panel OmniRoute > Providers > X" in notice
    assert "webllm guard clear qwen" in notice


def test_challenge_notice(tmp_path):
    g, _ = make_guard(tmp_path)
    notice = g.report(QWEN, ChatResult("http_error", http_status=403, body_excerpt="cf-chl captcha"))
    assert "verificación humana" in notice


def test_ok_result_does_not_trip(tmp_path):
    g, _ = make_guard(tmp_path)
    assert g.report(QWEN, ChatResult("ok", text="hola", http_status=200)) is None
    acquire(g, QWEN)


def test_clear_lifts_cooldown(tmp_path):
    g, _ = make_guard(tmp_path)
    g.report(QWEN, ChatResult("http_error", http_status=429))
    assert g.clear("qwen") is True
    acquire(g, QWEN)
    assert g.clear("qwen") is False


def test_corrupt_state_is_not_silently_ignored(tmp_path):
    g, _ = make_guard(tmp_path)
    g.state_file.parent.mkdir(parents=True, exist_ok=True)
    g.state_file.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unreadable"):
        acquire(g, QWEN)


# ------------------------------------------------------------------ in-flight lock

def test_second_request_while_in_flight_is_refused(tmp_path):
    g, _ = make_guard(tmp_path, min_spacing_s=0)
    permit = asyncio.run(g.acquire(QWEN, notify=lambda m: None))
    with pytest.raises(GuardBlocked) as e:
        asyncio.run(g.acquire(QWEN, notify=lambda m: None))
    assert e.value.reason == "busy"
    g.release(permit)
    acquire(g, QWEN)


def test_stale_lock_from_crashed_run_is_removed(tmp_path):
    g, _ = make_guard(tmp_path, min_spacing_s=0)
    g.lock_dir.mkdir(parents=True, exist_ok=True)
    lock = g.lock_dir / "qwen.lock"
    lock.write_text("1234 0\n")
    old = time.time() - 3600
    os.utime(lock, (old, old))
    acquire(g, QWEN)


# ------------------------------------------------------------------ persistence

def test_cooldown_persists_across_guard_instances(tmp_path):
    g1, ft = make_guard(tmp_path)
    g1.report(QWEN, ChatResult("http_error", http_status=429))
    del g1
    g2, _ = make_guard(tmp_path, ft=ft)  # "restart": fresh object, same state file
    with pytest.raises(GuardBlocked):
        acquire(g2, QWEN)
    saved = json.loads((tmp_path / "state" / "guard.json").read_text(encoding="utf-8"))
    assert saved["providers"]["qwen"]["cooldown_until"] > ft.now


def test_cooldown_persists_across_processes(tmp_path):
    data = tmp_path / "data"
    (data / "state").mkdir(parents=True)
    (data / "config.yaml").write_text(
        "providers:\n"
        "  qwen: {model: qwen-web/qwen3.8-max, kind: web, enabled: true}\n", encoding="utf-8")
    Guard(data / "state" / "guard.json", GuardConfig()).report(
        ProviderConfig(name="qwen", model="qwen-web/qwen3.8-max", kind="web"),
        ChatResult("http_error", http_status=429))
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="utf-8")
    out = subprocess.run([sys.executable, "-m", "webllm_agent.cli.main", "--data-dir", str(data), "status"],
                         capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "EN PAUSA" in out.stdout and "429" in out.stdout


# ------------------------------------------------------------------ through the broadcaster

def _bcast(cfg, targets, guard):
    notes: list[str] = []
    outcomes = asyncio.run(broadcast(cfg, "x", targets, api_key=GOOD_KEY, guard=guard, notify=notes.append))
    return outcomes, notes


def test_tripped_web_provider_is_skipped_in_todas_and_never_called(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [
        ProviderConfig(name="web1", model="webmock/r429", **WEB),
        ProviderConfig(name="api1", model="api/ok"),
    ], guard=GuardConfig(min_spacing_s=0))
    guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
    first, _ = _bcast(cfg, resolve_targets(cfg, "todas"), guard)
    assert any("AVISO web1" in n for n in first[0].notices)
    assert mock_server.calls("webmock/r429") == 1
    second, _ = _bcast(cfg, resolve_targets(cfg, "todas"), guard)
    by = {o.target.name: o for o in second}
    assert by["web1"].result.status == "skipped" and "pausa" in by["web1"].notices[0]
    assert by["api1"].result.ok
    assert mock_server.calls("webmock/r429") == 1  # not called again
    assert "SALTADO" in render(second)


def test_tripped_web_provider_does_not_fall_back(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [
        ProviderConfig(name="web1", model="webmock/r401", fallback_models=("webmock/ok",), **WEB),
    ], guard=GuardConfig(min_spacing_s=0))
    guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
    (o,), _ = _bcast(cfg, resolve_targets(cfg, "web1"), guard)
    assert o.tried_models == ["webmock/r401"] and mock_server.calls("webmock/ok") == 0
    assert "webllm guard clear web1" in o.notices[0]


def test_challenge_page_trips_guard(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [
        ProviderConfig(name="web1", model="webmock/r403cf", **WEB)], guard=GuardConfig(min_spacing_s=0))
    guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
    (o,), _ = _bcast(cfg, resolve_targets(cfg, "web1"), guard)
    assert "verificación humana" in o.notices[0]


def test_html_login_wall_with_200_trips_guard(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [
        ProviderConfig(name="web1", model="webmock/html200", **WEB)], guard=GuardConfig(min_spacing_s=0))
    guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
    (o,), _ = _bcast(cfg, resolve_targets(cfg, "web1"), guard)
    assert "sesión caducada" in o.notices[0]


def test_api_provider_429_does_not_create_cooldown(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [ProviderConfig(name="api1", model="api/r429")])
    guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
    _bcast(cfg, resolve_targets(cfg, "todas"), guard)
    _bcast(cfg, resolve_targets(cfg, "todas"), guard)
    assert mock_server.calls("api/r429") == 2
    assert guard.status() == {}


def test_spacing_applies_between_broadcasts(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [
        ProviderConfig(name="web1", model="webmock/ok", **WEB)], guard=GuardConfig(min_spacing_s=1.0))
    guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
    _bcast(cfg, resolve_targets(cfg, "web1"), guard)
    _, notes = _bcast(cfg, resolve_targets(cfg, "web1"), guard)
    times = [r["t"] for r in mock_server.requests]
    assert times[1] - times[0] >= 0.95
    assert any("espero" in n for n in notes)
