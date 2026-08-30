"""
Filesystem MCP server — exposes sandboxed document read/list tools through the Model
Context Protocol, so agents (starting Gate 4) reach uploaded documents through the same
standardized tool-calling interface they'll use for Gmail/GitHub/Calendar MCP later,
rather than a bespoke "just read the file" path that only this one use case gets.

Runs in-process (see filesystem_client.py) via MCP's in-memory transport — no separate
subprocess needed for a tool this simple and always-local.
"""
from mcp.server.fastmcp import FastMCP

from app.mcp.sandbox import resolve_safe_path, user_dir

mcp = FastMCP("pathlight-filesystem")


@mcp.tool()
def list_documents(user_id: str) -> list[str]:
    """List filenames available in this user's sandboxed document directory."""
    return sorted(p.name for p in user_dir(user_id).iterdir() if p.is_file())


@mcp.tool()
def read_document(user_id: str, filename: str) -> str:
    """
    Read a document's raw text content by filename, scoped to the given user's sandboxed
    directory. Rejects any filename that would resolve outside that directory (a path
    traversal attempt) rather than silently reading from elsewhere on disk.
    """
    path = resolve_safe_path(user_id, filename)  # raises ValueError on traversal attempts

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"No such document for this user: {filename!r}")

    return path.read_text(encoding="utf-8", errors="replace")
