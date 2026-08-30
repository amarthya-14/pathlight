"""
In-process client for the Filesystem MCP server (filesystem_server.py).

This is deliberately a thin, directly-callable wrapper: agents in Gate 4 will reach MCP
tools through LangGraph's own MCP adapter, not this function necessarily. This module
exists so the tool can be built, exercised, and tested standalone before any agent
exists to consume it (see docs/ARCHITECTURE.md Gate 3 scope) — and to document the
actual, verified response shape (list-typed tool results arrive in `structuredContent`,
not by parsing the text content block; see docs/ARCHITECTURE.md Gate 3 notes).
"""
from contextlib import asynccontextmanager

from mcp.shared.memory import create_connected_server_and_client_session

from app.mcp.filesystem_server import mcp as filesystem_mcp


@asynccontextmanager
async def filesystem_session():
    async with create_connected_server_and_client_session(filesystem_mcp) as session:
        yield session


def _raise_if_error(result, tool_name: str) -> None:
    if result.isError:
        message = result.content[0].text if result.content else f"{tool_name} failed"
        raise RuntimeError(message)


def _unwrap_exception_group(exc: BaseException) -> BaseException:
    """
    anyio's TaskGroup (used internally by mcp.shared.memory's in-process transport)
    wraps exceptions raised inside it in a BaseExceptionGroup, even when there's exactly
    one underlying exception. Callers of this module shouldn't need to know that detail
    to catch a plain RuntimeError — unwrap single-exception groups back to the original.
    """
    if isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        return _unwrap_exception_group(exc.exceptions[0])
    return exc


async def mcp_read_document(user_id: str, filename: str) -> str:
    """Reads a document's text content via the Filesystem MCP tool (not direct disk I/O)."""
    try:
        async with filesystem_session() as session:
            result = await session.call_tool("read_document", {"user_id": user_id, "filename": filename})
            _raise_if_error(result, "read_document")
            return result.content[0].text
    except BaseExceptionGroup as eg:
        raise _unwrap_exception_group(eg) from eg


async def mcp_list_documents(user_id: str) -> list[str]:
    """Lists filenames in a user's sandboxed document directory via the Filesystem MCP tool."""
    try:
        async with filesystem_session() as session:
            result = await session.call_tool("list_documents", {"user_id": user_id})
            _raise_if_error(result, "list_documents")
            # Verified empirically: FastMCP puts list-typed returns in structuredContent,
            # not as parseable JSON in the text content block — don't parse result.content here.
            return result.structuredContent["result"]
    except BaseExceptionGroup as eg:
        raise _unwrap_exception_group(eg) from eg
