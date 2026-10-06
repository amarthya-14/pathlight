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
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.llm_client import get_strong_llm
from app.agents.schemas import SkillGapResult, TailoredResumeResult
from app.core.ats import AtsReport, _norm, has_skill, literal_mention, score_resume
from app.core.resume_links import visible_urls
from app.models.agent_execution import AgentExecution
from app.models.opportunity import OpportunityRequirements

MAX_ATTEMPTS = 3
MAX_JD_CHARS = 6000

TAILOR_SYSTEM_PROMPT = """You are an expert technical recruiter tailoring a student's resume \
to one specific job posting so it scores as high as possible in applicant tracking systems \
(ATS) — honestly.

HARD RULES — violating any of these makes the output unusable:
- You may ONLY reword, reorder, and re-emphasize content that already exists in the \
resume. Do NOT add any skill, tool, technology, project, employer, metric, date, degree \
or achievement that is not already in the resume.
- If the posting requires a skill the resume does not show, do NOT mention that skill \
anywhere in tailored_text or skills_emphasized. Instead add a warning such as \
"Posting requires Kubernetes — not on your resume; not added."
- Keep every factual detail (names, dates, numbers, grades, URLs) exactly as written.
- Keep EVERY web address from the original (github.com/..., linkedin.com/..., portfolio \
links) exactly as written. Never shorten, invent or "fix" a URL, and never replace a URL \
with a label like "GitHub Repo" or "Link".
- Certifications: keep the certification names only. No badge/credential/verification \
links or "[View Badge]"-style labels.
- Keep ALL content: every job, project, bullet, skill category, skill and \
certification from the original must still be there (reordered and reworded is fine; \
tightening a bullet is fine; deleting one is not). The candidate decides what to cut, not you.
- skills_emphasized must only list skills that appear in the original resume, are listed \
under "SKILLS THE RESUME IMPLIES" or "SKILLS THE CANDIDATE CONFIRMED".
- No inflation: don't upgrade claims with words the resume doesn't support (e.g. \
"scalable", "robust", "production-ready", "deployed", "led", "expert", "proficient", \
"track record", "successfully") — say what was done, as the resume says it.

ATS RULES (these earn the score):
- Use standard section headings on their own line: Summary, Education, Experience, \
Projects, Technical Skills, Certifications (only those the resume has content for).
- First line: the candidate's name. Second line: contact details and links joined with \
" | " (email | phone | location | linkedin | github | portfolio — whatever the original has).
- Summary: 2-3 lines that name the target job title from the posting and lead with the \
candidate's skills that the posting asks for.
- Mirror the posting's EXACT wording for skills the resume already shows under another \
spelling (e.g. the resume says "RESTful API endpoints" and the posting says "REST APIs" \
-> write "REST APIs"). ATS matching is literal.
- Technical Skills: put the skills the posting asks for (that the resume has) first in \
each category.
- Add every skill listed under "SKILLS THE RESUME IMPLIES" and "SKILLS THE CANDIDATE \
CONFIRMED" to the Technical Skills section, in the posting's exact wording, inside the \
best-fitting existing category (or a new category line if none fits). These are honest: \
the resume already proves the implied ones (a Django project proves Python) and the \
candidate has personally confirmed knowing the others. Add them ONLY to Technical Skills \
and the Summary — never invent a project, bullet, employer or metric for them.
- Every Experience/Project bullet starts with "• " and a strong past-tense action verb \
(Built, Designed, Developed, Implemented, Improved, Optimized, Automated...). One bullet \
per line. Keep existing numbers; never invent new ones.
- Order sections and bullets so the most relevant content for THIS posting comes first.
- Plain text only: no tables, columns, icons, emojis, markdown (#, **), or "|" as a \
column separator except on the contact line.

Also write cover_note: a short (90-150 words), plain-text application email body \
addressed generically ("Dear Hiring Team,"), stating interest in the role and pointing \
to 2-3 relevant strengths that are genuinely in the resume. Same no-fabrication rules \
apply — no personality traits or practices the resume doesn't show ("quick learner", \
"clean code", "passionate"). 2-3 short paragraphs separated by blank lines. End with \
"Best regards," and the candidate's name from the resume — no other contact details.

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
        # has_skill: the base shows it under SOME spelling ("RESTful API" for "REST APIs").
        # Using the posting's wording for a skill the user has is honest, and it's what ATS
        # literal matching rewards — so it must not count as fabrication.
        if mentions_skill(base_text, skill) or has_skill(base_text, skill):
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
        if skill and not has_skill(base_text, skill)
    ]


def _build_prompt(
    base_text: str,
    role: str,
    company: str,
    requirements: OpportunityRequirements,
    skill_gap: SkillGapResult | None,
    job_description: str | None,
    confirmed_skills: list[str] | None = None,
) -> str:
    lines = [
        f"JOB: {role} at {company}",
        f"Required skills: {', '.join(requirements.required_skills) or 'not stated'}",
        f"Preferred skills: {', '.join(requirements.preferred_skills) or 'not stated'}",
    ]
    if requirements.raw_eligibility_text:
        lines.append(f"Other requirements: {requirements.raw_eligibility_text}")
    evidence = evidence_text(base_text, confirmed_skills)
    posting_skills = dict.fromkeys(s.strip() for s in requirements.required_skills + requirements.preferred_skills if s and s.strip())
    implied = [s for s in posting_skills if not has_skill(base_text, s, implied=False) and has_skill(base_text, s)]
    confirmed = [s for s in posting_skills if not has_skill(base_text, s) and has_skill(evidence, s)]
    # Confirmed skills the posting doesn't name still belong in Technical Skills.
    confirmed += [s for s in (confirmed_skills or []) if s.strip() and not any(_norm(s) == _norm(c) for c in confirmed)]
    if implied:
        lines.append(f"SKILLS THE RESUME IMPLIES (add to Technical Skills): {', '.join(implied)}")
    if confirmed:
        lines.append(f"SKILLS THE CANDIDATE CONFIRMED (add to Technical Skills): {', '.join(confirmed)}")
    if skill_gap is not None:
        lines.append(f"Skills the resume shows (from skill-gap analysis): {', '.join(skill_gap.matched) or 'none'}")
        absent = [s for s in skill_gap.missing if not has_skill(evidence, s)]
        lines.append(f"Skills the resume does NOT show — never add these: {', '.join(absent) or 'none'}")
    if job_description and job_description.strip():
        lines.append("")
        lines.append("FULL JOB DESCRIPTION (mirror its wording for skills the resume genuinely has):")
        lines.append(job_description.strip()[:MAX_JD_CHARS])
    lines.append("")
    lines.append("ORIGINAL RESUME (the only source of truth):")
    lines.append(base_text)
    return "\n".join(lines)


def evidence_text(base_text: str, confirmed_skills: list[str] | None) -> str:
    """The resume plus skills the candidate confirmed they know. Everything that decides
    what's honest (fabrication guard, ATS fixable vs blocked) reads this, not base_text."""
    skills = [s.strip() for s in confirmed_skills or [] if s and s.strip()]
    return f"{base_text}\n\nAdditional skills (confirmed by candidate): {', '.join(skills)}" if skills else base_text


def _content_kept(base_text: str, tailored_text: str) -> float:
    """Share of the original's distinct words still present — a cheap, deterministic
    detector for a tailor that "optimised" by deleting the user's content."""
    words = lambda t: {w for w in re.findall(r"[a-z0-9+#]{3,}", (t or "").lower())}
    base = words(base_text)
    return len(base & words(tailored_text)) / len(base) if base else 1.0


MIN_CONTENT_KEPT = 0.9

# Puffery an LLM likes to add. Fine if the user's own resume says it; otherwise it's a
# claim they never made.
INFLATION_WORDS = [
    "scalable", "robust", "production-ready", "production-grade", "high-performance", "enterprise-grade",
    "expert", "proficient", "track record", "spearheaded", "seamless", "cutting-edge", "world-class",
    "passionate", "quick learner", "clean code", "best practices", "mission-critical", "led", "successfully",
]
_LABEL_LINE = re.compile(r"^\s*([A-Z][A-Za-z/&()+.\- ]{1,32}):\s+\S", re.M)


def find_inflation(base_text: str, result: TailoredResumeResult) -> list[str]:
    produced = f"{result.tailored_text}\n{result.cover_note}"
    return [w for w in INFLATION_WORDS if literal_mention(produced, w) and not literal_mention(base_text, w)]


def missing_skill_lines(base_text: str, tailored_text: str) -> list[str]:
    """Skill-category labels ("AI/ML & Agentic Systems:") the tailor dropped."""
    tailored_low = tailored_text.lower()
    return [m.group(1) for m in _LABEL_LINE.finditer(base_text) if m.group(1).lower() + ":" not in tailored_low]


def _revision_feedback(
    report: AtsReport,
    dropped_urls: list[str],
    fabricated: list[str],
    kept: float = 1.0,
    inflated: list[str] | None = None,
    lost_lines: list[str] | None = None,
) -> str:
    """What the next attempt must fix — only things that can be fixed honestly."""
    notes = []
    if fabricated:
        notes.append(
            "REJECTED: your output claimed skills that are NOT on the original resume: "
            + ", ".join(fabricated) + ". Remove them completely (mention them only in warnings)."
        )
    if kept < MIN_CONTENT_KEPT:
        notes.append(
            "You deleted content from the original resume. Restore every job, project, bullet, "
            "skill category and certification — reorder and reword, but keep everything."
        )
    if lost_lines:
        notes.append("Put back these skill lines from the original, with all their skills: " + ", ".join(lost_lines))
    if inflated:
        notes.append(
            "Remove words the original resume never uses (they overstate what was done): " + ", ".join(inflated)
        )
    if dropped_urls:
        notes.append("You dropped these URLs from the original — put each back exactly: " + ", ".join(dropped_urls))
    notes.extend(report.suggestions)
    return (
        f"Your previous version scored {report.score}/100 on the ATS check. Revise it and return the "
        "complete resume again. Fix:\n- " + "\n- ".join(notes)
    )


async def run_resume_tailor(
    user_id: str,
    opportunity_id: str,
    base_text: str,
    role: str,
    company: str,
    requirements: OpportunityRequirements,
    skill_gap: SkillGapResult | None,
    job_description: str | None = None,
    confirmed_skills: list[str] | None = None,
) -> tuple[TailoredResumeResult, AtsReport, AgentExecution]:
    """Tailors the resume in a generate -> score -> revise loop:
    each attempt is checked by the fabrication guard (hard reject) and scored by the
    deterministic ATS scorer (app/core/ats.py). If points that honest rewording CAN earn
    are still missing (posting's exact wording, job title, dropped links, weak verbs),
    the next attempt gets precise feedback. Stops at the honest maximum
    (100 - points blocked by skills the user doesn't have) or after MAX_ATTEMPTS, keeping
    the best-scoring honest attempt. Logs one AgentExecution for the whole run and raises
    RuntimeError if no attempt was honest.

    `confirmed_skills` are skills the candidate told Pathlight they know but their resume
    doesn't show; they count as evidence (allowed in Technical Skills, scored as fixable)."""
    start = time.monotonic()
    structured_llm = get_strong_llm().with_structured_output(TailoredResumeResult)
    candidate_skills = list(requirements.required_skills) + list(requirements.preferred_skills)
    if skill_gap is not None:
        candidate_skills += list(skill_gap.missing) + list(skill_gap.weak)
    base_urls = visible_urls(base_text)
    evidence = evidence_text(base_text, confirmed_skills)

    messages = [
        SystemMessage(content=TAILOR_SYSTEM_PROMPT),
        HumanMessage(
            content=_build_prompt(base_text, role, company, requirements, skill_gap, job_description, confirmed_skills)
        ),
    ]

    best: tuple[TailoredResumeResult, AtsReport] | None = None
    best_effective = -1
    errors: list[str] = []
    scores: list[int] = []
    for _ in range(MAX_ATTEMPTS):
        try:
            candidate = await structured_llm.ainvoke(messages)
        except Exception as e:
            errors.append(f"llm_error: {e}")
            continue
        candidate.tailored_text = _clean_text(candidate.tailored_text)
        fabricated = find_fabricated_skills(evidence, candidate, candidate_skills)
        report = score_resume(
            candidate.tailored_text, role, requirements.required_skills, requirements.preferred_skills, evidence
        )
        tailored_urls = set(visible_urls(candidate.tailored_text))
        dropped = [u for u in base_urls if u not in tailored_urls]
        kept = _content_kept(base_text, candidate.tailored_text)
        inflated = find_inflation(base_text, candidate)
        lost_lines = missing_skill_lines(base_text, candidate.tailored_text)
        if fabricated:
            errors.append(f"fabrication_guard: output claimed skills not on the resume: {fabricated}")
        else:
            # A dropped link costs points the user can't see in the breakdown — the
            # "GitHub Repo that goes nowhere" bug. Penalise it so a version that keeps
            # every link always wins.
            honesty_issues = len(dropped) + len(inflated) + len(lost_lines) + (2 if kept < MIN_CONTENT_KEPT else 0)
            effective = report.score - 5 * honesty_issues
            scores.append(effective)
            if best is None or effective > best_effective:
                best, best_effective = (candidate, report), effective
            honest_max = 100 - report.blocked_points
            if report.score >= honest_max and honesty_issues == 0:
                break
        messages = messages[:2] + [
            AIMessage(content=candidate.tailored_text),
            HumanMessage(content=_revision_feedback(report, dropped, fabricated, kept, inflated, lost_lines)),
        ]

    result: TailoredResumeResult | None = best[0] if best else None
    ats: AtsReport | None = best[1] if best else None
    if result is not None:
        # Only add a deterministic warning if the LLM didn't already warn about that
        # skill in its own words (matched by skill name, not exact wording — a real
        # Gemini run phrased it differently and produced duplicates).
        llm_warnings = list(result.warnings)
        result.warnings = [w for w in llm_warnings if not any(
            mentions_skill(w, s) and has_skill(evidence, s) for s in candidate_skills
        )] + [
            warning
            for skill, warning in _absent_skill_warnings(evidence, requirements)
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
                "ats_score": ats.score,
                "attempt_scores": scores,
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
    return result, ats, execution


def _clean_text(text: str) -> str:
    """Strips markdown the model sometimes adds despite instructions (**bold**, # heads)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text or "")
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    return text.strip()
