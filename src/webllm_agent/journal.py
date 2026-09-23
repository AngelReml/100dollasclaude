"""Append-only JSONL journal, chained by hashes.

Each line is a JSON object with the entry fields plus ``prev_hash`` and
``hash``, where::

    hash = sha256(prev_hash + canonical_json(line_without_hash))

and the first line's ``prev_hash`` is GENESIS. Changing, removing, inserting
or reordering any line breaks the chain from that line on, which
:func:`verify` reports.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GENESIS = "0" * 64
JOURNAL_NAME = "journal.jsonl"


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def line_hash(prev_hash: str, line_without_hash: dict[str, Any]) -> str:
    return sha256_text(prev_hash + canonical_json(line_without_hash))


def _last_hash(path: Path) -> str:
    if not path.exists():
        return GENESIS
    last = GENESIS
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            if raw.strip():
                last = json.loads(raw)["hash"]
    return last


def append(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    """Chain ``entry`` to the end of the journal at ``path`` and return the written line."""
    if "hash" in entry or "prev_hash" in entry:
        raise ValueError("entry must not carry its own hash fields")
    path.parent.mkdir(parents=True, exist_ok=True)
    line = dict(entry)
    line["prev_hash"] = _last_hash(path)
    line["hash"] = line_hash(line["prev_hash"], line)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(canonical_json(line) + "\n")
    return line


@dataclass
class VerifyResult:
    ok: bool
    lines: int
    first_bad_line: int | None = None  # 1-based
    reason: str = ""


def verify(path: Path) -> VerifyResult:
    """Recompute the chain; report the first line that does not match."""
    prev = GENESIS
    count = 0
    with path.open("r", encoding="utf-8") as fh:
        for n, raw in enumerate(fh, start=1):
            if not raw.strip():
                return VerifyResult(False, count, n, "empty line")
            try:
                line = json.loads(raw)
            except json.JSONDecodeError as exc:
                return VerifyResult(False, count, n, f"not valid JSON: {exc}")
            if not isinstance(line, dict) or "hash" not in line or "prev_hash" not in line:
                return VerifyResult(False, count, n, "missing hash fields")
            if line["prev_hash"] != prev:
                return VerifyResult(False, count, n, "prev_hash does not match the previous line")
            body = {k: v for k, v in line.items() if k != "hash"}
            if line_hash(prev, body) != line["hash"]:
                return VerifyResult(False, count, n, "hash does not match the line content")
            prev = line["hash"]
            count += 1
    return VerifyResult(True, count)
