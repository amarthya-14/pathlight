"""
Application output schema (Gate 8) — added because the frontend needs to list a user's
Applications with Opportunity context (company/role/deadline) and their most recent
Eligibility/Skill Gap results/status history, none of which was previously fetchable
after ingestion (IngestResponse only returns it once, at ingest time, per docs/API.md).
"""
from datetime import datetime

from beanie import PydanticObjectId
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    # What the posting asks for in experience (None = it doesn't say / unknown), and
    # whether Pathlight has the real job description or only an alert's title+company.
    min_experience_years: float | None = None
    has_job_description: bool = False
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
    ats: dict | None = None
    generated_at: datetime


class KitAnswer(BaseModel):
    question: str
    answer: str
    note: str = ""


class KitLink(BaseModel):
    label: str
    url: str


class ApplicationKitOut(BaseModel):
    answers: list[KitAnswer]
    connection_note: str
    referral_message: str
    search_links: list[KitLink]


class StatusUpdateRequest(BaseModel):
    # Post-application progress the user records themselves (Pathlight can't see a
    # company's ATS): online assessment, interview, offer, rejection.
    stage: Literal["OA", "INTERVIEW", "OFFER", "REJECTED"]
    note: str | None = Field(default=None, max_length=500)


class RecheckRequest(BaseModel):
    # Optional: the full job description. Without it, eligibility is simply re-run on the
    # current data (e.g. after updating CGPA or experience in Profile).
    job_description: str | None = None


class TailorRequest(BaseModel):
    # Skills the student says they know that the resume doesn't show. Saved to their
    # profile (so later tailoring and autopilot use them too) and added to Technical Skills.
    add_skills: list[str] = Field(default_factory=list, max_length=30)


class TailoredEditRequest(BaseModel):
    tailored_text: str = Field(min_length=50, max_length=20000)
    cover_note: str = Field(min_length=1, max_length=5000)


class ReviewRequest(BaseModel):
    approve: bool


class ReviewResponse(BaseModel):
    outcome: Literal["applied", "manual_apply_required", "skipped"]
    detail: str
    sent_to: str | None = None
    application_url: str | None = None
    application: ApplicationOut
