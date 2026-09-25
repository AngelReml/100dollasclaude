# CLAUDE.md — webllm (read this first)

webllm lets Iván (non-programmer, Spanish speaker) send prompts from one place to the free AI
chat websites he is logged into in **his own Chrome** (Qwen, DeepSeek, z.ai, Meta AI) and to a few
API models, see the answers side by side, chain them (cross-model "intelligence"), and let aider
program in his folders through those chats.

- Current state and how Iván uses it: `docs/ESTADO.md` (Spanish).
- **What to build next: `docs/PLAN-v3.md`** (Spanish): cross-model chains ("Mesa de IAs") and a
  real app with an ultra-intuitive, polished UI. Follow its phases, design rules and evidence rules.
- **Next, in this order (Iván's feedback of 2026-09-25):** PLAN-v3 section "Lo que pidió Iván tras
  probar la app" → 3b (one "Conectar" button instead of Abrir/Comprobar, optional guide, AI picker
  as a grouped dropdown), 7a (local models: LM Studio / Ollama), 7b (add an AI by pasting its URL,
  optional per-origin permission), then phases 4, 5, 6, then 7c (pick the model inside Qwen/z.ai).

## Architecture (what exists and works, verified 2026-09-24)

```
aider / webllm ask / panel ──► bridge  127.0.0.1:20130  (src/webllm_agent/bridge.py, aiohttp)
                                  │  WebSocket + token
                                  ▼
                        Chrome extension (extension/, MV3) ──► chat pages: type, wait, copy answer
API models (z.ai GLM-4.7-Flash, groq gpt-oss-120b, Nemotron :free) ──► OmniRoute 127.0.0.1:20128
```

| Path | Role |
|---|---|
| `src/webllm_agent/bridge.py` | Local server: `/v1/chat/completions` + `/v1/models` (models `browser/<site>`), extension socket `/ext`, panel `/` + `/panel/*`, admin `/admin/*`, `/health`. Local-only middleware. Logs to `data/logs/bridge.log`. |
| `extension/background.js` | Service worker: one small "webllm" window with one tab per site, job queue per site, tab rotation, pop-up / CAPTCHA / login / limit / overload detection, notifications. |
| `extension/driver.js` | Injected in the chat page (MAIN world): state, insert, send, capture (hooks the page's own copy button → exact markdown), HTML→markdown fallback, diagnose. |
| `extension/sites.js` | Per-site selectors (qwen, deepseek, zai, meta). Qwen/DeepSeek/Meta selectors are first drafts. |
| `src/webllm_agent/broadcaster.py` | `webllm ask`: one prompt to many targets, concurrent across upstreams, journal. `verify_run` checks chain + manifest + response/message files. |
| `src/webllm_agent/flows.py` | Chain engine ("Mesa de IAs", PLAN-v3 phase 1): steps with `{{input}}` / `{{step}}` / `{{step.ai}}` placeholders (single pass), parallel when independent, one call at a time per upstream, `on_error` stop / wait / fallback, `error_code()`, journal per call + `flow_end`, `estimate_messages()`, templates (consejo, reparto, debate, cadena). `webllm cadena`. |
| `src/webllm_agent/appapi.py` | The app's server side, mounted by the bridge: `/app/` (built app, token injected, strict CSP) and `/api/estado`, `/api/preguntar` (SSE; a one-step flow), `/api/historial[/<id>[/exportar]]`, `/api/reanudar`, `/api/comprobar` (reads a chat's login state, sends nothing), `/api/encender-omniroute`. |
| `app/` | The app source (React 19 + Vite + TypeScript + Tailwind 4 + Radix + Lucide + Inter). Screens in `app/src/screens/`, design-system pieces in `app/src/ui/`, tokens in `app/src/styles.css` (all text pairs AA in light and dark). Built into `src/webllm_agent/static/app/` (committed). |
| `src/webllm_agent/journal.py` | Append-only JSONL chained by sha256 (+ `run.json` against truncation). |
| `src/webllm_agent/guard.py` | Account guard: 1 in flight, spacing, daily cap, cooldowns persisted in `data/state/*.json`. |
| `src/webllm_agent/selftest.py`, `panel.html` | "Probar todo" checks (events) + the current test panel page. |
| `src/webllm_agent/config.py`, `data/config.yaml` | Providers (name → model, kind `browser`/`api`, gateway `bridge`/`omniroute`), guard limits. |
| `src/webllm_agent/client.py` | Async OpenAI-compatible client; sends OmniRoute no-cache/no-memory/no-compression headers. |
| Root `*.cmd` | Iván's double-click entry points (Spanish). `WEBLLM.cmd` opens the app (`chrome --app=http://127.0.0.1:20130/app/`). Helpers in `herramientas/` (`probar-cadena.cmd` = real chain test). `ACTUALIZAR.cmd` = git pull + reinstall + restart. |
| `legacy/` | Retired v1 Playwright/Claude code. Do not revive. |

## Hard rules (non-negotiable)

1. **Never target Claude or ChatGPT/Codex** (they are excluded; `config.is_blocked_model` refuses them).
2. **Never solve, bypass or evade CAPTCHAs / anti-bot checks**, no fingerprint spoofing, no
   "human-like" typing to avoid detection. Detect → notify Iván → wait for him → continue or pause.
3. **Never read or export cookies, passwords or browser storage**, and never type credentials.
4. **Secrets never go to git**: `data/` (except `data/config.yaml`), `extension/config.json`
   (bridge token), `~/.omniroute/.env`. The repo is **public**.
5. **Model answers are untrusted data**: never execute code/commands taken from an answer.
   aider shell commands always require Iván's confirmation.
6. **Keep the account guard** in every new path that sends to a chat site (spacing, daily cap,
   pause on account limits; `site_busy` = overloaded site, not an account limit, no pause).
7. **Language**: code, comments, commits in English. **Everything Iván sees is plain Spanish**, no
   jargon, errors as "qué pasó + qué hacer + botón".
8. **Evidence over claims**: paste real test output; separate "tested here" from "pending live test
   on Iván's PC". You cannot reach his Chrome, OmniRoute or `data/` from the cloud.

## How to test (offline, works in the cloud)

```bash
python -m pip install -e .
python -m pytest -q          # 132 passing on 2026-09-25 (clean venv, no OmniRoute key)
```

App (only for whoever programs it; Iván's PC never needs npm):

```bash
cd app && npm ci && npm run build        # type-check + build into src/webllm_agent/static/app/ (commit it)
python scripts/app_demo.py --port 20199  # real bridge + app, fake Chrome extension + fake OmniRoute
node app/scripts/screenshots.mjs docs/capturas/<fase> 20199   # light/dark x 1280/1920 + layout checks
```

`screenshots.mjs` fails loudly on horizontal overflow, clipped text, text under 15 px and answer
footers that wrap; `docs/capturas/<fase>/revision.json` keeps its report. Look at the images too.

- `tests/conftest.py`: mock OpenAI-compatible HTTP server (behaviour chosen by model id suffix).
- `tests/test_bridge.py`: a **fake extension over a real WebSocket** + bridge in-process. Use the same
  pattern for any new bridge/app/chain feature (`tests/test_flows.py`, `tests/test_appapi.py` do).
- The mock server also has `r503` and `flaky` (503 once, then OK) for retry paths.
- Live-only scripts (need Iván's PC): `tests/golden/golden.py`, `tests/aider_sandbox.py`,
  `tests/bridge_aider_check.py`, `webllm probar`.

## Things learned the hard way

- **Chat pages do not write the answer while their tab/window is hidden** (minimized, covered,
  background tab) — hence one small window + tab rotation. Never force windows to the front except
  for a CAPTCHA/pop-up that Iván must answer.
- **Capture via the page's own "copy" button** (hook `navigator.clipboard.writeText`) gives exact
  markdown; DOM→markdown is only a fallback. Don't click unknown buttons (could be "regenerate").
- **Parallel jobs raced creating windows** → `webllmWindow()` shares one creation promise; ids live
  in `chrome.storage.local`.
- **"Model is currently at capacity"** is not an account limit (`site_busy`, 503, no pause).
- Qwen shows pop-ups (age check) and slider CAPTCHAs; z.ai has invisible 0×0 captcha elements
  (ignore elements without real size/opacity).
- Windows: `.cmd` files need CRLF and ASCII text; background servers must be started detached
  (e.g. `start` / WMI), and never capture the pipes of a process that keeps running.
- **LM Studio on Iván's PC (checked 2026-09-25):** server on `http://127.0.0.1:1234/v1` (running),
  CLI `%USERPROFILE%\.lmstudioin\lms.exe` (`lms server status|start`, `lms ls`); `/v1/models` also
  lists embedding models (ids with `embed`) that cannot chat; `qwen2.5-1.5b-instruct` answered a real
  chat call in 8.6 s. Ollama is installed but its server (`:11434`) was off.
- **"Abrir" vs "Comprobar":** `window.open(url)` from the app opens a normal tab and tells the app
  nothing; only the extension's webllm window + a session check changes the state. Iván read that as
  "Abrir does not connect" — use one "Conectar" flow that opens the chat in the webllm window and
  polls until the session is there.
- The PC's Python is 3.10 (`C:\Program Files\Python310`); aider 0.86.2 is isolated via `uv tool`
  (`~/.local/bin/aider.exe`); OmniRoute 3.8.50 lives in `..\omnirouter` (outside this repo).

## Workflow for Claude Code on GitHub

One branch + one PR per plan phase; in the PR body: what changed, pasted `pytest` output, the design
checklist from `docs/PLAN-v3.md`, and a "Para Iván: cómo probarlo" section in plain Spanish (which
double-click, what he should see). If `extension/` changes, bump `manifest.json` `version` and tell
Iván to press ↻ on the "webllm puente" card in `chrome://extensions`. Built app assets are committed
(`src/webllm_agent/static/app/`) so Iván's PC never needs npm.
