"""
title: Pensar más
author: webllm (github.com/angelreml/100dollasclaude)
version: 0.1.0
required_open_webui_version: 0.11.0
description: Pide a la IA de webllm que use su modo de pensar más (si lo tiene). Es un interruptor en el "+" de la caja de texto.
"""

# Open WebUI "filter" with a switch (PLAN-v5 D22): when it is on, the question carries the mode
# "pensar" to webllm (the pipe forwards body["webllm_modes"]). Turning it on in the web chat itself,
# and checking on the page that it is really on, is phase F4; until then webllm's answer says so.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

MODE = "pensar"
ICON = ("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAy"
        "NCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJjdXJyZW50Q29sb3IiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJv"
        "a2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNOSAxOGg2Ii8+PHBhdGggZD0iTTEwIDIyaDQiLz48cGF0aCBkPSJNMTIgMmE3IDcgMCAw"
        "IDAtNCAxMi43VjE3aDh2LTIuM0E3IDcgMCAwIDAgMTIgMnoiLz48L3N2Zz4=")  # a light bulb


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
