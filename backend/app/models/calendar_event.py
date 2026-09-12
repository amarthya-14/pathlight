"""
CalendarEvent — Gate 6. Backs the Calendar MCP tool (app/mcp/calendar_server.py).

Scope decision, stated plainly: docs/ARCHITECTURE.md §5 calls for "Calendar MCP (write
access to a dedicated Pathlight calendar only)". A real external calendar (Google
Calendar, etc.) needs an OAuth consent flow and encrypted token storage — and per
docs/SECURITY.md, NO MCP tool in this project has a real OAuth flow yet (Filesystem MCP
needs none; Gmail/GitHub/Calendar were always "planned"). Building real Google Calendar
OAuth for just this one tool, without the token-encryption infrastructure Gate 11 is
supposed to add, would mean either shipping plaintext OAuth tokens (violates
SECURITY.md's own stated principle) or half-building encryption ad hoc under a different
gate's scope. Neither is better than being honest about deferring it.

So for Gate 6, "the dedicated Pathlight calendar" is this CalendarEvent collection —
real, persisted, queryable, and reachable only through the Calendar MCP tool interface
(never written to directly by other code) — not yet a real external calendar. Swapping
in a real Google Calendar API call later is a provider swap behind the same MCP tool
interface, the same isolation pattern app/agents/llm_client.py and
app/retrieval/embeddings.py already use for Gemini — not a redesign.
"""
from datetime import datetime, timezone

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field


class CalendarEvent(Document):
    user_id: Indexed(PydanticObjectId)
    application_id: PydanticObjectId | None = None
    title: str
    description: str
    event_time: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "calendar_events"
