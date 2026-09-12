"""
User and Profile documents.

Profile is deliberately minimal for Gate 2 (cgpa, branch) — Skill/ProfileSkill and the
rest of the profile surface (certifications, resume links) come in once Skill and
ResumeVersion models exist (Gate 3+), per DATABASE.md's confirmed entity list.
"""
from datetime import datetime, timezone

from beanie import Document, Indexed, PydanticObjectId
from pydantic import EmailStr, Field


class User(Document):
    email: Indexed(EmailStr, unique=True)
    hashed_password: str
    full_name: str | None = None
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "profiles"
