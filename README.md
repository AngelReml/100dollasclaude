# webllm-agent (v2)

> 🚧 **UNDER CONSTRUCTION / EN CONSTRUCCIÓN.** Your own Chrome drives the AI chat
> pages (Qwen, DeepSeek, z.ai, Meta AI) through a local extension + bridge that
> looks like an OpenAI API, so aider can program with them. Verified end to end
> with a stand-in extension and on the live z.ai page; pending: the real
> extension loaded in the user's Chrome. See [docs/ESTADO.md](docs/ESTADO.md).
>
> ```
> aider / webllm ask ──► bridge 127.0.0.1:20130 ──► Chrome extension ──► chat page (type, wait, copy)
> ```
> Start: `iniciar.cmd` · ask: `preguntar.cmd` · code: `programar.cmd <qwen|deepseek|zai|meta>` · unpause: `reanudar.cmd`

Type one prompt and send it to several AI providers at once — or to one —
through a single local gateway, and let a coding agent apply changes to a
folder on your PC.

> Day-to-day instructions (in Spanish): **[docs/ESTADO.md](docs/ESTADO.md)**.
> Architecture: [docs/spec.md](docs/spec.md).

## Pieces

| Piece | What it is | Status |
|---|---|---|
| Gateway | [OmniRoute](https://github.com/diegosouzapw/OmniRoute) 3.8.50 on `http://127.0.0.1:20128/v1` (OpenAI-compatible), installed in `..\omnirouter` | running |
| Coding agent | [aider](https://aider.chat) 0.86.2 (isolated via `uv tool`), launched with `aider-omniroute.cmd` | working |
| Broadcaster | `webllm ask` (this package) | working |
| Plan B | Own Chrome extension | not needed (design in `docs/plan-b.md`) |

Providers are mapped in `data/config.yaml` (name → OmniRoute model id, in
priority order). Web providers (Qwen, DeepSeek, Meta AI) need their session
pasted once in the OmniRoute dashboard; see `docs/proveedores-web.md`.
Claude and ChatGPT/Codex are excluded and always refused.

## Commands

```bat
start-omniroute.cmd                       :: start the gateway (minimized window)
stop-omniroute.cmd                        :: stop it
preguntar.cmd                             :: double-click: type a prompt, pick todas / one
webllm.cmd ask "prompt" --to todas        :: or --to qwen|deepseek|zai|meta|groq|nemotron|<model-id>
webllm.cmd status                         :: providers, cooldowns, today's counts
webllm.cmd journal verify --all           :: check every run's hash chain
webllm.cmd guard clear <name>             :: lift a cooldown after fixing a session
aider-omniroute.cmd                       :: run from the folder you want aider to edit
```

Every `ask` writes `data/runs/<run_id>/` with `prompt.txt`, one response file
per provider, `journal.jsonl` (each line: ts, provider, model, prompt_sha256,
response_sha256, status, latency, prev_hash, hash = sha256(prev_hash +
canonical_json(line))) and `run.json` (line count + last hash, so truncation
is detected too).

## Account guard (web providers)

One request in flight (cross-process lock), 20 s minimum spacing, 150/day cap,
and a 6 h cooldown on HTTP 401/403/429 or a challenge / login-wall body —
persisted in `data/state/guard.json`, never retried through. OmniRoute's
native per-connection limits are applied with `scripts/apply_web_limits.py`.
No anti-bot evasion of any kind.

## Development

```bat
python -m pip install -e .
python -m pytest -q                                            :: offline tests (mock server)
python tests\golden\golden.py --model groq/openai/gpt-oss-120b --runs 5   :: live round-trip
python tests\aider_sandbox.py --model combo/webllm-default                 :: live aider check
```

Layout:

```
src/webllm_agent/
├── client.py        OmniRoute chat call (no cache / memory / compression)
├── broadcaster.py   webllm ask: targets, concurrency, rendering, run files
├── journal.py       hash-chained JSONL journal + verify
├── guard.py         account guard for web providers
├── config.py        data/config.yaml loading, excluded models
├── omniroute.py     key from ~/.omniroute/.env at runtime (never stored)
├── cli/main.py      the `webllm` command
└── observability/   logging, debug capture
legacy/              retired v1 Claude/Playwright code (not installed)
```
