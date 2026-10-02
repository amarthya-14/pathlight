"""
Resume Tailor Agent — Gate 10 (docs/AUTONOMOUS_APPLICATIONS.md §6). Given the user's most
recent resume, an opportunity's requirements, and the Skill Gap result from the same
pipeline run, produces a tailored resume + cover note for the user to review before
anything is sent.

Uses the strong LLM (rewriting a whole resume coherently is a generation task, not an
extraction one), via structured output, through app/agents/llm_client.py like every
other agent.

The non-negotiable rule — reword, reorder, re-emphasize; NEVER fabricate — is enforced
twice:
1. In the prompt (TAILOR_SYSTEM_PROMPT).
2. In code, after the LLM returns (find_fabricated_skills): any opportunity skill that is
   absent from the base resume but present in the tailored text or in skills_emphasized
   is a fabrication. The attempt is rejected and retried; if every attempt fabricates,
   the agent fails rather than hand the user a resume claiming skills they don't have.
A prompt alone is a request; this check is the guarantee. Same "deterministic guard
around an LLM" discipline as Skill Gap's negation guard (Gate 6).
"""
import re
import time

from beanie import PydanticObjectId
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm_client import get_strong_llm
from app.agents.schemas import SkillGapResult, TailoredResumeResult
from app.models.agent_execution import AgentExecution
from app.models.opportunity import OpportunityRequirements

MAX_ATTEMPTS = 2

TAILOR_SYSTEM_PROMPT = """You tailor a student's resume to one specific job posting.

HARD RULES — violating any of these makes the output unusable:
- You may ONLY reword, reorder, and re-emphasize content that already exists in the \
resume. Do NOT add any skill, tool, technology, project, employer, metric, date, degree \
or achievement that is not already in the resume.
- If the posting requires a skill the resume does not show, do NOT mention that skill \
anywhere in tailored_text or skills_emphasized. Instead add a warning such as \
"Posting requires Kubernetes — not on your resume; not added."
- Keep every factual detail (names, dates, numbers, grades) exactly as written.
- skills_emphasized must only list skills that literally appear in the original resume.
- No inflation: don't upgrade claims with words the resume doesn't support (e.g. \
"production-ready", "deployed", "led", "expert", "successfully") — say what was done, \
as the resume says it.
- Keep the resume's line structure: section headings and each entry on their own line, \
separated by newlines exactly like the original. Never join the resume into one paragraph \
or separate sections with "|" — the user reviews your output as a line-by-line diff.

Also write cover_note: a short (90-150 words), plain-text application email body \
addressed generically ("Dear Hiring Team,"), stating interest in the role and pointing \
to 2-3 relevant strengths that are genuinely in the resume. Same no-fabrication rules \
apply. Do not include a signature block with contact details you weren't given.

changes_summary: one short line per meaningful change (e.g. "Moved Projects above \
Experience to lead with the Django backend project").
confidence: 0-1, how well the existing resume can be honestly aligned to this posting."""


def _skill_pattern(skill: str) -> re.Pattern:
    # Boundary on alphanumerics rather than \b, so skills like "C++", ".NET" and "Node.js"
    # match correctly (\b fails next to non-word characters like '+'). Very short skills
    # ("Go", "R", "C") are matched case-sensitively — otherwise every "go" and "r" in
    # ordinary prose would count as a mention and trip the fabrication guard on honest output.
    skill = skill.strip()
    flags = 0 if len(skill) <= 2 else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(skill)}(?![A-Za-z0-9])", flags)


def mentions_skill(text: str, skill: str) -> bool:
    return bool(skill.strip()) and bool(_skill_pattern(skill).search(text or ""))


def find_fabricated_skills(base_text: str, result: TailoredResumeResult, candidate_skills: list[str]) -> list[str]:
    """Returns every candidate skill the tailored output claims that the base resume
    doesn't mention. Candidates are the opportunity's required+preferred skills — the
    ones an LLM is actually tempted to slip in. Pure function, no I/O."""
    fabricated = []
    emphasized_lower = {s.strip().lower() for s in result.skills_emphasized}
    for skill in dict.fromkeys(s for s in candidate_skills if s and s.strip()):
        if mentions_skill(base_text, skill):
            continue
        in_text = mentions_skill(result.tailored_text, skill) or mentions_skill(result.cover_note, skill)
        if in_text or skill.strip().lower() in emphasized_lower:
            fabricated.append(skill)
    return fabricated


def _absent_skill_warnings(base_text: str, requirements: OpportunityRequirements) -> list[tuple[str, str]]:
    """Deterministic warnings for required skills the resume lacks — added regardless of
    whether the LLM remembered to, so the user always sees them."""
    return [
        (skill, f"Posting requires {skill} — not on your resume, so it was not added.")
        for skill in requirements.required_skills
        if skill and not mentions_skill(base_text, skill)
    ]


def _build_prompt(base_text: str, role: str, company: str, requirements: OpportunityRequirements, skill_gap: SkillGapResult | None) -> str:
    lines = [
        f"JOB: {role} at {company}",
        f"Required skills: {', '.join(requirements.required_skills) or 'not stated'}",
        f"Preferred skills: {', '.join(requirements.preferred_skills) or 'not stated'}",
    ]
    if requirements.raw_eligibility_text:
        lines.append(f"Other requirements: {requirements.raw_eligibility_text}")
    if skill_gap is not None:
        lines.append(f"Skills the resume shows (from skill-gap analysis): {', '.join(skill_gap.matched) or 'none'}")
        lines.append(f"Skills the resume does NOT show — never add these: {', '.join(skill_gap.missing) or 'none'}")
    lines.append("")
    lines.append("ORIGINAL RESUME (the only source of truth):")
    lines.append(base_text)
    return "\n".join(lines)


async def run_resume_tailor(
    user_id: str,
    opportunity_id: str,
    base_text: str,
    role: str,
    company: str,
    requirements: OpportunityRequirements,
    skill_gap: SkillGapResult | None,
) -> tuple[TailoredResumeResult, AgentExecution]:
    """Tailors the resume, retrying once on LLM failure or a fabrication-guard rejection.
    Logs one AgentExecution for the whole run (success or failure) and raises
    RuntimeError if no attempt produced an honest result."""
    start = time.monotonic()
    structured_llm = get_strong_llm().with_structured_output(TailoredResumeResult)
    candidate_skills = list(requirements.required_skills) + list(requirements.preferred_skills)
    if skill_gap is not None:
        candidate_skills += list(skill_gap.missing) + list(skill_gap.weak)

    messages = [
        SystemMessage(content=TAILOR_SYSTEM_PROMPT),
        HumanMessage(content=_build_prompt(base_text, role, company, requirements, skill_gap)),
    ]

    result: TailoredResumeResult | None = None
    errors: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        try:
            candidate = await structured_llm.ainvoke(messages)
        except Exception as e:
            errors.append(f"llm_error: {e}")
            continue
        fabricated = find_fabricated_skills(base_text, candidate, candidate_skills)
        if fabricated:
            errors.append(f"fabrication_guard: output claimed skills not on the resume: {fabricated}")
            continue
        result = candidate
        break

    if result is not None:
        # Only add a deterministic warning if the LLM didn't already warn about that
        # skill in its own words (matched by skill name, not exact wording — a real
        # Gemini run phrased it differently and produced duplicates).
        llm_warnings = list(result.warnings)
        result.warnings = llm_warnings + [
            warning
            for skill, warning in _absent_skill_warnings(base_text, requirements)
            if not any(mentions_skill(w, skill) for w in llm_warnings)
        ]
        result.confidence = max(0.0, min(1.0, result.confidence))

    execution = AgentExecution(
        user_id=PydanticObjectId(user_id),
        agent_name="resume_tailor",
        method="llm",
        input_summary=f"role={role!r}, company={company!r}, required={requirements.required_skills}",
        output=(
            {
                "changes_summary": result.changes_summary,
                "skills_emphasized": result.skills_emphasized,
                "confidence": result.confidence,
                "warnings": result.warnings,
                "rejected_attempts": errors,
            }
            if result
            else None
        ),
        status="success" if result else "error",
        error_message=None if result else "; ".join(errors),
        latency_ms=(time.monotonic() - start) * 1000,
        opportunity_id=PydanticObjectId(opportunity_id),
    )
    await execution.insert()

    if result is None:
        raise RuntimeError(f"Resume tailor failed after {MAX_ATTEMPTS} attempts: {'; '.join(errors)}")
    return result, execution
