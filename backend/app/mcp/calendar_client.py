"""
In-process client for the Calendar MCP server (calendar_server.py). Mirrors
filesystem_client.py's pattern exactly, including the anyio exception-group unwrapping —
see that module's docstring for why it's needed.
"""
import json
from contextlib import asynccontextmanager
from datetime import datetime

from mcp.shared.memory import create_connected_server_and_client_session

from app.mcp.calendar_server import mcp as calendar_mcp


@asynccontextmanager
async def calendar_session():
    async with create_connected_server_and_client_session(calendar_mcp) as session:
        yield session


def _raise_if_error(result, tool_name: str) -> None:
    if result.isError:
        message = result.content[0].text if result.content else f"{tool_name} failed"
        raise RuntimeError(message)


def _unwrap_exception_group(exc: BaseException) -> BaseException:
    if isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        return _unwrap_exception_group(exc.exceptions[0])
    return exc


async def mcp_create_reminder(
    user_id: str, title: str, description: str, event_time: datetime, application_id: str | None = None
) -> dict:
    """Creates a reminder event via the Calendar MCP tool. Raises on failure (invalid
    event_time, DB error) — callers (the LangGraph pipeline) must catch this and proceed
    without a reminder rather than block, per docs/ARCHITECTURE.md §5's MCP failure
    principle: an MCP tool failure degrades that step, it never crashes the pipeline."""
    try:
        async with calendar_session() as session:
            result = await session.call_tool(
                "create_reminder",
                {
                    "user_id": user_id,
                    "title": title,
                    "description": description,
                    "event_time": event_time.isoformat(),
                    "application_id": application_id,
                },
            )
            _raise_if_error(result, "create_reminder")
            # Verified empirically (unlike list-typed MCP tool results — see
            # filesystem_client.py's docstring — a dict-typed FastMCP tool return does
            # NOT populate structuredContent; it arrives as a JSON string in the text
            # content block). Don't assume either shape without checking.
            return json.loads(result.content[0].text)
    except BaseExceptionGroup as eg:
        raise _unwrap_exception_group(eg) from eg
