# CLAUDE.md — webllm (read this first)

webllm lets Iván (non-programmer, Spanish speaker) send prompts from one place to the free AI
chat websites he is logged into in **his own Chrome** (Qwen, DeepSeek, z.ai, Meta AI) and to a few
API models, see the answers side by side, chain them (cross-model "intelligence"), and let aider
program in his folders through those chats.

- Current state and how Iván uses it: `docs/ESTADO.md` (Spanish).
- **Where this is going: `docs/VISION.md`** (Spanish): a frontier-level coding workshop made of free
  AIs; seven concepts (sources, skills, router, workshop, memory, guard, one chat). Anything built
  must fit one of them.
- **What to build next: `docs/PLAN-v5.md`** (Spanish, 2026-09-25; supersedes PLAN-v4): Open WebUI
  Desktop is the face, webllm the engine (its one OpenAI-compatible connection: every source and
  skill is a "model"). The Committee is mandatory (role → `CONFIRMO:` → problem → closed verdict →
  one fusion document by the strongest available AI). Memory has one writer (journal → one-way
  export to an Obsidian vault in Drive). Web layer self-repairs in 4 layers and records chats Iván
  continues by hand. Every web chat found (27) is preloaded from a catalog; Iván only logs in.
  **Iván's absolute control comes first (D21):** nothing switches AI/model/mode silently, every
  answer states what was really used (read back from the page; if unconfirmed, nothing is sent),
  nothing leaves his PC without his gesture, and webllm never clicks publish/share/delete/
  regenerate/deploy. Each chat's models (strongest first), modes (think, search, deep research,
  builder…), "+" menu tools and file uploads are discovered read-only and offered in the standard
  UI (D22) via a webllm "pipe" in Open WebUI. The code workshop (F11) may change any of Iván's files but never
  runs elevated, so Windows itself protects the OS (D24: refuse to start if elevated or UAC off/never-notify, Job
  Object with memory/CPU caps, no shutdown/logoff/elevation/recursive deletes outside the project). Phases F0 (stabilize; Meta) → F1 (face spike,
  12 checks) → F2 (gateway) → F3 (catalog) → F4 (each chat's capabilities) → F5 … F12, each with
  an entry gate and a measurable exit.
- `docs/PLAN-v3.md` still holds the design rules, contract and evidence rules (and what 3b, 7a, 7b
  and the lost-answer fix did, all done 2026-09-25, pending Iván's live test).

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
| `extension/background.js` | Service worker: one small "webllm" window with one tab per site, job queue per site, tab rotation, pop-up / CAPTCHA / login / limit / overload detection, notifications. Messages: `job`, `diagnose` (reuses an open tab, never reloads it), `show` (0.4.0: bring the chat forward so Iván can log in), `add_site` (0.5.0). While a chat waits for Iván (`needsHuman`: challenge / popup / hidden = window covered) that time does not count against any job's limit (`jobClock`), that tab stays in front, and `job_alive` tells the bridge every 10 s. A job the bridge sends carries `site_config` {name, url} for sites added from the app. 0.9.0 (F7): a job with `continue_url` goes back to that conversation (same origin, https, else `bad_continue_url`); if the page lands elsewhere or shows no previous answer nothing is typed (`conversation_lost`); model/modes are not touched; only a NEW copy button (or, without one, a new answer with text) counts as the answer, and only a new copy button is captured (`no_new_answer` if what is read equals what was there). |
| `extension/common.js`, `add.html`, `add.js` | Address rules shared with the server (`parseChatUrl`, `siteKey`, blocked hosts, `genericSite`), and the "Añadir … a webllm" page: `chrome.permissions.request` for that one origin (needs Iván's click), then `add_test` → open the site, find the box, `add_ready` (the bridge sends the "pong" test through the guard). |
| `extension/driver.js` | Injected in the chat page (MAIN world): state, insert, send, capture (hooks the page's own copy button → exact markdown), HTML→markdown fallback, diagnose. |
| `extension/sites.js` | Per-site selectors (qwen, deepseek, zai, meta). Qwen/DeepSeek/Meta selectors are first drafts. |
| `src/webllm_agent/gateway.py`, `problems.py` | PLAN-v5 D2 (F1): `/gw/v1/models` + `/gw/v1/chat/completions`, webllm as Open WebUI's one connection. Each question is a one-step flow (guard, journal, history "Desde Open WebUI", error codes); notes stream as `reasoning_content` (incl. `WAITING_SHORT` "te espera"); SSE keep-alive comments; the last chunk carries `webllm.avisos` (must-see: files/modes not used yet, a stand-in answered). Body extension `webllm: {chat_id, message_id, task, files[b64+sha256], modes}`; a `task` never reaches a web chat; files are checked, saved under the run (`kind: gateway` journal line, verified by `verify_run`). `problems.py` = the app's Spanish texts (a test keeps it in sync with `app/src/fix.ts`, both ways). F2: web chats go through `flows.run_flow`; APIs and this PC's models go direct (`_direct`/`_upstream`: streamed as written, `tools`/`tool_calls` passed through, JSON answers to a stream request re-chunked, only a stand-in configured in `fallback_models` is ever tried and it is said), always ending with `Respondió X [con modelo]`. `/gw/v1/parar` = "Parar todo" (gateway questions + `AppApi.stop_all` + `bridge.cancel_all`). |
| `src/webllm_agent/catalog.yaml`, `catalog.py` | PLAN-v5 F3: the 27 web chats (key, url, group tuyas/1/2, purpose, family, tags, account, `private`, own `daily_cap`, `may_fail`, note); packaged. What Iván did with each: `data/state/catalog_state.json` (`sin_conectar` / `conectada` / `no_funciona` + reason + page diagnosis for F6 / `no_la_quiero`). A connected one is a custom AI with `catalog: true` (its cap and privacy come from the catalog). `catalog.eligible_for_auto(p)` = what F7/F8 must use: never a non-private one (Arena, Google AI Studio). Built-in chats are matched by site (`browser/zai` is `zai-chat`; `zai` is the API). |
| Conectores (app + `/api/catalogo`, `/api/conectar-varias`) | "Conectar varias": `add_many` → the extension's `add.html?batch=` asks Chrome ONCE for every origin → `add_many_permission`; then the server tries them one by one with `add_check` (extension 0.6.0: waits `wait_login_s` for Iván's login with the tab in front; a login page on another address = login, any other address = `moved`) → `add_ready` → "pong" through the guard (`_send_test`, shared with "+ Añadir otra IA", which now connects a catalog address as that catalog chat). Parar lets go of the current one. |
| F4: each chat's card (`fichas.py`, driver `discover` / `chooseModel` / `setMode` / `attach` / `downloads` / `teach`) | `data/state/fichas/<site>.json` = what "Descubrir" read (menus opened, read, closed; no option pressed, nothing sent) + Iván's `strongest_by_ivan`; `data/state/patches/<site>.json` = where Iván showed things ("Enséñame", sent as `site_patch`, reversible with `/olvidar`). Model order: catalog `models` table (source, date); unknown = "nuevo, sin datos", a tie is never guessed. Gateway ids `site@slug` pick a model; plain `site` = the strongest or the page's own. A job carries `want` {model, modes} and `files` (sent before it as `file_part`s of 512 KB); the extension puts and CONFIRMS each on the page or nothing is sent (`not_confirmed`, `model_not_in_page`, `mode_not_in_page`, `file_not_attached`, `forbidden`), then returns `used` (+ `modes_on`) and `downloads` (blob/data files, saved by the bridge in `data/descargas/<run>/`, verified by `verify_run`). Every click goes through `safeClick` (`common.js FORBIDDEN_RE`, 8 languages). Expensive modes (investigar, constructor) are guarded apart (`guard.expensive_daily_cap`). |
| `openwebui/webllm_modo_*.py` | Five switches in Open WebUI's "+" (pensar, buscar, investigar, constructor, imagen) → `webllm_modes`. |
| `src/webllm_agent/vault.py` (+ `app/src/ui/Memoria.tsx`) | PLAN-v5 F5, D5 as Iván updated it (26-sep): the vault anywhere; the conversation note AND each answer of each AI in its own dated file. ONE writer that never reads the vault (it only checks the vault folder exists, so it never recreates it where Iván moved it from; it knows what it wrote from `data/state/vault_index.json`). One background thread (`_Writer`; `vault.flush()` in tests, on bridge shutdown and before the CLI exits): a slow/closed Drive never holds a question up; after a failure the next write rewrites everything missed. `<vault>/webllm/`: `<Proyecto>/<date> <title>.md` per conversation (key `owui:<chat_id>` or `run:<id>`; project = the Open WebUI folder, title = its title, both sent by the pipe's `_where` and journaled in the gateway line; rebuilt whole, atomic), `Respuestas/<IA>/<YYYY-MM-DD HH.MM.SS> <IA> - <question>.md` (written once per vault, `answers_done`; body after `## Respuesta` = the response file byte for byte), `Adjuntos/<run>/` (copied only if the sha still matches), `Índice.md`, `Comités/` (`write_committee`, for F7). `defuse()` makes Templater `<%`, dataview fences and `$=` inert (Templater's "trigger on new file creation" runs JS in NEW files). Fed by `flows.to_vault` (run_flow start / each answer / end; gateway direct), gateway `_record` (the question before the answer), panel and `webllm ask`. `flow.json` is written once (`flows.write_flow`): the writer thread may be reading it. App: `/api/memoria` GET/POST, `/api/memoria/reescribir`, `/api/memoria/anteriores` (history). |
| F6: webs that repair themselves + observer (`repair.py`, driver `xray` / `tryPatch` / `observe`, `openwebui/webllm_continuar.py`) | Layer 1 = wider generic detection (9 languages, modern boxes). Layer 3: on `no_input` / `empty_answer` the extension returns an `xray` (numbered candidates, the page's own `sel`/`general` selectors, NO conversation text: an answer is its length + `after_your_message`); `bridge._repair` asks the helper AI (`repair.helper`: private API/local only, default z.ai, `data/state/reparar.json`, on by default) for candidate NUMBERS only (`repair.parse` rejects anything else), `try_patch` checks it on the page sending nothing, then `fichas.add_patch` (dated, `by: ia:<name>`, undo one by one in the Ficha: `/api/ficha/<ai>/deshacer`); `no_input` is then sent once, `empty_answer` is `reread` (never resent). Every attempt in `data/state/reparaciones.jsonl`. Layer 4 = "Enséñame esta web" (3 clicks: input, send, answer; each tried with `try_patch`). Daily check (`AppApi.check_all`, `check` message, sends nothing; `revision.json`; `_daily_loop` when quiet). "Parar" also presses the site's stop (`pressStop`, `safeClick`). Observer (extension 0.8.0): `observe` message → normal tab, `startObserving` listens (Enter / send click, capture phase, before the page badge shows) and polls every 1.5 s; each turn → `{"type":"observed"}` → `flows.record_observed` (its own run, `kind: observed`, `follows`/`follows_root`, `by: ivan`, guard `note` = counts, never waits); a tab's later turns follow its first one (`AppApi.tab_conversation`, and `observe_follows` tells the extension, kept in `chrome.storage.session`); with the bridge down a turn waits in `chrome.storage.local` `pending_observed` (`sendObserved`, flushed on connect). Popup "Registrar esta conversación". "Continuar en la web": app `/api/continuar`, Open WebUI action → `/gw/v1/continuar` (finds the run by the pipe's chat_id + message_id, strictly). Back in Open WebUI, `flows.hand_turns` (`data/state/escritos_en_la_web.json` index) + `gateway.with_hand_turns` put the hand-written turns where they happened, with an aviso. Tests: `tests/test_repair.py`, `tests/extension/repair_flow.mjs` (16), `tests/openwebui/f6_checks.mjs`. |
| `src/webllm_agent/committee.py`, `committee_face.py` | PLAN-v5 F7, the Committee (model `comite` = "webllm · Comité", first in `/gw/v1/models`, no switches/button in Open WebUI). The face: the idea gets a PLAN and nothing is sent (`comite_pendientes.json`, 24 h; files kept apart); "adelante" re-plans and runs the STORED plan only if the people are the same, else shows the new one; "cancela" / "con 3|5" / "sin|con pensar"; `task` → 400. The plan must name everything that may receive the idea or the files (`files_line`: web all, API/this PC images only, reserves if they enter, fusion none; every fusion AI). The engine (`run`): role → `CONFIRMO: <rol>` (one shorter retry, then a reserve with the same role) → problem in the same conversation (web `continue_url`, API the whole `messages`) inside a random-tag data block → closed verdict (one reformat, then discarded + reserve) → `count` FOR vs AGAINST, always odd (4 valid: the last is `uncounted`) → fusion by the list, a non-participant first, verdicts by ROLE with every name `redact`ed, 8 `SECTIONS` (one retry; next AI only if the call fails). Web chats one at a time (`web_slots`), two if `parallel_web` (off: untested on Iván's PC). Journal head `committee`, each call with its role, a `committee_count` line; progress as `reasoning_content`; document = webllm's count header + fusion + who wrote it; vault `Comités/` with the annex (AI names + seal). App: `/api/comite` (card on Inicio). Settings `data/state/comite.json`. |
| `src/webllm_agent/budget.py` | PLAN-v5 F2 daily cap per AI by API (`guard.api_daily_cap`, default 300; per provider `daily_cap`; this PC's models uncapped): every call counts, stand-ins too; `data/state/api_budget.json`. `AppApi.usage()` is the one source of "today / cap" for the app and `/gw/v1/models` (chat sites: the guard's). |
| Stop ("parar") | Each question's tag (= run id) travels as `x-webllm-run` to the bridge: `bridge.jobs[site] = (job_id, tag)`, `bridge.stop(tag)` (a queued question is never sent), `bridge.cancel(site, tag)` (resolves it as `cancelled` and sends `{"type":"cancel"}`; extension 0.5.2 `stillWanted()` stops driving the page; since 0.8.0 (F6) it also presses the site's own stop button, `pressStop` through `safeClick`). `run_flow(stop=Event)`: the call in progress ends as `cancelled`, no retry/stand-in/next step, journal still closed. The app's questions register in `AppApi.asking`. |
| `openwebui/` | Functions Open WebUI runs: `webllm_pipe.py` (manifold pipe: models from the gateway, current message's files from `metadata.user_message` read whole from Open WebUI storage, `webllm_modes`, local answers for Open WebUI's background tasks, notes on the status line, whole-answer mode for `stream: false`), `webllm_modo_*.py` (filters with `self.toggle` = switches in the "+"). Installed by `scripts/openwebui_setup.py` (idempotent: functions + valves, per-model `file_context` off / `filterIds`, background tasks and compaction off, bypass embedding, Spanish suggestions, no Arena, tool permissions on; finds Open WebUI on 8080/3000/8081). Iván: `herramientas\poner-en-openwebui.cmd`. Results: `docs/F1-cara.md`. |
| `src/webllm_agent/broadcaster.py` | `webllm ask`: one prompt to many targets, concurrent across upstreams, journal. `verify_run` checks chain + manifest + response/message files. |
| `src/webllm_agent/flows.py` | Chain engine ("Mesa de IAs", PLAN-v3 phase 1): steps with `{{input}}` / `{{step}}` / `{{step.ai}}` placeholders (single pass), parallel when independent, one call at a time per upstream, `on_error` stop / wait / fallback, `error_code()`, journal per call + `flow_end`, `estimate_messages()`, templates (consejo, reparto, debate, cadena). `webllm cadena`. |
| `src/webllm_agent/appapi.py` | The app's server side, mounted by the bridge: `/app/` (built app, token injected, strict CSP) and `/api/estado`, `/api/preguntar` (SSE; a one-step flow), `/api/historial[/<id>[/exportar]]`, `/api/reanudar`, `/api/comprobar` (reads a chat's login state, sends nothing), `/api/conectar` (same + `show` when there is no session; the app then polls `comprobar` every 3 s up to 3 min), `/api/encender-omniroute`, `/api/encender-local`, `/api/anadir` (+ `GET /api/anadir/<id>` progress), `/api/quitar`, `/api/icono/<key>`. Added sites live in `data/state/custom_ais.json` (+ `icons/`), never in `data/config.yaml` (in git). `estado` gives each AI `custom`, `icon`, `waiting`. |
| `src/webllm_agent/local.py` | AIs "En tu PC" (PLAN-v3 7a): discovers LM Studio (:1234) / Ollama (:11434) / `local_servers` in config, lists `/v1/models` minus embeddings, remembers them in `data/state/local_models.json`, gateway `local` (no guard, one call at a time per server, the server's own model id), start command (`lms server start` / `ollama serve`). Providers are named `<server>:<model>`. |
| `app/` | The app source (React 19 + Vite + TypeScript + Tailwind 4 + Radix + Lucide + Inter). Screens in `app/src/screens/`, design-system pieces in `app/src/ui/`, tokens in `app/src/styles.css` (all text pairs AA in light and dark). Built into `src/webllm_agent/static/app/` (committed). |
| `src/webllm_agent/journal.py` | Append-only JSONL chained by sha256 (+ `run.json` against truncation). |
| `src/webllm_agent/guard.py` | Account guard: 1 in flight, spacing, daily cap, cooldowns persisted in `data/state/*.json`. |
| `src/webllm_agent/selftest.py`, `panel.html` | "Probar todo" checks (events) + the current test panel page. |
| `src/webllm_agent/config.py`, `data/config.yaml` | Providers (name → model, kind `browser`/`api`, gateway `bridge`/`omniroute`), guard limits. |
| `src/webllm_agent/client.py` | Async OpenAI-compatible client; sends OmniRoute no-cache/no-memory/no-compression headers. |
| Root `*.cmd` | Iván's double-click entry points (Spanish). `WEBLLM.cmd` opens the app (`chrome --app=http://127.0.0.1:20130/app/`). Helpers in `herramientas/` (`probar-cadena.cmd` = real chain test). `ACTUALIZAR.cmd` = git pull + reinstall + restart. |
| `legacy/` | Retired v1 Playwright/Claude code. Do not revive. |

## Hard rules (non-negotiable)

1. **Never target claude.ai or ChatGPT/Codex directly**, nor Iván's own Claude/ChatGPT/Codex
   subscriptions through OmniRoute (`config.is_blocked_model` and the blocked hosts refuse them).
   **Iván approved on 2026-09-25 services that use Claude or GPT inside** (Duck.ai, Poe, Perplexity,
   Arena, Copilot…); inside them any model may be picked.
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
python -m pip install -e ".[test]"   # pytest + pydantic (the openwebui/ functions use it)
python -m pytest -q          # see the latest count in docs/ESTADO.md (the real-Chromium tests need node, app/node_modules, Chromium, openssl;
                             # tests/test_openwebui_face.py also needs WEBLLM_OPENWEBUI_PY = a Python with open-webui)
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
- `tests/test_local.py`: a fake LM Studio (models incl. an embedding one, concurrency counter).
- `scripts/app_demo.py` also fakes LM Studio, an installed-but-off Ollama, and a Meta AI that
  "logs in" 6 s after `show` (to see "Conectar" turn green without a second click).
- `tests/extension/` (`test_extension_driver.py` runs them): **the real extension in Chromium** with
  the real bridge (`app_demo.py --sin-chrome`) and `fake_chat.html` served over https under
  `*.test` names (`harness.mjs`): `generic_driver.mjs`, `add_flow.mjs` (add a site),
  `captcha_flow.mjs` (a verification solved after 20 s with a 10 s limit; a covered window),
  `stuck_stop.mjs` (four misleading "stop" buttons), `parar_flow.mjs` ("Parar todo" mid-answer),
  `catalog_flow.mjs` ("Conectar varias" on 5 test sites; `startWorld({catalog, loginWaitS})` writes a test
  catalog for `app_demo.py --catalogo`), `capabilities_flow.mjs` (F4 on `fake_chat.html?completa=1`: a model
  menu, a "+" menu, mode toggles, file input, a blob download, "Publicar"; every click logged in
  `window.__clicks`), `repair_flow.mjs` (F6 on `fake_chat.html?extranjera=1` / `?rara=1`: layers 1, 3, 4, undo, Parar, the daily check, the observer; `WEBLLM_EXTENSION_DIR` = an older extension, to show each case fails with it), `conversation_flow.mjs` (F7 on `fake_chat.html` `/conversa/`: two turns in the same chat, a lost conversation, another site's address, `/conversa/tarda/` = 15 s before answering and no stop button). `tests/openwebui/f4_checks.mjs` = Open WebUI + the real extension; `f6_checks.mjs` = the "Continuar en la web" button; `f7_checks.mjs` = the Committee (plan, adelante, progress, document, lock, vault annex). Only
  Chrome's permission prompt and window occlusion are simulated (headless never reports a covered
  window, so the page is told `document.hidden`). Chromium must get `--no-proxy-server` here.
- Watch out for `\b`, `\t` in Windows paths written from scripts: a literal backspace once ended up
  in this file. Check with `grep -P '[\x00-\x08]'`.
- Live-only scripts (need Iván's PC): `tests/golden/golden.py`, `tests/aider_sandbox.py`,
  `tests/bridge_aider_check.py`, `webllm probar`.

## Things learned the hard way

- **Chat pages do not write the answer while their tab/window is hidden** (minimized, covered,
  background tab) — hence one small window + tab rotation. Never force windows to the front except
  for a CAPTCHA/pop-up that Iván must answer.
- **Capture via the page's own "copy" button** (hook `navigator.clipboard.writeText`) gives exact
  markdown; DOM→markdown is only a fallback. Don't click unknown buttons (could be "regenerate").
- **Time waiting for Iván must never count as the chat being slow** (2026-09-25, his live report):
  the answer limit ran while he solved a CAPTCHA, the app hung up at 7 min while the bridge waited 9,
  rotation took the CAPTCHA tab away every 2 s, and a covered window stopped the page while the clock
  ran; the late answer reached nobody. Keep every wait layer longer than the one below it, and keep
  "waiting for Iván" out of the clocks.
- **The chain engine asks the browser chats one at a time** (`upstream_key("browser/x") == "browser"`),
  although the bridge/extension allow one per site in parallel with tab rotation. Parallel was never
  tested on Iván's PC; change it only with a live test.
- **"Finished" = the stop button is gone, so a false stop hides a finished answer** (Iván's Meta,
  2026-09-25). `driver.js` only reads a button's own name (aria-label, title, test id, short text),
  whole words, enabled and on screen; `background.js` ignores a stop already there before sending and
  ends when a new copy button has been stable for 12 s. A timeout logs the page's `diagnose`.
  (`desktop` does NOT contain `stop`: check such claims, the test caught it.)
- **Open WebUI (0.11.4) facts that shaped F1** (read in its code, checked on screen): it sends background
  jobs (title, tags, follow-ups, emoji, query, autocomplete; `__task__`) to the SAME model, so the pipe
  answers them itself and the gateway refuses them for web chats; `__files__` holds every file of the
  conversation (use `metadata.user_message.files`); the reasoning block is folded, so must-see notes go
  to the status line (`__event_emitter__` status); API keys are OFF by default (`ENABLE_API_KEYS`);
  the "$" skill picker inserts `<$id|name>` tags (plain "$name" text is not a mention); with
  `stream: false` a pipe must return text, not the SSE lines.
- **Stopping must reach Chrome before the task dies** (F2): aiohttp's `TestServer` cancels a handler when
  the client goes (`handler_cancellation=True`; production `run_app` does not), and awaiting a task
  propagates that cancellation into it. The gateway awaits its work through `asyncio.shield` and tells the
  bridge/extension first. Tests that pass only because of handler cancellation prove nothing about Iván's PC.
- **Open WebUI sends the whole conversation**: anything matched in a prompt (the demo's "(demo: N minutos)")
  must look at the last question only. A streamed error is `data: {"error": …}` with no `choices`; Open
  WebUI shows it, so the pipe must pass it on (and drop only lines that are not JSON).
- **Open WebUI 0.11.4 tool approval bug:** with `tool_approval_mode="ask"` the `function_call` stays
  "queued" and a "Preparando <tool>…" spinner stays after the answer; "full" mode records it. The stream
  from webllm is identical in both: not ours, kept on (Iván's click before any tool use).
- **A list the page refreshes must not reset what Iván chose** (F3): the "Conectar varias" checklist was
  re-marked every 4 s because its init effect depended on an array rebuilt each render; initialise on open
  only. Found by the screenshot script, not by a unit test: look at the flows, not only at the checks.
- **A page reload resets what a test page logs** (F4): "Descubrir" opens the chat afresh, so a click log
  sliced with the old page's length proved nothing ("clics []"). Assert the positive (the menu triggers were
  clicked) as well as the negative (no option).
- **Open WebUI's integration menu rows are the buttons** (`aria-pressed`), the switch is drawn inside and
  does not take clicks; with several switches, "the first switch" is not "Pensar más".
- **aiohttp's WebSocket takes 4 MB per message by default**: files a chat produces come back through it, so
  the bridge sets `max_msg_size` (64 MB); files TO the extension travel in 512 KB parts.
- **Match configured chats by site, not by name**: z.ai's chat provider is `zai-chat` and `zai` is its API;
  a test that passed by that name coincidence proved nothing.
- **AI text in Obsidian can run code** (F5): Templater with "trigger on new file creation" executes `<%* … %>` in any
  NEW file, and Dataview runs `dataviewjs` blocks and `$=` queries when a note opens. webllm creates new files from
  AI answers, so the vault copy is defused (visibly, reversible, original in the journal).
- **Run ids sort by the second, then a random suffix**: questions asked in the same second (tests, fast APIs) come
  out in a random order by id. The vault orders a conversation by its journal's first `ts` (milliseconds). Test scripts too: find new runs by name (a set of the ones seen before), never by position in a sorted list (F6: a question made in the same second as the hand-written turn sorted before it, and the check read the wrong run).
- **Open WebUI (0.11.4) keeps a chat's folder and title in its own DB**: the pipe reads them with
  `Chats.get_chat_title_by_id`, `Chats.get_chat_folder_id(chat_id, user_id)` and
  `Folders.get_folder_by_id_and_user_id` (async); a new chat may already carry Open WebUI's title at its first question.
- **A provider's `error.code` is its own vocabulary** (OpenRouter: 429/402 numbers, z.ai: "1302"):
  `flows.error_code` only passes webllm's own codes (`OWN_ERROR_CODES`) and reads the rest like the
  HTTP status; a 429 that mentions credits is still a limit. Unknown codes made the app say
  "no pudo responder".
- **A client keeps only the first 500 characters of an error body** (F6): the extension's `empty_answer` carries the page's whole diagnosis; appended to the bridge's message it pushed `"code"` out of the excerpt and `error_code` read the 502 as `overloaded` (Iván would have read "Rara está saturada"). The bridge's errors now put `code` first and keep the detail short (the log has it); `error_code` also reads a cut-short body.
- **An observer that only polls the text box misses a message pasted and sent between two looks** (F6): note what is sent at the moment of sending (Enter / send click, capture phase), and start listening BEFORE the page shows "registrando" (the test typed the moment the badge appeared). Compare the answer against the page as it was before sending: his own message appearing is not an answer.
- **Open WebUI does not have what Iván wrote by hand in the web**: without `flows.hand_turns` the next question would silently lose it. And a tab found by its URL may be another tab on the same URL (the popup test found step 8's tab).
- **Continuing a conversation, "the page changed" is not "an answer began"** (F7): the generic last-answer block includes Iván's own
  message, and the last copy button is still the previous answer's. A model that thinks 15 s before writing got the previous answer
  back as the new one, silently. Require a NEW copy button (or a new answer with text) and capture only a new one.
- **A test that passes by timing luck proves nothing** (F7): with a 9 s "thinking" delay the old rule passed because it gave up at
  11.5 s; 15 s (a real thinking model) showed the bug. Pick delays longer than the rule's own timers.
- **Iván's "adelante" consents to what the plan says, nothing more** (F7, D21): reserves, backup fusion AIs and images sent to APIs
  mixed with a PDF all received his idea/files while the plan did not name them. Found by reading the doc against the code; each
  now has a test that fails with the old rule. The same company under two names ("z.ai" / "Zhipu (z.ai)") counted twice.
- **A per-site lock is not a cap** (F7): "two web chats at once" let 3 write at once; a test measures the real concurrency.
- **Parallel jobs raced creating windows** → `webllmWindow()` shares one creation promise; ids live
  in `chrome.storage.local`.
- **"Model is currently at capacity"** is not an account limit (`site_busy`, 503, no pause).
- Qwen shows pop-ups (age check) and slider CAPTCHAs; z.ai has invisible 0×0 captcha elements
  (ignore elements without real size/opacity).
- Windows: `.cmd` files need CRLF and ASCII text; background servers must be started detached
  (e.g. `start` / WMI), and never capture the pipes of a process that keeps running.
- **LM Studio on Iván's PC (checked 2026-09-25):** server on `http://127.0.0.1:1234/v1` (running),
  CLI `%USERPROFILE%\.lmstudio\bin\lms.exe` (`lms server status|start`, `lms ls`); `/v1/models` also
  lists embedding models (ids with `embed`) that cannot chat; `qwen2.5-1.5b-instruct` answered a real
  chat call in 8.6 s. Ollama is installed but its server (`:11434`) was off.
- **"Abrir" vs "Comprobar":** `window.open(url)` from the app opens a normal tab and tells the app
  nothing; only the extension's webllm window + a session check changes the state. Iván read that as
  "Abrir does not connect". Fixed with one "Conectar" (`app/src/ui/Connect.tsx`): never open chat
  pages with `window.open` from the app.
- The PC's Python is 3.10 (`C:\Program Files\Python310`); aider 0.86.2 is isolated via `uv tool`
  (`~/.local/bin/aider.exe`); OmniRoute 3.8.50 lives in `..\omnirouter` (outside this repo).

## Workflow for Claude Code on GitHub

One branch + one PR per plan phase; in the PR body: what changed, pasted `pytest` output, the design
checklist from `docs/PLAN-v3.md`, and a "Para Iván: cómo probarlo" section in plain Spanish (which
double-click, what he should see). If `extension/` changes, bump `manifest.json` `version` and tell
Iván to press ↻ on the "webllm puente" card in `chrome://extensions`. Built app assets are committed
(`src/webllm_agent/static/app/`) so Iván's PC never needs npm.
