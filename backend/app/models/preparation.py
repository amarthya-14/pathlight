"""
PreparationPlan / PreparationTask — Gate 6. Per docs/DATABASE.md's "Planned" entry for
these, the task dependency graph uses self-referencing IDs (PreparationTask.depends_on,
a list of sibling task IDs within the same plan), not a separate graph DB — consistent
with this project's repeated Mongo-embedding choice (OpportunityRequirements,
ApplicationStatusEvent) for data that's always written/read together with its parent.

PreparationTask is a plain embedded BaseModel, not its own top-level Document: a task
only ever exists as part of one plan, has no independent query pattern, and Beanie
doesn't auto-assign IDs to embedded sub-documents the way it does for top-level
Documents — so each task's `id` is generated explicitly by the Planner Agent
(app/agents/planner.py) at construction time, specifically so `depends_on` can reference
sibling tasks' IDs before anything is ever persisted.
"""
from datetime import datetime, timezone
from enum import Enum

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel


class TaskStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class PreparationTask(BaseModel):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId)
    skill: str
    title: str
    description: str
    depends_on: list[PydanticObjectId] = Field(default_factory=list)
    estimated_hours: float
    status: TaskStatus = TaskStatus.NOT_STARTED
    order_index: int  # topological position, for display without re-sorting client-side


class PreparationPlan(Document):
    user_id: Indexed(PydanticObjectId)
    opportunity_id: PydanticObjectId
    application_id: PydanticObjectId
    deadline: datetime | None = None
    available_hours: float | None = None  # None = not enough info to estimate feasibility
    total_estimated_hours: float
    feasible: bool | None = None  # None = unknown (no deadline/available_hours given)
    tasks: list[PreparationTask] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "preparation_plans"
        indexes = [
            # One active plan per application — regenerating (e.g. after a new Skill Gap
            # run, or a user-supplied hours/day) replaces it in place rather than
            # accumulating stale plans, same overwrite-on-re-run pattern as Opportunity
            # re-ingestion (see app/graphs/opportunity_pipeline.py).
            IndexModel([("application_id", ASCENDING)], unique=True, name="uq_plan_application"),
        ]
