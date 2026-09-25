# webllm-agent (v2)

> 🚧 **UNDER CONSTRUCTION / EN CONSTRUCCIÓN.** Your own Chrome drives the AI chat
> pages (Qwen, DeepSeek, z.ai, Meta AI) through a local extension + bridge that
> looks like an OpenAI API, so aider can program with them. Verified in the
> user's own Chrome on 2026-09-24 (z.ai and DeepSeek answered; aider fixed a test
> through the z.ai chat); Qwen and Meta still being tuned. See [docs/ESTADO.md](docs/ESTADO.md).
>
> ```
> aider / webllm ask ──► bridge 127.0.0.1:20130 ──► Chrome extension ──► chat page (type, wait, copy)
> ```
> Double-click files (Spanish UI): `1 - INSTALAR (solo una vez)` · `2 - PROBAR TODO` · `PREGUNTAR` ·
> `PROGRAMAR` · `REANUDAR`. Start with `LEEME - EMPIEZA AQUI.txt`. Helper scripts live in `herramientas/`.

Type one prompt and send it to several AI providers at once — or to one —
through a single local gateway, and let a coding agent apply changes to a
folder on your PC.

> Day-to-day instructions (in Spanish): **[docs/ESTADO.md](docs/ESTADO.md)**.
> Next build: **[docs/PLAN-v3.md](docs/PLAN-v3.md)**. Agents working on this repo: read **[CLAUDE.md](CLAUDE.md)** first.
> Architecture: [docs/spec.md](docs/spec.md).

## Pieces

| Piece | What it is | Status |
|---|---|---|
| Gateway | [OmniRoute](https://github.com/diegosouzapw/OmniRoute) 3.8.50 on `http://127.0.0.1:20128/v1` (OpenAI-compatible), installed in `..\omnirouter` | running |
| Coding agent | [aider](https://aider.chat) 0.86.2 (isolated via `uv tool`), launched with `aider-omniroute.cmd` | working |
| Broadcaster | `webllm ask` (this package) | working |
| Chrome extension + bridge | `extension/` (MV3) + `src/webllm_agent/bridge.py` on `127.0.0.1:20130`: the user's Chrome chats as `browser/<site>` models | working (z.ai, DeepSeek verified) |
| Chain engine ("Mesa de IAs") | `src/webllm_agent/flows.py`: steps that use earlier answers, 4 templates, `webllm cadena` | tests pass; live run pending (PLAN-v3 phase 1) |
| App | `app/` (React + Vite + TS + Tailwind), built into `src/webllm_agent/static/app/`, served at `http://127.0.0.1:20130/app/` with its API (`src/webllm_agent/appapi.py`); opened by `WEBLLM.cmd` | Inicio, Preguntar, Historial + first-time guide; tests + screenshots in `docs/capturas/fase3/`; live test pending (PLAN-v3 phase 3) |
| Local models | `src/webllm_agent/local.py`: LM Studio / Ollama models listed as "En tu PC" in the app, called directly (no OmniRoute, no account guard, one call at a time per program) | tests + fake LM Studio; live test pending (PLAN-v3 7a) |
| Next | Add an AI by URL, Mesa de IAs screen, Programar, single icon | planned: `docs/PLAN-v3.md` 7b, phases 2, 4-6 |

Providers are mapped in `data/config.yaml` (name → model id, in priority
order): `browser/*` models are the chat pages driven in the user's own Chrome
by `extension/` through the bridge (no cookies are copied anywhere); the rest
go through OmniRoute. Claude and ChatGPT/Codex are excluded and always refused.

## Commands

```bat
WEBLLM.cmd                                :: starts everything and opens the app (chrome --app)
"1 - INSTALAR (solo una vez).cmd"         :: starts everything, opens chrome://extensions, copies the extension path
"2 - PROBAR TODO.cmd"                     :: real end-to-end check, BIEN / MAL per item (webllm probar)
PREGUNTAR.cmd                             :: ask all AIs (or one)
PROGRAMAR.cmd                             :: drop a project folder on it; aider edits it through a Chrome chat
REANUDAR.cmd                              :: lift pauses after fixing an account
herramientas\webllm.cmd ask "prompt" --to todas|qwen|deepseek|zai-chat|meta|zai|groq|nemotron|<model-id>
herramientas\webllm.cmd status | journal verify --all | puente diagnosticar <site>
herramientas\webllm.cmd cadena prueba|consejo|reparto|debate|cadena|archivo [--gasto]
herramientas\probar-cadena.cmd            :: real "Reparto + integración" with 2 Chrome chats + 1 API AI
herramientas\start-omniroute.cmd / stop-omniroute.cmd / iniciar.cmd / aider-omniroute.cmd
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
