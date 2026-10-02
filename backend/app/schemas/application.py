"""
Application output schema (Gate 8) — added because the frontend needs to list a user's
Applications with Opportunity context (company/role/deadline) and their most recent
Eligibility/Skill Gap results/status history, none of which was previously fetchable
after ingestion (IngestResponse only returns it once, at ingest time, per docs/API.md).
"""
from datetime import datetime

from beanie import PydanticObjectId
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.agents.schemas import EligibilityResult, SkillGapResult
from app.models.application import ApplicationStage


class ApplicationStatusEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stage: ApplicationStage
    note: str | None
    created_at: datetime


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: PydanticObjectId
    opportunity_id: PydanticObjectId
    company_name: str
    role: str
    deadline: datetime | None
    # Gate 10: where the opportunity came from (manual | gmail_mcp | document:*) and how
    # to apply — shown on the review screen so the user sees where an approval will go.
    source: str | None = None
    apply_email: str | None = None
    application_url: str | None = None
    eligibility: EligibilityResult | None
    skill_gap: SkillGapResult | None
    skill_gap_note: str | None = None
    status_history: list[ApplicationStatusEventOut]
    created_at: datetime


class TailoredResumeOut(BaseModel):
    """Tailored resume + the base resume text it was derived from, so the frontend can
    render a diff without a second request (docs/AUTONOMOUS_APPLICATIONS.md §4/§7)."""
    application_id: PydanticObjectId
    base_document_id: PydanticObjectId
    base_resume_text: str | None
    tailored_text: str
    cover_note: str
    changes_summary: list[str]
    skills_emphasized: list[str]
    confidence: float
    warnings: list[str]
    generated_at: datetime


class ReviewRequest(BaseModel):
    approve: bool


class ReviewResponse(BaseModel):
    outcome: Literal["applied", "manual_apply_required", "skipped"]
    detail: str
    sent_to: str | None = None
    application_url: str | None = None
    application: ApplicationOut
