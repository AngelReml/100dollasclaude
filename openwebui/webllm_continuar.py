"""
title: Continuar en la web
author: webllm (github.com/angelreml/100dollasclaude)
version: 0.1.0
required_open_webui_version: 0.11.0
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJjdXJyZW50Q29sb3IiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTUgM2g2djYiLz48cGF0aCBkPSJNMTAgMTQgMjEgMyIvPjxwYXRoIGQ9Ik0xOCAxM3Y2YTIgMiAwIDAgMS0yIDJINWEyIDIgMCAwIDEtMi0yVjhhMiAyIDAgMCAxIDItMmg2Ii8+PC9zdmc+
description: Abre esta conversación en la web de ese chat, en tu Chrome, para seguir escribiendo allí a mano. webllm guarda cada mensaje tuyo y cada respuesta en esta misma conversación de tu historial y de tu memoria.
"""

# Open WebUI "action" (a button under each answer, PLAN-v5 F6 / D16). It only asks webllm: webllm finds the
# question by Open WebUI's own ids (the pipe sent them with it), opens that exact conversation of the web chat
# in a normal tab of Iván's Chrome (not webllm's small window) and records what he writes there (observer mode:
# it looks, it never clicks or types). An answer from an AI by API has no web conversation: it says so.

from __future__ import annotations

from typing import Any, Awaitable, Callable

import aiohttp
from pydantic import BaseModel, Field

ICON = ("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNC"
        "IgZmlsbD0ibm9uZSIgc3Ryb2tlPSJjdXJyZW50Q29sb3IiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdH"
        "Jva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTUgM2g2djYiLz48cGF0aCBkPSJNMTAgMTQgMjEgMyIvPjxwYXRoIGQ9Ik0xOC"
        "AxM3Y2YTIgMiAwIDAgMS0yIDJINWEyIDIgMCAwIDEtMi0yVjhhMiAyIDAgMCAxIDItMmg2Ii8+PC9zdmc+")  # an arrow out of a window


class Action:
    class Valves(BaseModel):
        WEBLLM_URL: str = Field(default="http://127.0.0.1:20130", description="Dónde está webllm en tu PC.")
        WEBLLM_TOKEN: str = Field(default="", description="La llave de webllm (la pone el instalador).")

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.icon_url = ICON

    async def action(self, body: dict[str, Any],
                     __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None = None) -> None:
        ok, text = await self.ask(str(body.get("chat_id") or ""), str(body.get("id") or ""))
        if __event_emitter__ is not None:
            # a notice only: the answer's own status line ("Respondió X…", what was really used) stays as it is
            await __event_emitter__({"type": "notification", "data": {"type": "success" if ok else "warning", "content": text}})

    async def ask(self, chat_id: str, message_id: str) -> tuple[bool, str]:
        try:
            timeout = aiohttp.ClientTimeout(total=90)  # opening the page may take a while
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.post(f"{self.valves.WEBLLM_URL}/gw/v1/continuar",
                                  json={"chat_id": chat_id, "message_id": message_id},
                                  headers={"Authorization": f"Bearer {self.valves.WEBLLM_TOKEN}"}) as r:
                    data = await r.json(content_type=None)
                    status = r.status
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return False, "webllm está apagado: ábrelo con su icono y vuelve a pulsar «Continuar en la web»."
        if status == 200 and isinstance(data, dict) and data.get("ok"):
            return True, (f"Abierta en tu Chrome la conversación de {data.get('label') or 'ese chat'}. Sigue escribiendo allí: "
                          "webllm guarda cada mensaje tuyo y cada respuesta aquí, en tu historial.")
        err = data.get("error") if isinstance(data, dict) else None  # {"error": "texto"} or {"error": {"message": ...}}
        text = err.get("message") if isinstance(err, dict) else err
        return False, str(text or "webllm no pudo abrir la conversación.")
