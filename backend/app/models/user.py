"""
User and Profile documents.

Profile is deliberately minimal for Gate 2 (cgpa, branch) — Skill/ProfileSkill and the
rest of the profile surface (certifications, resume links) come in once Skill and
ResumeVersion models exist (Gate 3+), per DATABASE.md's confirmed entity list.
"""
from datetime import datetime, timezone

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, EmailStr, Field


class AiKey(BaseModel):
    provider: str  # gemini | groq | openai | anthropic | custom
    encrypted_key: str
    last4: str
    strong_model: str
    small_model: str
    base_url: str | None = None  # custom OpenAI-compatible providers
    added_at: datetime


class User(Document):
    email: Indexed(EmailStr, unique=True)
    hashed_password: str
    full_name: str | None = None
    # The student's own AI provider keys (app/core/ai_providers.py), tried in this order
    # before Pathlight's shared keys. Ciphertext only; never returned by the API.
    ai_keys: list[AiKey] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"


class Profile(Document):
    # unique=True enforces the 1:1 User<->Profile relationship at the DB level, the same
    # role SQLAlchemy's `unique=True` FK column played before the Mongo switch.
    user_id: Indexed(PydanticObjectId, unique=True)
    cgpa: float | None = None
    branch: str | None = None
    # Gate 6: optional, used by the Skill Gap Agent as a GitHub MCP evidence lookup key
    # (see app/mcp/github_server.py). Public username only — no OAuth/private-repo
    # access exists yet, see that module's scope-decision docstring.
    github_username: str | None = None
    # Years of full-time work experience (0 = fresher). Checked against a posting's
    # min_experience_years by the Eligibility Agent.
    experience_years: float | None = None
    # Who's using Pathlight — asked during onboarding, used to rank the job feed
    # (target roles, locations) and to frame the app (graduation year -> fresher roles).
    college: str | None = None
    graduation_year: int | None = None
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    open_to_remote: bool = True
    # Application-form answers Pathlight can't infer from the resume (Application kit).
    expected_ctc_lpa: float | None = None
    notice_period: str | None = None  # e.g. "Immediate", "Available from June 2027"
    # Job-feed listings the student hid ("source:external_id"), newest last, capped.
    dismissed_jobs: list[str] = Field(default_factory=list)
    # Autopilot (app/workers/autopilot.py): each morning, prepare the best new matches —
    # tracked, checked and tailored, waiting for review. Never applies by itself.
    autopilot_enabled: bool = False
    autopilot_min_match: int = 75
    autopilot_last_run: str | None = None  # IST date of the last run
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "profiles"
