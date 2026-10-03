"""
JobListing — a posting fetched from a public job board (app/sources/job_boards.py).

Global, not per-user (like Opportunity): one row per (source, external_id), refreshed
about twice a day. A listing only becomes an Opportunity + Application — and spends any
LLM quota — when a user chooses to track it; the feed itself is ranked deterministically
(app/sources/job_matching.py).
"""
from datetime import datetime, timezone

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel


class JobListing(Document):
    source: str
    external_id: str
    title: str
    company: str
    location: str = ""
    remote: bool = False
    url: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    # Vocabulary skills found in title+description (app/sources/job_matching.py), computed
    # once at fetch time so ranking a feed never re-scans descriptions.
    skills: list[str] = Field(default_factory=list)
    # Who the role is for (app/sources/job_signals.py), computed at fetch time.
    family: str = "other"
    min_experience: float | None = None
    entry_level: bool = False
    senior: bool = False
    batch_years: list[int] = Field(default_factory=list)
    posted_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "job_listings"
        indexes = [
            IndexModel([("source", ASCENDING), ("external_id", ASCENDING)], unique=True, name="uq_listing_source_id"),
            IndexModel([("fetched_at", DESCENDING)], name="ix_listing_fetched_at"),
        ]


class JobListingCard(BaseModel):
    """Feed projection — everything but the (large) description."""
    id: PydanticObjectId = Field(alias="_id")
    source: str
    title: str
    company: str
    location: str = ""
    remote: bool = False
    url: str
    external_id: str
    posted_at: datetime | None = None
    skills: list[str] = Field(default_factory=list)
    # Who the role is for (app/sources/job_signals.py), computed at fetch time.
    family: str = "other"
    min_experience: float | None = None
    entry_level: bool = False
    senior: bool = False
    batch_years: list[int] = Field(default_factory=list)
