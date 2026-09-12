"""
Structured I/O schemas for agents. Kept separate from app/models/ because these are
LLM structured-output contracts (what we ask Gemini to return), not database documents —
though EligibilityResult is also embedded directly into the Application document
(app/models/application.py) since it's small and always read together with its parent.

Deliberately importable without pulling in any agent/LLM code, so app/models/ can depend
on these schemas without a circular import.
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExtractedOpportunity(BaseModel):
    """What the Discovery Agent extracts from raw source text (an email, a pasted JD).
    Every field is optional except company_name/role — extraction should leave fields
    null/empty rather than invent values not present in the source text (see the
    Discovery Agent's system prompt in app/agents/discovery.py)."""
    company_name: str
    role: str
    deadline: datetime | None = None
    min_cgpa: float | None = None
    allowed_branches: list[str] | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    compensation: str | None = None
    raw_eligibility_text: str | None = None


class EligibilityDecision(str, Enum):
    ELIGIBLE = "eligible"
    PARTIALLY_ELIGIBLE = "partially_eligible"
    NOT_ELIGIBLE = "not_eligible"
    UNCERTAIN = "uncertain"


class EligibilityResult(BaseModel):
    """Every eligibility decision must carry this full shape — never a bare verdict.
    See docs/AI_DESIGN.md's non-negotiable rule."""
    decision: EligibilityDecision
    reason: str
    evidence: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: float


class SkillGapResult(BaseModel):
    """Skill Gap Agent output (Gate 5). Classification is a plain embedding-distance
    threshold, not an LLM judgment — see app/agents/skill_gap.py for why."""
    matched: list[str] = Field(default_factory=list)
    weak: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
