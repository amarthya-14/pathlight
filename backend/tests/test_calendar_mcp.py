"""
Tests for the Calendar MCP server/client (app/mcp/calendar_server.py,
app/mcp/calendar_client.py). See app/models/calendar_event.py's docstring for why this
writes to an internal CalendarEvent collection rather than a real external calendar.
"""
from datetime import datetime, timezone

from beanie import PydanticObjectId

from app.mcp.calendar_client import calendar_session, mcp_create_reminder
from app.models.calendar_event import CalendarEvent


async def test_create_reminder_persists_calendar_event(client):
    user_id = str(PydanticObjectId())
    event_time = datetime(2027, 3, 1, tzinfo=timezone.utc)

    result = await mcp_create_reminder(
        user_id=user_id,
        title="Acme Corp deadline",
        description="Application deadline for Backend Intern",
        event_time=event_time,
    )

    assert result["title"] == "Acme Corp deadline"

    stored = await CalendarEvent.get(PydanticObjectId(result["id"]))
    assert stored is not None
    assert stored.title == "Acme Corp deadline"
    # Mongo (and mongomock) round-trips datetimes as naive UTC, same as every other
    # datetime field in this codebase — compare on that basis, not tz-aware equality.
    assert stored.event_time == event_time.replace(tzinfo=None)


async def test_create_reminder_invalid_time_rejected_by_server(client):
    # Exercises the server's own datetime.fromisoformat validation directly (a raw
    # session call, bypassing the client's event_time.isoformat() call) — the client
    # wrapper always hands the server a valid ISO string by construction, so this is the
    # only way to reach the server's own rejection path.
    async with calendar_session() as session:
        result = await session.call_tool(
            "create_reminder",
            {
                "user_id": str(PydanticObjectId()),
                "title": "Bad event",
                "description": "",
                "event_time": "not-a-real-datetime",
                "application_id": None,
            },
        )
        assert result.isError
