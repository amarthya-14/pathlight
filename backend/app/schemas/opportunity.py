from datetime import datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict


class OpportunityCreate(BaseModel):
    company_name: str
    role: str
    deadline: datetime | None = None
    source: str = "manual"


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: PydanticObjectId
    role: str
    deadline: datetime | None
    source: str
    created_at: datetime
