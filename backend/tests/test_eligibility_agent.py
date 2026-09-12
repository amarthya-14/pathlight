"""
Eligibility Agent tests. Deterministic paths are verified to NEVER call the LLM — not
just that the returned decision looks right, but that get_strong_llm is never even
invoked (a monkeypatch that raises AssertionError if called catches this directly). The
one LLM-only path uses a fake (this sandbox cannot reach Gemini).
"""
from beanie import PydanticObjectId

from app.agents.eligibility import run_eligibility
from app.agents.schemas import EligibilityDecision, EligibilityResult
from app.models.opportunity import OpportunityRequirements
from app.models.user import Profile
from tests.fakes import FakeLLM


def _fail_if_llm_called(*args, **kwargs):
    raise AssertionError("LLM should NOT be called for a purely deterministic case")


async def test_hard_fail_cgpa_never_calls_llm(client, monkeypatch):
    monkeypatch.setattr("app.agents.eligibility.get_strong_llm", _fail_if_llm_called)

    requirements = OpportunityRequirements(min_cgpa=8.0)
    profile = Profile(user_id=PydanticObjectId(), cgpa=6.5, branch="CSE")

    result, execution = await run_eligibility(
        requirements, profile, str(PydanticObjectId()), str(PydanticObjectId())
    )

    assert result.decision == EligibilityDecision.NOT_ELIGIBLE
    assert result.confidence == 1.0
    assert execution.method == "deterministic"


async def test_hard_fail_branch_never_calls_llm(client, monkeypatch):
    monkeypatch.setattr("app.agents.eligibility.get_strong_llm", _fail_if_llm_called)

    requirements = OpportunityRequirements(allowed_branches=["ECE", "EEE"])
    profile = Profile(user_id=PydanticObjectId(), cgpa=9.0, branch="CSE")

    result, execution = await run_eligibility(
        requirements, profile, str(PydanticObjectId()), str(PydanticObjectId())
    )

    assert result.decision == EligibilityDecision.NOT_ELIGIBLE


async def test_missing_profile_field_is_uncertain_never_calls_llm(client, monkeypatch):
    monkeypatch.setattr("app.agents.eligibility.get_strong_llm", _fail_if_llm_called)

    requirements = OpportunityRequirements(min_cgpa=8.0)
    profile = Profile(user_id=PydanticObjectId(), cgpa=None, branch="CSE")

    result, execution = await run_eligibility(
        requirements, profile, str(PydanticObjectId()), str(PydanticObjectId())
    )

    assert result.decision == EligibilityDecision.UNCERTAIN
    assert any("CGPA" in m for m in result.missing_information)


async def test_all_criteria_met_no_qualitative_text_never_calls_llm(client, monkeypatch):
    monkeypatch.setattr("app.agents.eligibility.get_strong_llm", _fail_if_llm_called)

    requirements = OpportunityRequirements(min_cgpa=7.0, allowed_branches=["CSE"])
    profile = Profile(user_id=PydanticObjectId(), cgpa=8.5, branch="CSE")

    result, execution = await run_eligibility(
        requirements, profile, str(PydanticObjectId()), str(PydanticObjectId())
    )

    assert result.decision == EligibilityDecision.ELIGIBLE
    assert execution.method == "deterministic"


async def test_qualitative_text_triggers_llm_call(client, monkeypatch):
    canned = EligibilityResult(
        decision=EligibilityDecision.PARTIALLY_ELIGIBLE,
        reason="Profile doesn't mention leadership experience explicitly.",
        evidence=["CGPA and branch requirements met"],
        missing_information=["No mention of leadership experience in profile"],
        confidence=0.6,
    )
    monkeypatch.setattr("app.agents.eligibility.get_strong_llm", lambda: FakeLLM(canned_result=canned))

    requirements = OpportunityRequirements(
        min_cgpa=7.0,
        allowed_branches=["CSE"],
        raw_eligibility_text="Looking for candidates with leadership experience.",
    )
    profile = Profile(user_id=PydanticObjectId(), cgpa=8.5, branch="CSE")

    result, execution = await run_eligibility(
        requirements, profile, str(PydanticObjectId()), str(PydanticObjectId())
    )

    assert result.decision == EligibilityDecision.PARTIALLY_ELIGIBLE
    assert execution.method == "llm"


async def test_eligibility_llm_failure_raises_and_logs(client, monkeypatch):
    monkeypatch.setattr(
        "app.agents.eligibility.get_strong_llm", lambda: FakeLLM(raise_exc=RuntimeError("Gemini down"))
    )

    requirements = OpportunityRequirements(raw_eligibility_text="Some qualitative requirement.")
    profile = Profile(user_id=PydanticObjectId(), cgpa=8.5, branch="CSE")

    import pytest

    with pytest.raises(RuntimeError, match="Eligibility agent failed"):
        await run_eligibility(requirements, profile, str(PydanticObjectId()), str(PydanticObjectId()))
