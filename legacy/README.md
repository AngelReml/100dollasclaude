# legacy/ — retired v1 code (not installed, not imported)

Moved here on 2026-09-23 when the project switched to the v2 architecture
(see `docs/spec.md`). Kept for reference only; nothing under `src/` imports it.

| Path | Why it was retired |
|------|--------------------|
| `browser/manager.py` | Playwright persistent-context / CDP driver. Chrome 136+ ignores `--remote-debugging-port` on the default profile, and the web transport is now OmniRoute. |
| `providers/claude.py`, `providers/selectors.py`, `providers/selectors/` | Claude.ai DOM adapter. Claude is excluded from this tool, and the 2026-09-11 run never got past a Cloudflare challenge. |
| `backend/webllm_backend.py` | Backend wired to `BrowserManager` + `ClaudeProvider`; replaced by the OmniRoute-based broadcaster. |
| `cli/main.py` | Old `doctor` / `login` / `chat` commands (all Playwright/Claude). |
| `scripts/diagnose_claude.py`, `scripts/test_chrome.py` | Claude / Chrome diagnostics. |

The Claude browser profile (`data/browser_profiles/claude`, ~43 MB) was left
untouched on disk; it is git-ignored runtime data.
