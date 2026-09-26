"""A harmless MCP server for PLAN-v5 F1/F2 check 5: one tool that says the time (always "10:30", so the
test can check it). Streamable HTTP, as Open WebUI connects to MCP servers natively.
    python tests/openwebui/mcp_hora.py PORT      (needs the "mcp" package; Open WebUI's Python has it)"""

import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("hora", host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 20211)


@mcp.tool()
def hora_actual() -> str:
    """Dice qué hora es ahora mismo."""
    return "Son las 10:30."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
