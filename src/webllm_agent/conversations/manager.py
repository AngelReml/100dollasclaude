"""ConversationManager — register, persist, and resume provider conversations.

Phase 1 keeps this deliberately simple: a JSON file under
`data/state/conversations.json`. Phase 3 may swap this for SQLite if we
need concurrency / querying.

Schema (versioned so we can evolve):

    {
      "version": 1,
      "providers": {
        "<provider>": {
          "last_conversation_id": "<id>",
          "items": [
            { "id": "...", "provider": "...", "url": "...",
              "page_id": "...", "title": "...", "state": "READY",
              "created_at": "...", "last_activity": "..." }
          ]
        }
      }
    }
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..observability.logging import get_logger
from ..providers.base import Conversation

log = get_logger("conversations")


class ConversationManager:
    """JSON-backed registry of conversations per provider."""

    SCHEMA_VERSION = 1

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir
        self._path = state_dir / "conversations.json"
        self._lock = threading.Lock()
        self._data: dict = self._load()

    # --------------------------------------------------------------------- load

    def _load(self) -> dict:
        if not self._path.exists():
            return {"version": self.SCHEMA_VERSION, "providers": {}}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            log.warning("corrupt conversations.json — starting fresh: %s", exc)
            return {"version": self.SCHEMA_VERSION, "providers": {}}
        if not isinstance(data, dict) or "providers" not in data:
            return {"version": self.SCHEMA_VERSION, "providers": {}}
        return data

    def _save(self) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False, default=str)
        tmp.replace(self._path)

    # ------------------------------------------------------------------- public

    def register(self, conv: Conversation) -> None:
        """Insert or update a conversation entry."""
        with self._lock:
            bucket = self._data["providers"].setdefault(conv.provider, {"items": []})
            items: list = bucket["items"]
            existing_idx = next(
                (i for i, it in enumerate(items) if it["id"] == conv.id), None
            )
            payload = {
                "id": conv.id,
                "provider": conv.provider,
                "url": conv.url,
                "page_id": conv.page_id,
                "title": conv.title,
                "state": conv.state,
                "created_at": conv.created_at.astimezone(timezone.utc).isoformat(),
                "last_activity": conv.last_activity.astimezone(timezone.utc).isoformat(),
            }
            if existing_idx is None:
                items.append(payload)
            else:
                items[existing_idx] = payload
            bucket["last_conversation_id"] = conv.id
            self._save()
        log.info("registered conversation id=%s provider=%s", conv.id, conv.provider)

    def last(self, provider: str) -> Optional[Conversation]:
        """Return the most recent conversation for `provider`, if any."""
        bucket = self._data["providers"].get(provider)
        if not bucket:
            return None
        last_id = bucket.get("last_conversation_id")
        items = bucket.get("items") or []
        if last_id:
            for raw in items:
                if raw["id"] == last_id:
                    return self._from_raw(raw)
        if items:
            return self._from_raw(items[-1])
        return None

    def get(self, provider: str, conversation_id: str) -> Optional[Conversation]:
        for raw in (self._data["providers"].get(provider) or {}).get("items") or []:
            if raw["id"] == conversation_id:
                return self._from_raw(raw)
        return None

    def list(self, provider: str) -> list[Conversation]:
        items = (self._data["providers"].get(provider) or {}).get("items") or []
        return [self._from_raw(it) for it in items]

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _from_raw(raw: dict) -> Conversation:
        return Conversation(
            id=raw["id"],
            provider=raw["provider"],
            url=raw["url"],
            page_id=raw.get("page_id"),
            title=raw.get("title", ""),
            state=raw.get("state", "READY"),
            created_at=datetime.fromisoformat(raw["created_at"]),
            last_activity=datetime.fromisoformat(raw["last_activity"]),
        )
