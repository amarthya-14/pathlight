from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict


class ProfileUpsert(BaseModel):
    cgpa: float | None = None
    branch: str | None = None
    github_username: str | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: PydanticObjectId | None = None  # None specifically means "no profile created yet"
    user_id: PydanticObjectId
    cgpa: float | None
    branch: str | None
    github_username: str | None = None
