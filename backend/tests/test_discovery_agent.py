"""
Discovery Agent tests. The LLM call is faked (tests/fakes.py) — this sandbox cannot
reach Google's Gemini API (see app/agents/llm_client.py). These verify the agent's own
logic: structured-output handling and AgentExecution logging, including on failure.
"""
import pytest
from beanie import PydanticObjectId

from app.agents.discovery import run_discovery
from app.agents.schemas import ExtractedOpportunity
from app.models.agent_execution import AgentExecution
from tests.fakes import FakeLLM


async def test_discovery_success_logs_agent_execution(client, monkeypatch):
    canned = ExtractedOpportunity(company_name="Acme", role="SWE Intern", required_skills=["Python"])
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=canned))

    user_id = str(PydanticObjectId())
    result, execution = await run_discovery(
        "We are hiring a SWE Intern at Acme, Python required.", "manual", user_id
    )

    assert result.company_name == "Acme"
    assert result.role == "SWE Intern"
    assert execution.status == "success"
    assert execution.agent_name == "discovery"

    logged = await AgentExecution.get(execution.id)
    assert logged is not None
    assert logged.output["company_name"] == "Acme"


async def test_discovery_failure_still_logs_agent_execution(client, monkeypatch):
    """Observability principle: a failed run must still be inspectable, not silently lost."""
    monkeypatch.setattr(
        "app.agents.discovery.get_small_llm", lambda: FakeLLM(raise_exc=RuntimeError("Gemini timeout"))
    )

    user_id = str(PydanticObjectId())
    with pytest.raises(RuntimeError, match="Discovery agent failed"):
        await run_discovery("some text", "manual", user_id)

    logged = await AgentExecution.find(AgentExecution.user_id == PydanticObjectId(user_id)).to_list()
    assert len(logged) == 1
    assert logged[0].status == "error"
    assert "Gemini timeout" in logged[0].error_message
