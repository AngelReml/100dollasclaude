# webllm-agent

> **v2 in progress (2026-09-23).** The Playwright/Claude design below is
> retired to `legacy/`. The v2 architecture (OmniRoute gateway + aider +
> `webllm ask` broadcaster) is in `docs/spec.md`. This README is rewritten
> at the end of v2 Phase 6.

Local coding-agent runtime whose LLM transport is a web UI
(Claude.ai, ChatGPT, Gemini, Grok) driven by Playwright.

> The browser is a transport. The provider web app is an adapter.
> The backend is an LLM abstraction. The Agent Engine doesn't
> know Playwright exists.

## Status

| Phase | Status | Notes |
|-------|--------|-------|
| 0 — Skeleton + BrowserManager | **in progress** | target: open Chromium, persist session, close cleanly |
| 1 — Vertical slice (Claude → CLI) | pending | requires a Claude.ai session in the persistent profile |
| 2 — Provider hardening | pending | |
| 3 — Conversation manager + backend | pending | |
| 4 — Read-only tool runtime | pending | |
| 5 — Write-safe + agent loop | pending | |
| 6 — Bash + permissions | pending | |
| 7 — Multi-provider | pending | |
| 8 — Advanced resilience | pending | |

See `docs/spec.md` for the full architecture specification.

## Install (developer mode)

```powershell
python -m pip install -e .
python -m playwright install chromium
```

## Quick start

```powershell
# Phase 0 sanity check: open a browser context, persist nothing, close.
webllm doctor

# Phase 1 will expose `webllm login <provider>` to seed the persistent profile.
```

## Layout

```
src/webllm_agent/
├── browser/         Playwright runtime (only module that imports Playwright)
├── providers/       Provider adapters (Claude, ChatGPT, Gemini, Grok)
├── backend/         WebLLMBackend + ProviderRouter
├── conversations/   Conversation lifecycle & persistence
├── tools/           Tool system (Read/Edit/Write/Bash/...)
├── agent/           Agent Engine + ContextManager + ToolCallParser
├── observability/   Logs, events, run journals
└── cli/             Entry point
```

Runtime data lives under `data/` (created on first run):

```
data/
├── browser_profiles/<provider>/     persistent Chromium user-data
├── state/conversations.json         conversation registry
├── runs/<run_id>/                   per-run journal
├── logs/                            rotating logs
└── config.yaml                      user-overridable config
```
