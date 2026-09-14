from datetime import datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.preparation import TaskStatus


class PreparationPlanRequest(BaseModel):
    # User-supplied estimate of how much prep time they can realistically give this
    # opportunity per day — overrides the pipeline's DEFAULT_HOURS_PER_DAY first-pass
    # guess (see app/agents/planner.py) with a real number and regenerates the plan.
    hours_per_day: float = Field(gt=0)


class PreparationTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: PydanticObjectId
    skill: str
    title: str
    description: str
    depends_on: list[PydanticObjectId]
    estimated_hours: float
    status: TaskStatus
    order_index: int


class PreparationPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: PydanticObjectId
    application_id: PydanticObjectId
    opportunity_id: PydanticObjectId
    deadline: datetime | None
    available_hours: float | None
    total_estimated_hours: float
    feasible: bool | None
    tasks: list[PreparationTaskOut]
    generated_at: datetime
