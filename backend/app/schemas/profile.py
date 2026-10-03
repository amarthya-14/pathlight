from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field


class ProfileUpsert(BaseModel):
    cgpa: float | None = Field(default=None, ge=0, le=10)
    branch: str | None = None
    github_username: str | None = None
    experience_years: float | None = Field(default=None, ge=0, le=50)
    college: str | None = Field(default=None, max_length=120)
    graduation_year: int | None = Field(default=None, ge=1990, le=2040)
    target_roles: list[str] = Field(default_factory=list, max_length=8)
    preferred_locations: list[str] = Field(default_factory=list, max_length=8)
    open_to_remote: bool = True
    expected_ctc_lpa: float | None = Field(default=None, ge=0, le=500)
    notice_period: str | None = Field(default=None, max_length=80)
    autopilot_enabled: bool = False
    autopilot_min_match: int = Field(default=75, ge=50, le=95)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: PydanticObjectId | None = None  # None specifically means "no profile created yet"
    user_id: PydanticObjectId
    cgpa: float | None
    branch: str | None
    github_username: str | None = None
    experience_years: float | None = None
    college: str | None = None
    graduation_year: int | None = None
    target_roles: list[str] = []
    preferred_locations: list[str] = []
    open_to_remote: bool = True
    expected_ctc_lpa: float | None = None
    notice_period: str | None = None
    autopilot_enabled: bool = False
    autopilot_min_match: int = 75
    autopilot_last_run: str | None = None
