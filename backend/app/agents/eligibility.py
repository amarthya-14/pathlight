"""
Eligibility Agent — deterministic rules FIRST, LLM only when a qualitative eligibility
statement needs interpretation the structured fields can't capture. This ordering is a
non-negotiable rule from docs/AI_DESIGN.md: never let the LLM decide something a plain
comparison can decide reliably and cheaply.
"""
import time

from beanie import PydanticObjectId
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm_client import get_strong_llm
from app.agents.schemas import EligibilityDecision, EligibilityResult
from app.models.agent_execution import AgentExecution
from app.models.opportunity import OpportunityRequirements
from app.models.user import Profile

ELIGIBILITY_SYSTEM_PROMPT = """You are an eligibility-reasoning assistant for a career \
intelligence platform. You will be given a student's profile facts and a qualitative \
eligibility statement from a job posting. Decide whether the student is eligible, using \
ONLY the facts given to you.
- NEVER invent experience, certifications, skills, or achievements the profile does not \
state. If the profile doesn't mention something the posting asks about, that is missing \
information, not a basis to assume the student has it.
- If you cannot confidently decide from the given facts, choose 'uncertain' and list what \
information is missing — do not guess to avoid saying 'uncertain'.
- 'confidence' should reflect how directly the given facts support your decision, not how \
confident you feel about the wording."""


def _deterministic_check(requirements: OpportunityRequirements, profile: Profile) -> EligibilityResult | None:
    """
    Returns a definitive EligibilityResult if deterministic rules alone can decide, or
    None if qualitative text (raw_eligibility_text) still needs an LLM's judgment after
    the structured checks pass. Hard-fails (a clearly unmet numeric/branch requirement)
    always win — no LLM call needed or wanted for those.
    """
    evidence: list[str] = []
    missing: list[str] = []
    hard_fail = False

    if requirements.min_cgpa is not None:
        if profile.cgpa is None:
            missing.append("Profile CGPA is not set")
        elif profile.cgpa < requirements.min_cgpa:
            evidence.append(f"Requires CGPA >= {requirements.min_cgpa}, profile has {profile.cgpa}")
            hard_fail = True
        else:
            evidence.append(f"CGPA requirement met: {profile.cgpa} >= {requirements.min_cgpa}")

    if requirements.allowed_branches:
        allowed_lower = [b.strip().lower() for b in requirements.allowed_branches]
        if profile.branch is None:
            missing.append("Profile branch is not set")
        elif profile.branch.strip().lower() not in allowed_lower:
            evidence.append(f"Branch '{profile.branch}' not in allowed list {requirements.allowed_branches}")
            hard_fail = True
        else:
            evidence.append(f"Branch requirement met: {profile.branch}")

    if hard_fail:
        return EligibilityResult(
            decision=EligibilityDecision.NOT_ELIGIBLE,
            reason="A hard eligibility criterion (CGPA or branch) was not met.",
            evidence=evidence,
            missing_information=missing,
            confidence=1.0,
        )

    if missing:
        return EligibilityResult(
            decision=EligibilityDecision.UNCERTAIN,
            reason="Cannot determine eligibility: required profile fields are missing.",
            evidence=evidence,
            missing_information=missing,
            confidence=0.5,
        )

    # All checkable deterministic criteria passed. If there's also qualitative text
    # needing interpretation, defer to the LLM for that part rather than finalizing now.
    if requirements.raw_eligibility_text:
        return None

    return EligibilityResult(
        decision=EligibilityDecision.ELIGIBLE,
        reason="All deterministic eligibility criteria were met; no qualitative criteria to interpret.",
        evidence=evidence,
        missing_information=[],
        confidence=1.0,
    )


async def run_eligibility(
    requirements: OpportunityRequirements,
    profile: Profile,
    user_id: str,
    opportunity_id: str,
) -> tuple[EligibilityResult, AgentExecution]:
    start = time.monotonic()

    deterministic_result = _deterministic_check(requirements, profile)

    if deterministic_result is not None:
        # Deterministic path never touches the LLM — this is enforced by simply not
        # calling get_strong_llm() at all, not by a flag that could be bypassed.
        latency_ms = (time.monotonic() - start) * 1000
        execution = AgentExecution(
            user_id=PydanticObjectId(user_id),
            agent_name="eligibility",
            method="deterministic",
            input_summary=f"cgpa={profile.cgpa}, branch={profile.branch}, requirements={requirements.model_dump(mode='json')}",
            output=deterministic_result.model_dump(mode="json"),
            status="success",
            latency_ms=latency_ms,
            opportunity_id=PydanticObjectId(opportunity_id),
        )
        await execution.insert()
        return deterministic_result, execution

    # Only reached when structured checks passed but qualitative text still needs
    # interpretation — see _deterministic_check's docstring.
    llm = get_strong_llm()
    structured_llm = llm.with_structured_output(EligibilityResult)

    prompt = (
        f"Student profile: CGPA={profile.cgpa}, branch={profile.branch}.\n"
        f"Structured requirements (already verified, all met): "
        f"min_cgpa={requirements.min_cgpa}, allowed_branches={requirements.allowed_branches}.\n"
        f"Qualitative eligibility statement from the job posting that still needs "
        f"interpretation:\n{requirements.raw_eligibility_text}"
    )

    result: EligibilityResult | None = None
    status = "success"
    error_message: str | None = None

    try:
        result = await structured_llm.ainvoke(
            [
                SystemMessage(content=ELIGIBILITY_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
    except Exception as e:
        status = "error"
        error_message = str(e)

    latency_ms = (time.monotonic() - start) * 1000

    execution = AgentExecution(
        user_id=PydanticObjectId(user_id),
        agent_name="eligibility",
        method="llm",
        input_summary=prompt[:500],
        output=result.model_dump(mode="json") if result else None,
        status=status,
        error_message=error_message,
        latency_ms=latency_ms,
        opportunity_id=PydanticObjectId(opportunity_id),
    )
    await execution.insert()

    if status == "error" or result is None:
        raise RuntimeError(f"Eligibility agent failed: {error_message}")

    return result, execution
