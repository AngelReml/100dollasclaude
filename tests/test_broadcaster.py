"""Broadcaster tests against the local mock server (no network)."""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from conftest import GOOD_KEY, make_config
from webllm_agent.broadcaster import (
    GatewayError, TargetError, broadcast, render, resolve_targets, verify_run, write_run,
)
from webllm_agent.config import ProviderConfig
from webllm_agent.guard import Guard


def P(name, model, **kw):
    return ProviderConfig(name=name, model=model, **kw)


def run(cfg, prompt, targets, key=GOOD_KEY, timeout_s=None):
    guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
    return asyncio.run(broadcast(cfg, prompt, targets, api_key=key, guard=guard,
                                 timeout_s=timeout_s, notify=lambda m: None))


# ------------------------------------------------------------------ happy path

def test_all_ok_sections_in_priority_order(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [P("alpha", "a/ok"), P("beta", "b/ok")])
    outcomes = run(cfg, "hola", resolve_targets(cfg, "todas"))
    assert [o.target.name for o in outcomes] == ["alpha", "beta"]
    assert all(o.result.ok for o in outcomes)
    text = render(outcomes, "RID")
    assert text.index("1/2 · alpha · a/ok · OK") < text.index("2/2 · beta · b/ok · OK")
    assert "answer from a/ok" in text and "answer from b/ok" in text
    # transparent headers reach the gateway
    hdrs = {k.lower(): v for k, v in mock_server.requests[0]["headers"].items()}
    assert hdrs["x-omniroute-no-cache"] == "true" and hdrs["x-omniroute-compression"] == "off"


def test_different_providers_run_concurrently(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [P(f"p{i}", f"u{i}/ok") for i in range(4)])
    t0 = time.perf_counter()
    run(cfg, "x", resolve_targets(cfg, "todas"))
    assert time.perf_counter() - t0 < 4 * 0.3  # each mock answer takes 0.3 s


def test_same_upstream_runs_sequentially(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url,
                      [P("one", "same/ok1"), P("two", "same/ok2"), P("other", "diff/ok")])
    outcomes = run(cfg, "x", resolve_targets(cfg, "todas"))
    assert all(o.result.ok for o in outcomes)
    assert mock_server.max_inflight["same"] == 1


# -------------------------------------------------------------- failure modes

def test_one_timeout_does_not_hide_others(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url,
                      [P("fast", "f/ok"), P("slow", "s/slow", timeout_s=0.5)])
    outcomes = run(cfg, "x", resolve_targets(cfg, "todas"))
    by = {o.target.name: o.result for o in outcomes}
    assert by["fast"].ok
    assert by["slow"].status == "timeout"
    text = render(outcomes)
    assert "TIEMPO AGOTADO" in text and "answer from f/ok" in text


def test_429_reported_and_others_fine(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [P("ok", "o/ok"), P("limited", "l/r429")])
    outcomes = run(cfg, "x", resolve_targets(cfg, "todas"))
    by = {o.target.name: o.result for o in outcomes}
    assert by["ok"].ok
    assert by["limited"].status == "http_error" and by["limited"].http_status == 429
    assert "FALLO (HTTP 429)" in render(outcomes)


def test_malformed_body(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [P("broken", "m/malformed"), P("ok", "o/ok")])
    outcomes = run(cfg, "x", resolve_targets(cfg, "todas"))
    by = {o.target.name: o.result for o in outcomes}
    assert by["broken"].status == "malformed" and by["ok"].ok
    assert "RESPUESTA ROTA" in render(outcomes)


def test_fallback_model_used_after_failure(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url,
                      [P("zai", "z/r500", fallback_models=("d/ok",))])
    (o,) = run(cfg, "x", resolve_targets(cfg, "zai"))
    assert o.result.ok and o.tried_models == ["z/r500", "d/ok"]
    assert any("respaldo" in n for n in o.notices)


def test_gateway_down_fails_fast(tmp_path):
    cfg = make_config(tmp_path, "http://127.0.0.1:9/v1", [P("a", "a/ok")])
    with pytest.raises(GatewayError, match="PROBAR TODO"):
        run(cfg, "x", resolve_targets(cfg, "todas"))


def test_bad_gateway_key_fails_before_any_chat(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [P("a", "a/ok")])
    with pytest.raises(GatewayError, match="clave"):
        run(cfg, "x", resolve_targets(cfg, "todas"), key="bad-key")
    assert mock_server.requests == []


# ------------------------------------------------------------------ name mapping

def test_name_mapping(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [
        P("qwen", "qwen-web/qwen3.8-max", kind="web"),
        P("zai", "zai/glm-4.7-flash", enabled=False),
        P("groq", "groq/openai/gpt-oss-120b"),
    ])
    assert [t.name for t in resolve_targets(cfg, "todas")] == ["qwen", "groq"]
    assert [t.name for t in resolve_targets(cfg, "TODAS")] == ["qwen", "groq"]
    assert resolve_targets(cfg, "groq")[0].model == "groq/openai/gpt-oss-120b"
    raw = resolve_targets(cfg, "ds-web/deepseek-v4-pro")[0]
    assert raw.model == "ds-web/deepseek-v4-pro" and raw.kind == "web"
    assert resolve_targets(cfg, "openrouter/x:free")[0].kind == "api"
    with pytest.raises(TargetError, match="desactivado"):
        resolve_targets(cfg, "zai")
    with pytest.raises(TargetError, match="No conozco"):
        resolve_targets(cfg, "grok")


@pytest.mark.parametrize("model", [
    "codex/gpt-5.5", "cx/gpt-5.6-sol", "gpt-5.5", "claude-sonnet", "openrouter/anthropic/claude-x",
    "chatgpt-web/gpt-5", "somegateway/chatgpt-4o",
])
def test_excluded_models_are_refused(tmp_path, mock_server, model):
    cfg = make_config(tmp_path, mock_server.base_url, [P("groq", "groq/openai/gpt-oss-120b")])
    with pytest.raises(TargetError):
        resolve_targets(cfg, model)


def test_excluded_model_in_config_is_refused(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [P("sneaky", "a/ok", fallback_models=("codex/gpt-5.5",))])
    with pytest.raises(TargetError, match="excluido"):
        resolve_targets(cfg, "todas")


# --------------------------------------------------------------------- journal

def _run_and_write(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [P("alpha", "a/ok"), P("beta", "b/r429"), P("gamma", "c/ok")])
    outcomes = run(cfg, "prompt with ñ and €", resolve_targets(cfg, "todas"))
    return write_run(cfg.paths.runs_dir, "RUN1", "prompt with ñ and €", outcomes)


def test_journal_verifies_ok(tmp_path, mock_server):
    run_dir = _run_and_write(tmp_path, mock_server)
    res = verify_run(run_dir)
    assert res.ok and res.lines == 3
    lines = [json.loads(x) for x in (run_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert lines[0]["prev_hash"] == "0" * 64
    assert lines[1]["prev_hash"] == lines[0]["hash"]
    assert {"ts", "provider", "model", "prompt_sha256", "response_sha256", "status", "latency_s",
            "prev_hash", "hash"} <= set(lines[0])
    assert lines[1]["status"] == "http_error" and lines[1]["response_sha256"] is None


def test_journal_tamper_detected_at_first_broken_line(tmp_path, mock_server):
    run_dir = _run_and_write(tmp_path, mock_server)
    j = run_dir / "journal.jsonl"
    lines = j.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace('"status":"http_error"', '"status":"ok"')
    j.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = verify_run(run_dir)
    assert not res.ok and res.first_bad_line == 2


def test_journal_reorder_detected(tmp_path, mock_server):
    run_dir = _run_and_write(tmp_path, mock_server)
    j = run_dir / "journal.jsonl"
    a, b, c = j.read_text(encoding="utf-8").splitlines()
    j.write_text("\n".join([b, a, c]) + "\n", encoding="utf-8")
    res = verify_run(run_dir)
    assert not res.ok and res.first_bad_line == 1


def test_journal_truncation_detected(tmp_path, mock_server):
    run_dir = _run_and_write(tmp_path, mock_server)
    j = run_dir / "journal.jsonl"
    j.write_text("\n".join(j.read_text(encoding="utf-8").splitlines()[:2]) + "\n", encoding="utf-8")
    res = verify_run(run_dir)
    assert not res.ok and res.first_bad_line == 3


def test_edited_response_file_detected(tmp_path, mock_server):
    run_dir = _run_and_write(tmp_path, mock_server)
    f = next((run_dir / "responses").glob("*alpha*"))
    f.write_text("something else", encoding="utf-8")
    res = verify_run(run_dir)
    assert not res.ok and res.first_bad_line == 1
