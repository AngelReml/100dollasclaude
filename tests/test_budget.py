"""A daily cap per AI by API (PLAN-v5 D9): counted on every call, everywhere, reset every day."""

from __future__ import annotations

import asyncio

from conftest import make_config
from webllm_agent import flows
from webllm_agent.budget import Budget
from webllm_agent.config import GuardConfig, ProviderConfig
from webllm_agent.guard import Guard


def P(name, model, **kw):
    return ProviderConfig(name=name, model=model, **kw)


def test_the_cap_counts_every_call_and_comes_back_the_next_day(tmp_path):
    day = ["2026-09-26"]
    b = Budget(tmp_path / "b.json", default_cap=2, today=lambda: day[0])
    api = P("zai", "zai/x")
    assert b.take(api) and b.take(api) and not b.take(api) and b.used("zai") == 2
    day[0] = "2026-09-27"
    assert b.take(api) and b.used("zai") == 1


def test_one_ai_can_have_its_own_cap_and_this_pcs_models_have_none(tmp_path):
    b = Budget(tmp_path / "b.json", default_cap=2)
    own = P("groq", "groq/x", daily_cap=1)
    local = P("lm", "lmstudio/x", gateway="local")
    assert b.take(own) and not b.take(own)
    assert all(b.take(local) for _ in range(10)) and b.cap(local) is None
    assert b.cap(P("qwen", "browser/qwen", kind="browser", gateway="bridge")) is None  # the guard handles chats


def test_over_the_cap_nothing_is_sent_and_the_app_hears_daily_cap(tmp_path, mock_server):
    cfg = make_config(tmp_path, mock_server.base_url, [P("x", "x/ok", daily_cap=1)], guard=GuardConfig(min_spacing_s=0))
    flow = flows.Flow("x", (flows.Step("s1", ("x",), "q"),))

    def go():
        return asyncio.run(flows.run_flow(cfg, flow, api_key="k", guard=Guard(tmp_path / "g.json", cfg.guard)))

    assert go().steps["s1"].answers["x"].ok
    second = go().steps["s1"].answers["x"]
    assert not second.ok and second.code == "daily_cap" and "tope diario" in second.notices[0]
    assert mock_server.calls("x/ok") == 1
