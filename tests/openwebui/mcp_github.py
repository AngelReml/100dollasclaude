"""A stand-in for GitHub's official MCP server (PLAN-v5 F9 checks): the same tool names (issue_write,
delete_repository, merge_pull_request, create_or_update_file, get_me), nothing reaches GitHub. Every call that
really runs is written to a log file, so the check can see what ran (only after "Permitir") and what never did.
Streamable HTTP, as Open WebUI connects to MCP servers natively.
    python tests/openwebui/mcp_github.py PORT LOG.jsonl     (needs the "mcp" package; Open WebUI's Python has it)"""

import json
import sys

from mcp.server.fastmcp import FastMCP

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 20212
LOG = sys.argv[2] if len(sys.argv) > 2 else "mcp_github.jsonl"
mcp = FastMCP("github", host="127.0.0.1", port=PORT)
issues: list[dict] = []


def ran(tool: str, **args) -> None:
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"tool": tool, "args": args}, ensure_ascii=False) + "\n")


@mcp.tool()
def get_me() -> str:
    """El usuario de GitHub del token."""
    ran("get_me")
    return "angelreml"


@mcp.tool()
def issue_write(method: str, owner: str, repo: str, title: str, body: str = "") -> str:
    """Crea (method=create) o cambia (method=update) un issue."""
    ran("issue_write", method=method, owner=owner, repo=repo, title=title, body=body)
    issues.append({"title": title})
    return f"Creado el issue #{len(issues)} en {owner}/{repo}: {title}"


@mcp.tool()
def create_or_update_file(owner: str, repo: str, path: str, content: str, message: str, branch: str) -> str:
    """Crea o cambia un archivo en una rama."""
    ran("create_or_update_file", owner=owner, repo=repo, path=path, branch=branch)
    return f"Guardado {path} en la rama {branch}"


@mcp.tool()
def merge_pull_request(owner: str, repo: str, pullNumber: int) -> str:  # noqa: N803 (GitHub's own name)
    """Fusiona un pull request."""
    ran("merge_pull_request", owner=owner, repo=repo, pullNumber=pullNumber)
    return "Fusionado"


@mcp.tool()
def delete_repository(owner: str, repo: str) -> str:
    """Borra un repositorio entero."""
    ran("delete_repository", owner=owner, repo=repo)
    return "Borrado"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
