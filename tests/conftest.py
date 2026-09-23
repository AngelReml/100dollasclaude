"""Shared fixtures: a local mock of OmniRoute's OpenAI-compatible API.

The behaviour is chosen by the last segment of the requested model id:
    ok*        200 with "answer from <model>"
    slow       sleeps 2 s, then 200
    r429       429 rate limit
    r401       401 session expired
    r403cf     403 with a Cloudflare-style challenge page
    r500       500 internal error
    malformed  200 with a body that is not JSON
    html200    200 whose content is an HTML login page
GET /v1/models returns 200, or 401 when the Bearer key is "bad-key".
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from webllm_agent.config import AppConfig, GuardConfig, Paths, ProviderConfig

GOOD_KEY = "sk-test-key"


class MockState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.requests: list[dict] = []
        self.inflight: dict[str, int] = defaultdict(int)
        self.max_inflight: dict[str, int] = defaultdict(int)

    def calls(self, model: str) -> int:
        return sum(1 for r in self.requests if r["model"] == model)


def _make_handler(state: MockState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep test output clean
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json", headers: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("Authorization") == "Bearer bad-key":
                return self._send(401, b'{"error":"invalid api key"}')
            self._send(200, json.dumps({"object": "list", "data": [{"id": "mock/ok"}]}).encode())

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            model = body["model"]
            upstream = model.split("/", 1)[0]
            behaviour = model.rsplit("/", 1)[-1]
            with state.lock:
                state.requests.append({"model": model, "t": time.time(), "headers": dict(self.headers),
                                       "prompt": body["messages"][0]["content"]})
                state.inflight[upstream] += 1
                state.max_inflight[upstream] = max(state.max_inflight[upstream], state.inflight[upstream])
            try:
                hdr = {"x-omniroute-provider": upstream, "x-omniroute-cache": "MISS"}
                if behaviour == "slow":
                    time.sleep(2.0)
                elif behaviour.startswith("ok"):
                    time.sleep(0.3)
                if behaviour.startswith("ok") or behaviour == "slow":
                    out = {"id": "x", "object": "chat.completion", "model": model,
                           "choices": [{"index": 0, "message": {"role": "assistant",
                                                                "content": f"answer from {model}"}}]}
                    return self._send(200, json.dumps(out).encode(), headers=hdr)
                if behaviour == "r429":
                    return self._send(429, b'{"error":{"message":"rate limited","type":"rate_limit_error"}}', headers=hdr)
                if behaviour == "r401":
                    return self._send(401, b'{"error":{"message":"session expired, please log in"}}', headers=hdr)
                if behaviour == "r403cf":
                    return self._send(403, b"<!DOCTYPE html><html><title>Just a moment...</title>cf-chl</html>",
                                      ctype="text/html", headers=hdr)
                if behaviour == "r500":
                    return self._send(500, b'{"error":{"message":"upstream exploded"}}', headers=hdr)
                if behaviour == "malformed":
                    return self._send(200, b'{"choices": [ this is not json', headers=hdr)
                if behaviour == "html200":
                    out = {"model": model, "choices": [{"message": {"content":
                           "<!DOCTYPE html><html><body>Please log in to continue</body></html>"}}]}
                    return self._send(200, json.dumps(out).encode(), headers=hdr)
                return self._send(404, b'{"error":"unknown mock model"}')
            finally:
                with state.lock:
                    state.inflight[upstream] -= 1

    return Handler


@pytest.fixture
def mock_server():
    state = MockState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    yield state
    server.shutdown()
    server.server_close()


def make_config(tmp_path: Path, base_url: str, providers: list[ProviderConfig],
                guard: GuardConfig | None = None) -> AppConfig:
    paths = Paths.from_data_dir(tmp_path / "data")
    paths.ensure()
    return AppConfig(
        paths=paths,
        base_url=base_url,
        providers={p.name: p for p in providers},
        guard=guard or GuardConfig(min_spacing_s=0, daily_cap=150, cooldown_hours=6),
        blocked_model_prefixes=("codex/", "cx/", "cxa/", "cc/", "cgpt", "gpt-"),
        blocked_model_substrings=("claude", "anthropic", "chatgpt", "codex"),
        web_model_prefixes=("qwen-web/", "ds-web/", "ms-web/", "webmock/"),
    )
