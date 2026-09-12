"""
Calendar MCP server — Gate 6. Exposes a `create_reminder` tool through the same MCP
tool-calling interface as Filesystem MCP, so the Planner/pipeline reaches "the dedicated
Pathlight calendar" the standardized way rather than a bespoke DB write. See
app/models/calendar_event.py's docstring for why this writes to an internal
CalendarEvent collection rather than a real external calendar for now.

Runs in-process via MCP's in-memory transport, same as filesystem_server.py — no
separate subprocess for a tool this simple.
"""
from datetime import datetime

from beanie import PydanticObjectId
from mcp.server.fastmcp import FastMCP

from app.models.calendar_event import CalendarEvent

mcp = FastMCP("pathlight-calendar")


@mcp.tool()
async def create_reminder(
    user_id: str, title: str, description: str, event_time: str, application_id: str | None = None
) -> dict:
    """
    Creates a reminder event on the user's dedicated Pathlight calendar.
    `event_time` must be an ISO-8601 datetime string; raises ValueError otherwise so the
    caller (a real MCP tool failure) can decide how to degrade, per this project's MCP
    failure-handling principle (see docs/ARCHITECTURE.md §5) — never silently no-ops.
    """
    parsed_time = datetime.fromisoformat(event_time)

    event = CalendarEvent(
        user_id=PydanticObjectId(user_id),
        application_id=PydanticObjectId(application_id) if application_id else None,
        title=title,
        description=description,
        event_time=parsed_time,
    )
    await event.insert()

    return {"id": str(event.id), "title": event.title, "event_time": event.event_time.isoformat()}
