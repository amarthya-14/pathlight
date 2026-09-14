from pydantic import BaseModel, Field

from app.schemas.application import ApplicationOut


class DashboardHomeOut(BaseModel):
    recent_applications: list[ApplicationOut] = Field(default_factory=list)
    urgent_deadlines: list[ApplicationOut] = Field(default_factory=list)
    total_missing_skills: int = 0
    total_weak_skills: int = 0
    most_common_missing_skills: list[str] = Field(default_factory=list)
    has_profile: bool = False
    has_resume: bool = False
