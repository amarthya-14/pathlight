"""
AgentExecution — observability log for every agent run (Discovery, Eligibility, and any
agent added later). Every run is logged, including failures: the point of this collection
is to make agent behavior inspectable for debugging and for the evaluation framework
(docs/EVALUATION.md), so a failed run that silently vanished would defeat its purpose.
"""
from datetime import datetime, timezone

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field


class AgentExecution(Document):
    user_id: Indexed(PydanticObjectId)
    agent_name: str  # "discovery" | "eligibility"
    method: str  # "llm" | "deterministic" — which path actually produced the result
    input_summary: str  # truncated snapshot of the input, not the full raw text
    output: dict | None = None
    status: str  # "success" | "error"
    error_message: str | None = None
    latency_ms: float
    opportunity_id: PydanticObjectId | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "agent_executions"
