"""
Skill Gap Agent tests, using the default FakeEmbedder (tests/fakes.py, applied globally
by the `client` fixture) — this sandbox cannot reach Google's embedding API. The exact
distance thresholds this relies on are separately verified empirically in
tests/test_vector_store.py, not just assumed here.
"""
from beanie import PydanticObjectId

from app.agents.skill_gap import run_skill_gap
from app.models.agent_execution import AgentExecution
from app.retrieval.vector_store import index_resume_chunks


async def test_matched_weak_missing_classification(client):
    user_id = str(PydanticObjectId())
    await index_resume_chunks(user_id, "doc-1", "Experienced with Python.")

    result, execution = await run_skill_gap(
        user_id=user_id,
        opportunity_id=str(PydanticObjectId()),
        required_skills=["Python", "AWS"],
        preferred_skills=["Django"],
    )

    assert result.matched == ["Python"]
    assert result.weak == ["Django"]
    assert result.missing == ["AWS"]
    assert execution.agent_name == "skill_gap"
    assert execution.method == "embeddings"
    assert execution.status == "success"


async def test_no_resume_indexed_marks_everything_missing(client):
    user_id = str(PydanticObjectId())
    # deliberately no index_resume_chunks call

    result, execution = await run_skill_gap(
        user_id=user_id,
        opportunity_id=str(PydanticObjectId()),
        required_skills=["Python"],
        preferred_skills=[],
    )

    assert result.matched == []
    assert result.missing == ["Python"]
    assert "has_resume=False" in execution.input_summary


async def test_no_skills_to_check_returns_empty_result(client):
    user_id = str(PydanticObjectId())
    result, execution = await run_skill_gap(
        user_id=user_id,
        opportunity_id=str(PydanticObjectId()),
        required_skills=[],
        preferred_skills=[],
    )
    assert result.matched == []
    assert result.weak == []
    assert result.missing == []


async def test_skill_gap_logs_agent_execution(client):
    user_id = str(PydanticObjectId())
    await index_resume_chunks(user_id, "doc-1", "Experienced with Python.")

    _result, execution = await run_skill_gap(
        user_id=user_id,
        opportunity_id=str(PydanticObjectId()),
        required_skills=["Python"],
        preferred_skills=[],
    )

    logged = await AgentExecution.get(execution.id)
    assert logged is not None
    assert logged.output["matched"] == ["Python"]
