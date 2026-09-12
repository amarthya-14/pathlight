from pydantic import BaseModel, Field

from app.agents.schemas import EligibilityResult, SkillGapResult


class IngestRequest(BaseModel):
    """Ingest either raw text directly, or a reference to a previously-uploaded
    Document (read via the Filesystem MCP tool) — exactly one of the two must be set."""
    raw_text: str | None = None
    document_id: str | None = None
    source: str = "manual"


class IngestResponse(BaseModel):
    opportunity_id: str
    application_id: str
    company_name: str
    role: str
    eligibility: EligibilityResult | None = None
    skill_gap: SkillGapResult | None = None
    skill_gap_note: str | None = None
    needs_human_review: bool = False
    error: str | None = None
