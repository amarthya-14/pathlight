"""
Skill Gap Agent tests, using the default FakeEmbedder (tests/fakes.py, applied globally
by the `client` fixture) — this sandbox cannot reach Google's embedding API. The exact
distance thresholds this relies on are separately verified empirically in
tests/test_vector_store.py, not just assumed here.
"""
import httpx
from beanie import PydanticObjectId

from app.agents.skill_gap import _skill_explicitly_negated, run_skill_gap
from app.models.agent_execution import AgentExecution
from app.retrieval.vector_store import index_resume_chunks


def _mock_github_repos(monkeypatch, repos):
    async def _fake_get(self, url, params=None, headers=None):
        request = httpx.Request("GET", url)
        return httpx.Response(200, json=repos, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)


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


async def test_negation_guard_overrides_close_distance_to_missing(client):
    """
    Regression test for the real bug found during the Gate 6 manual smoke test against
    the live Gemini API (see docs/ARCHITECTURE.md §15): a resume line disclaiming a
    skill embeds just as close to that skill's name as a line claiming it, because both
    contain the word. FakeEmbedder's "django" bucket doesn't know about negation either
    (it matches on the substring "django" regardless of context) — this is exactly what
    lets this test exercise the override deterministically, without needing real
    embeddings, by putting the skill in a bucket that would otherwise score as a match.
    """
    user_id = str(PydanticObjectId())
    await index_resume_chunks(user_id, "doc-1", "No experience with Django or REST APIs in production.")

    result, _execution = await run_skill_gap(
        user_id=user_id,
        opportunity_id=str(PydanticObjectId()),
        required_skills=["Django"],
        preferred_skills=[],
    )

    assert result.matched == []
    assert result.weak == []
    assert result.missing == ["Django"]


def test_skill_explicitly_negated_detects_common_disclaimer_phrasing():
    assert _skill_explicitly_negated("No experience with Kubernetes or Rust.", "Kubernetes")
    assert _skill_explicitly_negated("Not familiar with Rust.", "Rust")
    assert not _skill_explicitly_negated("Experienced with Python and Django.", "Django")


async def test_github_evidence_attached_for_weak_and_missing_only(client, monkeypatch):
    user_id = str(PydanticObjectId())
    await index_resume_chunks(user_id, "doc-1", "Experienced with Python.")
    _mock_github_repos(
        monkeypatch,
        [{"name": "aws-lambda-toy", "description": "AWS demo", "language": "Python", "topics": ["aws"]}],
    )

    result, _execution = await run_skill_gap(
        user_id=user_id,
        opportunity_id=str(PydanticObjectId()),
        required_skills=["Python", "AWS"],
        preferred_skills=["Django"],
        github_username="octocat",
    )

    assert result.matched == ["Python"]
    assert result.weak == ["Django"]
    assert result.missing == ["AWS"]
    # Matched skill never looked up on GitHub — resume evidence is already strong.
    assert "Python" not in result.github_evidence
    # Weak/missing skills that had no GitHub match simply aren't keyed in.
    assert "Django" not in result.github_evidence
    assert result.github_evidence["AWS"] == ["aws-lambda-toy (Python)"]
    assert result.github_unavailable is False


async def test_github_evidence_unavailable_on_failure_does_not_block(client, monkeypatch):
    async def _fake_get_error(self, url, params=None, headers=None):
        request = httpx.Request("GET", url)
        return httpx.Response(404, json={"message": "Not Found"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get_error)
    user_id = str(PydanticObjectId())
    await index_resume_chunks(user_id, "doc-1", "Experienced with Python.")

    result, _execution = await run_skill_gap(
        user_id=user_id,
        opportunity_id=str(PydanticObjectId()),
        required_skills=["Python", "AWS"],
        preferred_skills=[],
        github_username="no-such-user",
    )

    # Classification is unaffected by the GitHub failure — it degrades evidence, not
    # the pipeline (docs/ARCHITECTURE.md §5's MCP failure principle).
    assert result.matched == ["Python"]
    assert result.missing == ["AWS"]
    assert result.github_evidence == {}
    assert result.github_unavailable is True


async def test_no_github_username_skips_lookup_entirely(client, monkeypatch):
    def _fail_if_called(*a, **k):
        raise AssertionError("Should not call GitHub when no username is configured")

    monkeypatch.setattr(httpx.AsyncClient, "get", _fail_if_called)
    user_id = str(PydanticObjectId())
    await index_resume_chunks(user_id, "doc-1", "Experienced with Python.")

    result, _execution = await run_skill_gap(
        user_id=user_id,
        opportunity_id=str(PydanticObjectId()),
        required_skills=["Python", "AWS"],
        preferred_skills=[],
    )

    assert result.github_evidence == {}
    assert result.github_unavailable is False


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
