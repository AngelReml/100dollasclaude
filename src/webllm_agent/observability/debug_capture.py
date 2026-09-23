"""Debug capture — screenshot + HTML dump when something goes wrong.

Per spec §11 ("Debug opcional: screenshots, HTML snapshots, HAR de red").
The point is: when a selector fails or a response stalls, we leave evidence
on disk so we can debug without re-running the failure.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..config import Paths
from .logging import get_logger

log = get_logger("observability.debug")


async def capture_failure(
    page: Any,  # playwright.async_api.Page — kept loose to avoid import cycle
    paths: Paths,
    *,
    label: str,
    error: Optional[BaseException] = None,
) -> tuple[Path, Path]:
    """Take a screenshot + dump the DOM, return their paths.

    Failures inside the capture itself are logged but never re-raised —
    we never want evidence-gathering to mask the original error.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    safe_label = "".join(ch for ch in label if ch.isalnum() or ch in ("-", "_"))[:40]
    base = f"{ts}_{safe_label or 'failure'}"
    screenshot_path = paths.screenshots_dir / f"{base}.png"
    html_path = paths.dumps_dir / f"{base}.html"

    try:
        await page.screenshot(path=str(screenshot_path), full_page=False)
    except Exception as exc:  # noqa: BLE001
        log.warning("screenshot capture failed: %s", exc)

    try:
        html = await page.content()
        html_path.write_text(html, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log.warning("html dump failed: %s", exc)

    log.warning(
        "captured failure evidence label=%s screenshot=%s html=%s%s",
        label,
        screenshot_path.name,
        html_path.name,
        f" error={error!r}" if error else "",
    )
    return screenshot_path, html_path


def schedule_failure_capture(
    page: Any,
    paths: Paths,
    *,
    label: str,
    error: Optional[BaseException] = None,
) -> "asyncio.Task":
    """Schedule a capture without blocking the caller.

    Used from sync-ish error paths where we don't want to await.
    """
    return asyncio.create_task(capture_failure(page, paths, label=label, error=error))
