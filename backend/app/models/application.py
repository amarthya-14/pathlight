"""
Application model — per-user tracking against an Opportunity, and the home for the
Eligibility Agent's result (Gate 4).

ApplicationStatus history is an EMBEDDED array (status_history below), not a separate
top-level collection with a foreign key — see ARCHITECTURE.md §11 for why: MongoDB
naturally fits "one Application, many status events" as a document with a growing array,
appended to via $push (see app/graphs/opportunity_pipeline.py), never mutated in place,
which preserves the append-only audit guarantee the original relational design called for.
"""
from datetime import datetime, timezone
from enum import Enum

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel

from app.agents.schemas import EligibilityResult, SkillGapResult


class ApplicationStage(str, Enum):
    DISCOVERED = "DISCOVERED"
    ELIGIBILITY_CHECKED = "ELIGIBILITY_CHECKED"
    PREPARING = "PREPARING"
    READY_TO_APPLY = "READY_TO_APPLY"
    APPLIED = "APPLIED"
    OA = "OA"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    # Gate 10 (docs/AUTONOMOUS_APPLICATIONS.md §4): outcomes of the human review gate.
    MANUAL_APPLY_REQUIRED = "MANUAL_APPLY_REQUIRED"  # approved, but no apply_email to send to
    SKIPPED_BY_USER = "SKIPPED_BY_USER"  # reviewed the tailored resume, chose not to apply


class ApplicationStatusEvent(BaseModel):
    stage: ApplicationStage
    note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Stages after which the user has already decided — the pipeline never re-tailors or
# re-opens review for these, so re-ingesting a posting can't trigger a second send.
REVIEW_DECIDED_STAGES = {
    ApplicationStage.APPLIED,
    ApplicationStage.MANUAL_APPLY_REQUIRED,
    ApplicationStage.SKIPPED_BY_USER,
}


class Application(Document):
    user_id: Indexed(PydanticObjectId)
    opportunity_id: PydanticObjectId
    eligibility: EligibilityResult | None = None  # most recent result — history is in status_history
    skill_gap: SkillGapResult | None = None  # most recent result (Gate 5)
    status_history: list[ApplicationStatusEvent] = Field(default_factory=list)
    # Gate 10: set atomically by POST /api/applications/{id}/review the moment a review
    # decision is claimed (see app/api/routes/applications.py::_claim_review) — this is
    # what makes a double-clicked Approve send exactly one email, not two.
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "applications"
        indexes = [
            # One Application per (user, opportunity) — re-running the pipeline on the
            # same opportunity updates the existing Application, never duplicates it.
            IndexModel(
                [("user_id", ASCENDING), ("opportunity_id", ASCENDING)],
                unique=True,
                name="uq_application_user_opportunity",
            ),
        ]
