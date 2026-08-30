"""
Company and Opportunity documents.

Opportunity is global (one row per real posting), not per-user — this is what makes
company+role_hash dedupe meaningful (see ARCHITECTURE.md §6, DATABASE.md). Application
(per-user tracking against an Opportunity) is added in a later gate once the Discovery
Agent is producing real Opportunity rows to apply against.
"""
from datetime import datetime, timezone

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class Company(Document):
    name: Indexed(str, unique=True)

    class Settings:
        name = "companies"


class Opportunity(Document):
    company_id: PydanticObjectId
    role: str
    role_hash: str  # normalized hash for dedupe
    deadline: datetime | None = None
    source: str = "manual"  # manual | gmail_mcp | ...
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "opportunities"
        indexes = [
            # Dedupe key: same company + same role_hash = same posting, even from
            # different sources. Enforced by MongoDB itself, not just application code.
            IndexModel(
                [("company_id", ASCENDING), ("role_hash", ASCENDING)],
                unique=True,
                name="uq_opportunity_company_role_hash",
            ),
        ]
