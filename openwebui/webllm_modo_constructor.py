"""
title: Modo constructor
author: webllm (github.com/angelreml/100dollasclaude)
version: 0.1.0
required_open_webui_version: 0.11.0
description: Pide a la IA de webllm su modo de crear una web, una app o unas diapositivas (si lo tiene; se cuenta aparte). webllm nunca pulsa publicar ni desplegar. Es un interruptor en el "+" de la caja de texto.
"""

# Open WebUI "filter" with a switch (PLAN-v5 D22): when it is on, the question carries the mode
# "constructor" to webllm (the pipe forwards body["webllm_modes"]). webllm turns it on in the web chat itself
# and checks on the page that it is on before sending (F4); if the chat does not have it, nothing is sent
# and the answer says so. The AIs by API do not have modes: the answer says that too.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

MODE = "constructor"
ICON = ("data:image/svg+xml;base64,"
        "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ry"
        "b2tlPSJjdXJyZW50Q29sb3IiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49"
        "InJvdW5kIj48cGF0aCBkPSJtMTUgMTItOC41IDguNWEyLjEgMi4xIDAgMCAxLTMtM0wxMiA5Ii8+PHBhdGggZD0iTTE3LjYgNi40"
        "IDIyIDIiLz48cGF0aCBkPSJtMTggMTAtNi02IDMtMyA2IDZ6Ii8+PC9zdmc+")  # a hammer


class Filter:
    class Valves(BaseModel):
        pass

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True  # a switch in the text box, off until Iván turns it on
        self.icon = ICON

    async def inlet(self, body: dict[str, Any]) -> dict[str, Any]:
        modes = list(body.get("webllm_modes") or [])
        if MODE not in modes:
            modes.append(MODE)
        body["webllm_modes"] = modes
        return body
