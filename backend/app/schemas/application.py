"""
Application output schema (Gate 8) — added because the frontend needs to list a user's
Applications with Opportunity context (company/role/deadline) and their most recent
Eligibility/Skill Gap results/status history, none of which was previously fetchable
after ingestion (IngestResponse only returns it once, at ingest time, per docs/API.md).
"""
from datetime import datetime

from beanie import PydanticObjectId
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
    eligibility: EligibilityResult | None
    skill_gap: SkillGapResult | None
    skill_gap_note: str | None = None
    status_history: list[ApplicationStatusEventOut]
    created_at: datetime
