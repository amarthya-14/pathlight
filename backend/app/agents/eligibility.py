"""
Eligibility Agent — deterministic rules FIRST, LLM only when a qualitative eligibility
statement needs interpretation the structured fields can't capture. This ordering is a
non-negotiable rule from docs/AI_DESIGN.md: never let the LLM decide something a plain
comparison can decide reliably and cheaply.
"""
import re
import time

from beanie import PydanticObjectId
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm_client import get_strong_llm
from app.agents.schemas import EligibilityDecision, EligibilityResult
from app.core.branches import branch_allowed
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
confident you feel about the wording.
- 'eligible' needs positive evidence. If the statement contains no actual eligibility \
criterion (e.g. it's an application instruction like "apply with resume", a perk, or a \
location), answer 'uncertain' and say the posting doesn't state its eligibility criteria \
— absence of a requirement is not proof the student meets the role's real bar.
- If the job title implies an experienced hire (Senior, Lead, II/III, SDE-2...) and the \
student's work experience is 0 or not stated, do not answer 'eligible'."""


# Titles that almost always mean an experienced hire. Used ONLY to stop a posting with no
# stated criteria (e.g. a LinkedIn alert digest — title/company/location only) from being
# called "Eligible"; it never makes anything NOT_ELIGIBLE on its own.
_SENIOR_TITLE = re.compile(
    r"(?i)\b(senior|sr\.?|lead|staff|principal|manager|architect|head of|director|vp)\b"
    r"|\b(II|III|IV)\b"
    r"|(?i:\b(sde|engineer|developer)[\s-]*[2-4]\b)"
)


def looks_senior(role: str | None) -> bool:
    return bool(role and _SENIOR_TITLE.search(role))


def _fmt_years(value: float) -> str:
    return f"{value:g} year{'' if value == 1 else 's'}"


def _deterministic_check(
    requirements: OpportunityRequirements, profile: Profile, role: str | None = None
) -> EligibilityResult | None:
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
        required = requirements.min_cgpa
        if profile.cgpa is None:
            missing.append("Profile CGPA is not set")
        elif required > 10:
            # "60% aggregate" extracted as 60 — a percentage, not a CGPA. Conversions vary by
            # university (x9.5 is common, x10 at most), so only clear cases decide.
            if profile.cgpa * 9.5 >= required:
                evidence.append(f"Requires {required:g}%, your CGPA {profile.cgpa} is about {profile.cgpa * 9.5:.0f}%")
            elif profile.cgpa * 10 < required:
                evidence.append(f"Requires {required:g}%, your CGPA {profile.cgpa} is at most {profile.cgpa * 10:.0f}%")
                hard_fail = True
            else:
                missing.append(f"Posting asks for {required:g}%; check your university's CGPA-to-percentage conversion")
        elif profile.cgpa < required:
            evidence.append(f"Requires CGPA >= {required}, profile has {profile.cgpa}")
            hard_fail = True
        else:
            evidence.append(f"CGPA requirement met: {profile.cgpa} >= {required}")

    if requirements.allowed_branches:
        allowed = requirements.allowed_branches
        fits = branch_allowed(profile.branch, allowed) if profile.branch and profile.branch.strip() else None
        if not (profile.branch and profile.branch.strip()):
            missing.append("Profile branch is not set")
        elif fits is False:
            evidence.append(f"Branch '{profile.branch}' not in allowed list {allowed}")
            hard_fail = True
        elif fits is None:
            missing.append(f"Couldn't tell whether '{profile.branch}' is one of the allowed branches {allowed}")
        else:
            evidence.append(f"Branch requirement met: {profile.branch} (allowed: {', '.join(allowed)})")

    if requirements.min_experience_years is not None:
        required = requirements.min_experience_years
        if required <= 0:
            evidence.append("Open to freshers — no prior experience required")
        elif profile.experience_years is None:
            missing.append(f"Posting requires {_fmt_years(required)}+ of experience; your work experience isn't set in Profile")
        elif profile.experience_years < required:
            evidence.append(
                f"Requires {_fmt_years(required)}+ of experience, you have {_fmt_years(profile.experience_years)}"
            )
            hard_fail = True
        else:
            evidence.append(f"Experience requirement met: {_fmt_years(profile.experience_years)} >= {_fmt_years(required)}")

    if hard_fail:
        return EligibilityResult(
            decision=EligibilityDecision.NOT_ELIGIBLE,
            reason="A hard eligibility criterion (CGPA, branch or experience) was not met.",
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

    # Absence of criteria is NOT a pass. Found with real LinkedIn alerts: the digest
    # email only has title/company/location, so nothing was checked and the result came
    # back "Eligible" for a role that needed 7+ years. Say what we actually know instead.
    nothing_checked = (
        requirements.min_cgpa is None
        and not requirements.allowed_branches
        and requirements.min_experience_years is None
    )
    if requirements.min_experience_years is None and looks_senior(role):
        return EligibilityResult(
            decision=EligibilityDecision.UNCERTAIN,
            reason=(
                f"The posting doesn't state its experience requirement, and the title ('{role}') "
                "usually means an experienced hire. Paste the full job description to check properly."
            ),
            evidence=evidence,
            missing_information=["Experience requirement (not in this posting/alert)"],
            confidence=0.3,
        )
    if nothing_checked:
        return EligibilityResult(
            decision=EligibilityDecision.UNCERTAIN,
            reason=(
                "This posting doesn't list any eligibility criteria (CGPA, branch or experience) — "
                "job alerts usually only include the title and company. Paste the full job "
                "description to check properly."
            ),
            evidence=[],
            missing_information=["Eligibility criteria (CGPA, branch, experience) not stated"],
            confidence=0.3,
        )

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
    role: str | None = None,
) -> tuple[EligibilityResult, AgentExecution]:
    start = time.monotonic()

    deterministic_result = _deterministic_check(requirements, profile, role)

    if deterministic_result is not None:
        # Deterministic path never touches the LLM — this is enforced by simply not
        # calling get_strong_llm() at all, not by a flag that could be bypassed.
        latency_ms = (time.monotonic() - start) * 1000
        execution = AgentExecution(
            user_id=PydanticObjectId(user_id),
            agent_name="eligibility",
            method="deterministic",
            input_summary=(
                f"role={role!r}, cgpa={profile.cgpa}, branch={profile.branch}, "
                f"experience_years={profile.experience_years}, requirements={requirements.model_dump(mode='json')}"
            ),
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
        f"Job title: {role}.\n"
        f"Student profile: CGPA={profile.cgpa}, branch={profile.branch}, "
        f"work experience={profile.experience_years if profile.experience_years is not None else 'not stated'} years.\n"
        f"Structured requirements (already verified, all met): "
        f"min_cgpa={requirements.min_cgpa}, allowed_branches={requirements.allowed_branches}, "
        f"min_experience_years={requirements.min_experience_years}.\n"
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
