"""
Company and Opportunity documents.

Opportunity is global (one row per real posting), not per-user — this is what makes
company+role_hash dedupe meaningful (see ARCHITECTURE.md §6, DATABASE.md). Application
(per-user tracking against an Opportunity) lives in app/models/application.py, added at
Gate 4 once the Discovery Agent is producing real Opportunity rows to apply against.

OpportunityRequirement is implemented as an EMBEDDED sub-document (OpportunityRequirements
below), not a separate top-level collection — see ARCHITECTURE.md §11/§13 for why: this
data is written once by the Discovery Agent and always read together with its parent
Opportunity, which is exactly the case MongoDB's document embedding is suited for.
"""
from datetime import datetime, timezone

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel


class Company(Document):
    name: Indexed(str, unique=True)

    class Settings:
        name = "companies"


class OpportunityRequirements(BaseModel):
    """Structured eligibility criteria extracted by the Discovery Agent (Gate 4). All
    fields are optional because extraction may not find every field in a given source
    text — the Eligibility Agent treats an unset field as 'no deterministic check
    possible for this criterion', not as 'requirement not present, so it's a free pass'."""
    min_cgpa: float | None = None
    allowed_branches: list[str] | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    compensation: str | None = None
    raw_eligibility_text: str | None = None  # qualitative text the LLM may need to interpret


class Opportunity(Document):
    company_id: PydanticObjectId
    role: str
    role_hash: str  # normalized hash for dedupe
    deadline: datetime | None = None
    source: str = "manual"  # manual | gmail_mcp | ...
    requirements: OpportunityRequirements | None = None
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
