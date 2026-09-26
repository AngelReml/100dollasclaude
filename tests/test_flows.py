"""Chain engine tests: mock OmniRoute (API AIs) and a fake Chrome extension (chat AIs); no network."""

from __future__ import annotations

import asyncio
import json
import time

import pytest
from aiohttp.test_utils import TestServer

from conftest import GOOD_KEY, make_config
from test_bridge import TOKEN, FakeExtension
from webllm_agent import flows
from webllm_agent.client import ChatResult
from webllm_agent.bridge import Bridge
from webllm_agent.broadcaster import GatewayError, verify_run
from webllm_agent.config import GuardConfig, ProviderConfig
from webllm_agent.flows import Flow, FlowError, Step
from webllm_agent.guard import Guard


def P(name, model, **kw):
    return ProviderConfig(name=name, model=model, **kw)


def cfg_for(tmp_path, mock_server, providers=None):
    return make_config(tmp_path, mock_server.base_url, providers or [
        P("alpha", "a/ok"), P("beta", "b/ok"), P("gamma", "g/ok"),
    ])


def go(cfg, flow, key=GOOD_KEY, **kw):
    events: list[dict] = []
    guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
    run = asyncio.run(flows.run_flow(cfg, flow, api_key=key, guard=guard, emit=events.append, **kw))
    return run, events


def prompts_to(mock_server, model):
    return [r["prompt"] for r in mock_server.requests if r["model"] == model]


# ------------------------------------------------------------------ validation

@pytest.mark.parametrize("steps, inputs, fragment", [
    ([Step("s1", ("alpha",), "{{nada}}")], {}, "no es ningún paso"),
    ([Step("s1", ("alpha",), "{{s1}}")], {}, "su propia respuesta"),
    ([Step("s1", ("alpha",), "{{s2}}"), Step("s2", ("beta",), "{{s1}}")], {}, "vueltas sin fin"),
    ([Step("s1", ("alpha",), "x"), Step("s1", ("beta",), "y")], {}, "mismo nombre"),
    ([Step("s1", ("alpha",), "x", on_error="retry")], {}, "si falla"),
    ([Step("s1", (), "x")], {}, "no dice a qué IA"),
    ([Step("s1", ("alpha", "alpha"), "x")], {}, "repite una IA"),
    ([Step("s1", ("todas",), "x")], {}, "nombra cada IA"),
    ([Step("s1", ("nadie",), "x")], {}, "No conozco"),
    ([Step("s1", ("cc/claude-sonnet",), "x")], {}, "excluido"),
    ([Step("s1", ("alpha",), "{{s2.beta}}"), Step("s2", ("gamma",), "x")], {}, "no pregunta a"),
    ([Step("s1", ("alpha",), "{{q.x}}")], {"q": "hola"}, "no tiene partes"),
    ([Step("q", ("alpha",), "x")], {"q": "hola"}, "a la vez un paso"),
    ([Step("mal id", ("alpha",), "x")], {}, "letras, números"),
])
def test_invalid_flows_are_refused_before_sending(tmp_path, mock_server, steps, inputs, fragment):
    cfg = cfg_for(tmp_path, mock_server)
    with pytest.raises(FlowError, match=fragment):
        go(cfg, Flow("x", tuple(steps), inputs))
    assert mock_server.requests == []


def test_disabled_provider_is_refused(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server, [P("alpha", "a/ok"), P("off", "o/ok", enabled=False)])
    with pytest.raises(FlowError, match="desactivado"):
        flows.validate(cfg, Flow("x", (Step("s1", ("off",), "x"),)))


def test_flow_json_round_trip(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server)
    flow = flows.council_and_judge(cfg, "¿Qué es mejor?", ["alpha", "beta"], "gamma")
    again = flows.flow_from_dict(json.loads(json.dumps(flows.flow_to_dict(flow))))
    assert again == flow


# ------------------------------------------------------------------ rendering

def test_substitution_is_single_pass(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server)
    flow = Flow("x", (Step("s1", ("alpha",), "Dice: {{q}}"),), {"q": "texto con {{s1}} dentro"})
    run, _ = go(cfg, flow)
    assert prompts_to(mock_server, "a/ok") == ["Dice: texto con {{s1}} dentro"]
    assert run.status == flows.OK


def test_answers_flow_into_later_steps(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server)
    flow = Flow("x", (
        Step("s1", ("alpha", "beta"), "{{q}}"),
        Step("s2", ("gamma",), "Todas:\n{{s1}}\nSolo beta: {{s1.beta}}"),
    ), {"q": "hola"})
    go(cfg, flow)
    (judge_prompt,) = prompts_to(mock_server, "g/ok")
    assert "### alpha\n\nanswer from a/ok" in judge_prompt
    assert "### beta\n\nanswer from b/ok" in judge_prompt
    assert judge_prompt.endswith("Solo beta: answer from b/ok")


# ------------------------------------------------------------------ scheduling

def test_independent_steps_run_in_parallel_dependent_ones_wait(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server, [P("s1", "u1/slow"), P("s2", "u2/slow"), P("j", "u3/ok")])
    flow = Flow("x", (
        Step("p1", ("s1",), "a"), Step("p2", ("s2",), "b"), Step("merge", ("j",), "{{p1}} {{p2}}"),
    ))
    t0 = time.monotonic()
    run, _ = go(cfg, flow)
    elapsed = time.monotonic() - t0
    assert run.status == flows.OK
    assert elapsed < 3.8, elapsed  # two 2 s steps side by side, not one after the other
    by_model = {r["model"]: r["t"] for r in mock_server.requests}
    assert by_model["u3/ok"] >= max(by_model["u1/slow"], by_model["u2/slow"]) + 1.9


def test_same_upstream_never_overlaps_across_parallel_steps(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server, [P("x1", "same/ok1"), P("x2", "same/ok2")])
    flow = Flow("x", (Step("p1", ("x1",), "a"), Step("p2", ("x2",), "b")))
    run, _ = go(cfg, flow)
    assert run.status == flows.OK
    assert mock_server.max_inflight["same"] == 1


def test_a_queued_answer_starts_its_clock_only_when_it_is_sent(tmp_path, mock_server):
    """Iván saw chats "Esperando… 200 s" that were only queued behind another one."""
    cfg = cfg_for(tmp_path, mock_server, [P("x1", "same/slow"), P("x2", "same/ok")])
    run, events = go(cfg, Flow("x", (Step("p1", ("x1", "x2"), "a"),)))
    assert run.status == flows.OK
    order = [(e["type"], e["target"]) for e in events if e["type"] in ("target_start", "target_done")]
    assert order == [("target_start", "x1"), ("target_done", "x1"), ("target_start", "x2"), ("target_done", "x2")]


# ------------------------------------------------------------------ failures

def test_stop_on_error_does_not_send_later_steps(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server, [P("bad", "b/r500"), P("j", "j/ok")])
    flow = Flow("x", (Step("s1", ("bad",), "a"), Step("s2", ("j",), "{{s1}}")))
    run, events = go(cfg, flow)
    assert run.status == flows.STOPPED
    assert run.steps["s1"].status == flows.FAILED and run.steps["s2"].status == flows.SKIPPED
    assert prompts_to(mock_server, "j/ok") == []
    assert events[-1]["type"] == "flow_done" and events[-1]["status"] == "stopped"


def test_partial_step_continues_and_says_who_did_not_answer(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server, [P("good", "g/ok"), P("bad", "b/r500"), P("j", "j/ok")])
    flow = Flow("x", (Step("s1", ("good", "bad"), "q"), Step("s2", ("j",), "{{s1}}")))
    run, _ = go(cfg, flow)
    assert run.steps["s1"].status == flows.PARTIAL and run.status == flows.PARTIAL
    (p,) = prompts_to(mock_server, "j/ok")
    assert "### bad\n\n(no respondió)" in p and "answer from g/ok" in p


def test_wait_retries_a_temporary_failure_once(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server, [P("f", "f/flaky")])
    slept: list[float] = []

    async def fake_sleep(s):
        slept.append(s)

    run, events = go(cfg, Flow("x", (Step("s1", ("f",), "q", on_error="wait", wait_s=45),)), sleep=fake_sleep)
    assert run.status == flows.OK and slept == [45]
    assert len(prompts_to(mock_server, "f/flaky")) == 2
    assert any(e["type"] == "target_wait" for e in events)


def test_wait_never_retries_an_account_limit(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server, [P("lim", "l/r429")])
    slept: list[float] = []

    async def fake_sleep(s):
        slept.append(s)

    run, _ = go(cfg, Flow("x", (Step("s1", ("lim",), "q", on_error="wait"),)), sleep=fake_sleep)
    assert run.status == flows.STOPPED and slept == []
    assert len(prompts_to(mock_server, "l/r429")) == 1


def test_fallback_asks_another_ai_and_later_steps_use_it(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server, [P("bad", "b/r503"), P("alt", "alt/ok"), P("j", "j/ok")])
    flow = Flow("x", (
        Step("s1", ("bad",), "q", on_error="fallback", fallback=("alt",)),
        Step("s2", ("j",), "{{s1.bad}}"),
    ))
    run, events = go(cfg, flow)
    a = run.steps["s1"].answers["bad"]
    assert a.ok and a.provider == "alt" and run.status == flows.OK
    assert prompts_to(mock_server, "j/ok") == ["answer from alt/ok"]
    assert [e["provider"] for e in events if e["type"] == "target_fallback"] == ["alt"]
    lines = [json.loads(x) for x in (run.run_dir / "journal.jsonl").read_text("utf-8").splitlines()]
    assert [(x.get("attempt"), x.get("provider")) for x in lines if x["kind"] == "flow"][:2] == [
        ("first", "bad"), ("fallback", "alt")]


def test_web_provider_in_cooldown_is_skipped_not_sent(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server, [P("web", "webmock/ok", kind="web")])
    Guard(cfg.paths.state_dir / "guard.json", cfg.guard).trip(cfg.providers["web"], "prueba", 1)
    run, events = go(cfg, Flow("x", (Step("s1", ("web",), "q"),)))
    assert run.status == flows.STOPPED and mock_server.requests == []
    done = [e for e in events if e["type"] == "target_done"][0]
    assert not done["ok"] and done["code"] == "cooldown" and "pausa" in done["notices"][0]


@pytest.mark.parametrize("model, code", [
    ("x/r429", "rate_limited"), ("x/r401", "unauthorized"), ("x/r503", "overloaded"),
    ("x/r500", "error"), ("x/malformed", "malformed"),
])
def test_failures_carry_a_code_for_the_app(tmp_path, mock_server, model, code):
    cfg = cfg_for(tmp_path, mock_server, [P("x", model)])
    run, events = go(cfg, Flow("x", (Step("s1", ("x",), "q"),)))
    assert run.steps["s1"].answers["x"].code == code
    assert [e["code"] for e in events if e["type"] == "target_done"] == [code]


def test_gateway_down_fails_before_anything_is_written_or_sent(tmp_path):
    cfg = make_config(tmp_path, "http://127.0.0.1:9/v1", [P("a", "a/ok")])
    with pytest.raises(GatewayError):
        go(cfg, Flow("x", (Step("s1", ("a",), "q"),)))
    assert list(cfg.paths.runs_dir.iterdir()) == []


# ------------------------------------------------------------------ journal

def test_flow_run_is_journaled_and_tamper_evident(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server)
    run, events = go(cfg, flows.council_and_judge(cfg, "¿té o café?", ["alpha", "beta"], "gamma"))
    assert run.verified and verify_run(run.run_dir).ok
    lines = [json.loads(x) for x in (run.run_dir / "journal.jsonl").read_text("utf-8").splitlines()]
    assert [x["kind"] for x in lines] == ["flow", "flow", "flow", "flow_end"]
    assert lines[-1]["status"] == "ok" and lines[-1]["steps"] == {"consejo": "ok", "juez": "ok"}
    assert json.loads((run.run_dir / "flow.json").read_text("utf-8"))["template"] == "consejo"
    assert events[0]["type"] == "flow_start" and events[-1] == {
        "type": "flow_done", "run_id": run.run_id, "status": "ok", "verified": True,
        "steps": {"consejo": "ok", "juez": "ok"}}

    msg = run.run_dir / "messages" / "juez.md"
    original = msg.read_bytes()
    msg.write_text("mensaje cambiado", encoding="utf-8")
    bad = verify_run(run.run_dir)
    assert not bad.ok and "message_file" not in bad.reason and "prompt_sha256" in bad.reason
    msg.write_bytes(original)
    assert verify_run(run.run_dir).ok
    resp = sorted((run.run_dir / "responses").iterdir())[0]
    resp.write_text("respuesta cambiada", encoding="utf-8")
    assert not verify_run(run.run_dir).ok


# ------------------------------------------------------------------ estimate & templates

def test_estimate_counts_messages_per_ai(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server)
    flow = flows.debate(cfg, "q", "alpha", "beta", rounds=2)
    est = flows.estimate_messages(cfg, flow)
    assert est["normal"] == {"alpha": 3, "beta": 2}
    assert est["worst"] == {"alpha": 6, "beta": 4}  # "wait" may resend once
    judge = flows.council_and_judge(cfg, "q", ["alpha", "beta"], "gamma")
    assert flows.estimate_messages(cfg, judge)["normal"] == {"alpha": 1, "beta": 1, "gamma": 1}


def test_debate_structure_and_run(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server)
    flow = flows.debate(cfg, "¿Es buena idea?", "alpha", "beta", rounds=2)
    assert [s.id for s in flow.steps] == ["a1", "b1", "a2", "b2", "a3"]
    run, _ = go(cfg, flow)
    assert run.status == flows.OK
    assert [r["model"] for r in mock_server.requests] == ["a/ok", "b/ok", "a/ok", "b/ok", "a/ok"]
    with pytest.raises(FlowError):
        flows.debate(cfg, "q", "alpha", "beta", rounds=6)


def test_chain_passes_each_answer_to_the_next(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server)
    flow = flows.chain(cfg, "vender pan", [("alpha", "Dame una idea"), ("beta", "Haz un plan"), ("gamma", "Revísalo")])
    run, _ = go(cfg, flow)
    assert run.status == flows.OK
    assert prompts_to(mock_server, "a/ok") == ["Dame una idea\n\nvender pan"]
    assert prompts_to(mock_server, "b/ok") == ["Haz un plan\n\nanswer from a/ok"]
    assert prompts_to(mock_server, "g/ok") == ["Revísalo\n\nanswer from b/ok"]


def test_judge_falls_back_to_another_api_ai(tmp_path, mock_server):
    cfg = cfg_for(tmp_path, mock_server, [P("alpha", "a/ok"), P("beta", "b/ok"),
                                          P("judge", "j/r503"), P("spare", "s/ok")])
    flow = flows.council_and_judge(cfg, "q", ["alpha", "beta"], "judge")
    assert flow.steps[1].fallback == ("spare", "alpha", "beta")  # not a council member first
    run, _ = go(cfg, flow)
    assert run.status == flows.OK and run.steps["juez"].answers["judge"].provider == "spare"


# ------------------------------------------------------------------ with Chrome chats (fake extension)

def test_split_and_merge_with_two_chrome_chats_and_one_api_ai(tmp_path, mock_server):
    """The plan's phase-1 check (Reparto + integración, 2 chats + 1 API AI), with test doubles."""

    async def scenario():
        cfg = make_config(tmp_path, mock_server.base_url, [
            P("qwen", "browser/qwen", kind="browser", gateway="bridge"),
            P("deepseek", "browser/deepseek", kind="browser", gateway="bridge"),
            P("zai", "z/ok"),
        ], guard=GuardConfig(min_spacing_s=0))
        bridge = Bridge(cfg, TOKEN, timeout_s=5, human_wait_s=0, connect_wait_s=1, launcher=None, log=lambda m: None)
        server = TestServer(bridge.app())
        await server.start_server()
        object.__setattr__(cfg, "bridge_port", server.port)
        ext = FakeExtension({})
        await ext.connect(server)
        await asyncio.wait_for(bridge.connected.wait(), 2)
        try:
            flow = flows.split_and_merge(cfg, "comparar té y café",
                                         [("qwen", "beneficios del café"), ("deepseek", "beneficios del té")], "zai")
            guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
            return await flows.run_flow(cfg, flow, api_key=GOOD_KEY, guard=guard, bridge_key=TOKEN), ext
        finally:
            await ext.close()
            await server.close()

    run, ext = asyncio.run(scenario())
    assert run.status == flows.OK and run.verified
    assert sorted(j["site"] for j in ext.jobs) == ["deepseek", "qwen"]
    assert "Tu parte: beneficios del café" in next(j["prompt"] for j in ext.jobs if j["site"] == "qwen")
    (merge_prompt,) = prompts_to(mock_server, "z/ok")
    assert "PARTE DE QWEN (beneficios del café):\nanswer from qwen" in merge_prompt
    assert "PARTE DE DEEPSEEK (beneficios del té):\nanswer from deepseek" in merge_prompt


# ------------------------------------------------------------------ CLI

def test_cli_cadena_runs_a_council_and_reports_the_lock(tmp_path, mock_server, capsys, monkeypatch):
    import yaml
    from webllm_agent.cli.main import main

    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / "data"
    data.mkdir()
    (data / "config.yaml").write_text(yaml.safe_dump({
        "omniroute": {"base_url": mock_server.base_url},
        "providers": {"alpha": {"model": "a/ok"}, "beta": {"model": "b/ok"}, "gamma": {"model": "g/ok"}},
        "guard": {"min_spacing_s": 0},
    }), encoding="utf-8")
    args = ["--data-dir", str(data), "cadena", "consejo", "--pregunta", "¿té o café?", "--ias", "alpha,beta",
            "--juez", "gamma"]
    assert main([*args, "--gasto"]) == 0
    assert mock_server.requests == []
    assert "Mensajes que gastará: alpha 1, beta 1, gamma 1." in capsys.readouterr().out
    assert main([*args, "--si"]) == 0
    out = capsys.readouterr().out
    assert "[OK] alpha respondió" in out and "RESULTADO FINAL (El juez compara)" in out
    assert "answer from g/ok" in out and "Candado: VERDE" in out


# What an API provider puts in error.code is its own vocabulary, not webllm's: OpenRouter sends the
# HTTP number (429, 402), z.ai its own numbers ("1302"), OpenAI-style gateways words. Iván saw
# "Nemotron no pudo responder" (the app's message for a code it does not know) instead of "límite".
# Bodies below have the shape those providers use; the messages are illustrative.
@pytest.mark.parametrize("http, body, code", [
    (429, {"error": {"code": 429, "message": "Rate limit exceeded: free-models-per-day"}}, "rate_limited"),
    (429, {"error": {"code": 429, "message": "Rate limit exceeded: free-models-per-day. "
                                            "Add 10 credits to unlock 1000 free model requests per day"}}, "rate_limited"),
    (400, {"error": {"code": "1113", "message": "Insufficient balance"}}, "no_credit"),
    (200, {"error": {"code": 429, "message": "Rate limit exceeded"}}, "rate_limited"),
    (429, {"error": {"code": "1302", "message": "High concurrency usage of this API"}}, "rate_limited"),
    (429, {"error": {"code": "rate_limit_exceeded", "message": "Too many requests"}}, "rate_limited"),
    (402, {"error": {"code": 402, "message": "Insufficient credits"}}, "no_credit"),
    (429, {"error": {"code": "insufficient_quota", "message": "You exceeded your current quota"}}, "no_credit"),
    (429, {"error": {"code": 1302, "message": "High concurrency usage of this API"}}, "rate_limited"),
    (400, {"error": {"code": "1301", "message": "contenido no permitido"}}, "error"),
    (503, {"error": {"code": "service_unavailable", "message": "overloaded"}}, "overloaded"),
    (503, {"error": {"code": "no_upstream", "message": "no healthy upstream in load balancer"}}, "overloaded"),
    (400, {"error": {"code": "context_length", "message": "insufficient context length"}}, "error"),
    (403, {"error": {"code": "paused", "message": "en pausa"}}, "paused"),
    (401, {"error": {"code": "login_required", "message": "sin sesión"}}, "login_required"),
])
def test_provider_error_codes_become_webllm_codes(http, body, code):
    r = ChatResult(status="http_error", http_status=http, error=f"HTTP {http}", body_excerpt=json.dumps(body))
    assert flows.error_code(r) == code


# ------------------------------------------------------------------ parar

def test_stop_ends_a_call_in_progress_and_sends_nothing_more(tmp_path, mock_server):
    """Iván's "parar" while an API AI is answering: that call ends as "cancelled" at once (not after the
    answer), its stand-in is not asked, the next step is not sent, and the journal still closes and verifies."""
    cfg = cfg_for(tmp_path, mock_server, [P("lenta", "l/slow"), P("reserva", "r/ok"), P("juez", "j/ok")])
    flow = Flow("x", (Step("s1", ("lenta",), "hola", on_error="fallback", fallback=("reserva",)),
                      Step("s2", ("juez",), "{{s1}}")))
    stop = asyncio.Event()

    async def main():
        loop = asyncio.get_running_loop()
        loop.call_later(0.4, stop.set)
        guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
        events: list[dict] = []
        t0 = time.perf_counter()
        result = await flows.run_flow(cfg, flow, api_key=GOOD_KEY, guard=guard, emit=events.append, stop=stop)
        return result, events, time.perf_counter() - t0

    result, events, took = asyncio.run(main())
    assert took < 1.5  # the slow AI takes 2 s: it was not waited for
    done = [e for e in events if e["type"] == "target_done"]
    assert [(e["target"], e["code"], e["ok"]) for e in done] == [("lenta", "cancelled", False)]
    assert [r["model"] for r in mock_server.requests] == ["l/slow"]  # no stand-in, no judge
    assert result.status == flows.STOPPED and result.steps["s2"].status == flows.SKIPPED
    lines = [json.loads(x) for x in (result.run_dir / "journal.jsonl").read_text("utf-8").splitlines()]
    assert [x["kind"] for x in lines] == ["flow", "flow_end"] and lines[0]["code"] == "cancelled"
    assert result.verified and verify_run(result.run_dir).ok


def test_stop_never_sends_a_call_still_waiting_its_turn(tmp_path, mock_server):
    """Two AIs behind the same service go one at a time; "parar" during the first: the second never goes."""
    cfg = cfg_for(tmp_path, mock_server, [P("lenta", "u/slow"), P("otra", "u/ok")])
    stop = asyncio.Event()

    async def main():
        asyncio.get_running_loop().call_later(0.4, stop.set)
        guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
        events: list[dict] = []
        result = await flows.run_flow(cfg, Flow("x", (Step("s1", ("lenta", "otra"), "hola"),)), api_key=GOOD_KEY,
                                      guard=guard, emit=events.append, stop=stop)
        return result, events

    result, events = asyncio.run(main())
    assert [r["model"] for r in mock_server.requests] == ["u/slow"]
    assert {e["target"]: e["code"] for e in events if e["type"] == "target_done"} == {"lenta": "cancelled", "otra": "cancelled"}
    assert [e["target"] for e in events if e["type"] == "target_start"] == ["lenta"]  # "otra" never started
    assert result.status == flows.STOPPED and verify_run(result.run_dir).ok
