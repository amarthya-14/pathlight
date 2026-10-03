"""
Opportunity ingestion pipeline (LangGraph) — Discovery -> persist -> Eligibility ->
Skill Gap -> Planner -> Resume Tailor.

Resume Tailor (Gate 10) is the last node and the only one that moves an Application to
READY_TO_APPLY. Applying itself is deliberately NOT a node: sending an application is
irreversible, so it only ever happens from the human review route
(POST /api/applications/{id}/review), never from inside this graph — see
docs/AUTONOMOUS_APPLICATIONS.md §1/§3.

Skill Gap was deliberately deferred out of Gate 4 (see docs/ARCHITECTURE.md §13) until
its actual dependency — Chroma + embeddings — existed, rather than shipping a
placeholder. It's added here at Gate 5 alongside that infrastructure. The Planner node
(Gate 6) is added the same way: right alongside the Preparation Planner Agent it depends
on (app/agents/planner.py), not before.

Retry policy: each AI-calling step attempts up to MAX_ATTEMPTS times (a plain loop, not
LangGraph's own retry machinery, to keep this legible) before routing to a
`needs_human_review` terminal node instead of raising. Every attempt — success or
failure — is logged via AgentExecution regardless, so a give-up is still fully
inspectable, not a silent dead end. Skill Gap and Planner do not have their own retry
loop: neither is a structured-output LLM call prone to schema-validation failures (Skill
Gap is a distance-threshold classification, Planner is pure deterministic computation),
so a single attempt is treated as reliable enough for this MVP.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, TypedDict

from beanie import PydanticObjectId
from langgraph.graph import END, StateGraph
from pymongo.errors import DuplicateKeyError

from app.agents.discovery import run_discovery
from app.agents.eligibility import run_eligibility
from app.agents.planner import DEFAULT_HOURS_PER_DAY, compute_available_hours, run_planner
from app.agents.resume_tailor import run_resume_tailor
from app.agents.schemas import EligibilityDecision, EligibilityResult, ExtractedOpportunity, SkillGapResult
from app.agents.skill_gap import run_skill_gap
from app.core.dedupe import role_hash as compute_role_hash
from app.core.resume_links import drop_dead_anchors, extract_pdf
from app.core.usage import friendly_llm_error, limit_for, try_consume
from app.mcp.sandbox import resolve_safe_path
from app.mcp.calendar_client import mcp_create_reminder
from app.models.application import REVIEW_DECIDED_STAGES, Application, ApplicationStage, ApplicationStatusEvent
from app.models.document import Document, DocumentType
from app.models.opportunity import Company, Opportunity, OpportunityRequirements
from app.models.preparation import PreparationPlan
from app.models.tailored_resume import TailoredResume
from app.models.user import Profile
from app.retrieval.vector_store import user_has_indexed_resume

MAX_ATTEMPTS = 2
MAX_DESCRIPTION_CHARS = 20000


class PipelineState(TypedDict, total=False):
    raw_text: str
    source: str
    user_id: str
    extraction: Optional[ExtractedOpportunity]
    opportunity_id: Optional[str]
    application_id: Optional[str]
    eligibility: Optional[EligibilityResult]
    skill_gap: Optional[SkillGapResult]
    skill_gap_note: Optional[str]
    preparation_plan: Optional[PreparationPlan]
    tailored_resume: Optional[TailoredResume]
    resume_tailor_note: Optional[str]
    error: Optional[str]
    needs_human_review: bool
    # Interactive callers (pasting a JD) want eligibility + skill gap back in seconds; the
    # tailor's ATS revise loop takes minutes, so they run it afterwards (tailor_in_background).
    defer_tailor: bool
    tailor_deferred: bool


async def _discovery_node(state: PipelineState) -> PipelineState:
    if state.get("extraction") is not None:
        # Already extracted by the caller (one job out of an alert digest, or a job-board
        # listing whose fields are structured already) — no second LLM call.
        return state
    last_error = None
    for _ in range(MAX_ATTEMPTS):
        try:
            extraction, _ = await run_discovery(state["raw_text"], state["source"], state["user_id"])
            state["extraction"] = extraction
            return state
        except Exception as e:
            last_error = str(e)
    state["error"] = f"Discovery failed after {MAX_ATTEMPTS} attempts: {last_error}"
    state["needs_human_review"] = True
    return state


async def _persist_opportunity_node(state: PipelineState) -> PipelineState:
    extraction: ExtractedOpportunity = state["extraction"]

    company = await Company.find_one(Company.name == extraction.company_name)
    if company is None:
        company = Company(name=extraction.company_name)
        await company.insert()

    hashed_role = compute_role_hash(extraction.role)
    requirements = OpportunityRequirements(
        min_cgpa=extraction.min_cgpa,
        allowed_branches=extraction.allowed_branches,
        required_skills=extraction.required_skills,
        preferred_skills=extraction.preferred_skills,
        compensation=extraction.compensation,
        raw_eligibility_text=extraction.raw_eligibility_text,
        min_experience_years=extraction.min_experience_years,
        apply_email=extraction.apply_email,
        application_url=extraction.application_url,
    )

    existing = await Opportunity.find_one(
        Opportunity.company_id == company.id, Opportunity.role_hash == hashed_role
    )
    if existing:
        opportunity = existing
        # Overwrite with the latest extraction. Simple for now — revisit a merge
        # strategy (e.g. prefer non-null fields from either version) if re-ingestion
        # from a second source with less complete data starts overwriting good data.
        opportunity.requirements = requirements
        if len(state["raw_text"] or "") > len(opportunity.description or ""):
            opportunity.description = state["raw_text"][:MAX_DESCRIPTION_CHARS]
        await opportunity.save()
    else:
        opportunity = Opportunity(
            company_id=company.id,
            role=extraction.role,
            role_hash=hashed_role,
            deadline=extraction.deadline,
            source=state["source"],
            requirements=requirements,
            description=(state["raw_text"] or "")[:MAX_DESCRIPTION_CHARS],
        )
        try:
            await opportunity.insert()
        except DuplicateKeyError:
            # Race with another concurrent ingestion of the same opportunity.
            opportunity = await Opportunity.find_one(
                Opportunity.company_id == company.id, Opportunity.role_hash == hashed_role
            )

    state["opportunity_id"] = str(opportunity.id)

    application = await Application.find_one(
        Application.user_id == PydanticObjectId(state["user_id"]),
        Application.opportunity_id == opportunity.id,
    )
    if application is None:
        application = Application(
            user_id=PydanticObjectId(state["user_id"]),
            opportunity_id=opportunity.id,
            status_history=[ApplicationStatusEvent(stage=ApplicationStage.DISCOVERED)],
        )
        await application.insert()

    state["application_id"] = str(application.id)
    return state


async def _eligibility_node(state: PipelineState) -> PipelineState:
    opportunity = await Opportunity.get(PydanticObjectId(state["opportunity_id"]))
    profile = await Profile.find_one(Profile.user_id == PydanticObjectId(state["user_id"]))

    if profile is None:
        # No profile yet — an expected case (no Profile-creation endpoint exists yet),
        # not a system failure. Surface as UNCERTAIN rather than crash the pipeline.
        state["eligibility"] = EligibilityResult(
            decision="uncertain",
            reason="No profile exists for this user yet, so eligibility cannot be checked.",
            evidence=[],
            missing_information=["User profile (CGPA, branch) has not been created"],
            confidence=0.0,
        )
        return state

    requirements = opportunity.requirements or OpportunityRequirements()

    last_error = None
    eligibility_result = None
    for _ in range(MAX_ATTEMPTS):
        try:
            eligibility_result, _ = await run_eligibility(
                requirements, profile, state["user_id"], str(opportunity.id), role=opportunity.role
            )
            break
        except Exception as e:
            last_error = str(e)

    if eligibility_result is None:
        state["error"] = f"Eligibility failed after {MAX_ATTEMPTS} attempts: {last_error}"
        state["needs_human_review"] = True
        return state

    state["eligibility"] = eligibility_result

    application = await Application.get(PydanticObjectId(state["application_id"]))
    application.eligibility = eligibility_result
    application.status_history.append(ApplicationStatusEvent(stage=ApplicationStage.ELIGIBILITY_CHECKED))
    await application.save()

    return state


async def _skill_gap_node(state: PipelineState) -> PipelineState:
    opportunity = await Opportunity.get(PydanticObjectId(state["opportunity_id"]))
    requirements = opportunity.requirements or OpportunityRequirements()

    all_skills = list(requirements.required_skills) + list(requirements.preferred_skills)
    if not all_skills:
        # Nothing to compare — not an error, just nothing for this agent to do.
        return state

    has_resume = await user_has_indexed_resume(state["user_id"])
    if not has_resume:
        state["skill_gap_note"] = (
            "No resume on file for this user — skill gap could not be computed "
            "against real evidence. Upload a resume to enable this."
        )

    profile = await Profile.find_one(Profile.user_id == PydanticObjectId(state["user_id"]))
    github_username = profile.github_username if profile else None

    skill_gap_result, _execution = await run_skill_gap(
        state["user_id"],
        state["opportunity_id"],
        requirements.required_skills,
        requirements.preferred_skills,
        github_username=github_username,
    )
    state["skill_gap"] = skill_gap_result

    application = await Application.get(PydanticObjectId(state["application_id"]))
    application.skill_gap = skill_gap_result
    await application.save()

    return state


async def _planner_node(state: PipelineState) -> PipelineState:
    skill_gap = state.get("skill_gap")
    if skill_gap is None or not (skill_gap.missing or skill_gap.weak):
        # Nothing to prepare for — either Skill Gap didn't run (no skills to check) or
        # everything's already matched. Not an error, just nothing for this agent to do,
        # same "no-op when there's nothing to compare" pattern as _skill_gap_node above.
        return state

    opportunity = await Opportunity.get(PydanticObjectId(state["opportunity_id"]))
    deadline = opportunity.deadline
    deadline_aware = None
    if deadline is not None:
        deadline_aware = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)

    # First-pass estimate only, using a default hours/day assumption — a real value
    # should come from the user via the preparation-plan API (app/api/routes/preparation.py)
    # and regenerate this plan (see app/agents/planner.py's DEFAULT_HOURS_PER_DAY docstring).
    available_hours = compute_available_hours(deadline, DEFAULT_HOURS_PER_DAY)

    plan, _execution = await run_planner(
        state["user_id"],
        state["opportunity_id"],
        state["application_id"],
        skill_gap.missing,
        skill_gap.weak,
        deadline,
        available_hours,
    )

    existing = await PreparationPlan.find_one(
        PreparationPlan.application_id == PydanticObjectId(state["application_id"])
    )
    if existing:
        existing.deadline = plan.deadline
        existing.available_hours = plan.available_hours
        existing.total_estimated_hours = plan.total_estimated_hours
        existing.feasible = plan.feasible
        existing.tasks = plan.tasks
        existing.generated_at = plan.generated_at
        await existing.save()
        plan = existing
    else:
        await plan.insert()

    state["preparation_plan"] = plan

    application = await Application.get(PydanticObjectId(state["application_id"]))
    application.status_history.append(ApplicationStatusEvent(stage=ApplicationStage.PREPARING))
    await application.save()

    # Best-effort deadline reminder — an MCP tool failure degrades this step, it never
    # blocks the pipeline (docs/ARCHITECTURE.md §5's failure principle). No Notification
    # model exists yet (docs/DATABASE.md lists it as still "Planned"), so there's no
    # in-app fallback to create here if this fails — just proceed without a reminder.
    if deadline_aware is not None:
        try:
            await mcp_create_reminder(
                user_id=state["user_id"],
                title=f"Application deadline: {opportunity.role}",
                description=f"Preparation plan has {len(plan.tasks)} task(s), "
                f"{plan.total_estimated_hours}h estimated.",
                event_time=deadline_aware,
                application_id=state["application_id"],
            )
        except Exception:
            pass

    return state


async def latest_resume(user_id: str) -> Document | None:
    resume = await Document.find(
        Document.owner_id == PydanticObjectId(user_id),
        Document.doc_type == DocumentType.RESUME,
        Document.extracted_text != None,  # noqa: E711 — Beanie query expression, not a Python comparison
    ).sort(-Document.created_at).first_or_none()
    if resume is not None and resume.links is None:
        await _upgrade_extraction(resume)
    return resume


async def _upgrade_extraction(resume: Document) -> None:
    """Resumes uploaded before link-aware extraction have dead anchors ("GitHub Repo")
    in their text. Re-reads the original file once so tailoring sees the real URLs —
    users don't have to re-upload. Best-effort: if the file is gone, keep the old text."""
    if resume.content_type == "application/pdf":
        raw = resume.content
        if raw is None:
            try:
                raw = resolve_safe_path(str(resume.owner_id), resume.storage_filename).read_bytes()
            except Exception:
                raw = None
        if raw:
            text, links = extract_pdf(raw)
            if text:
                resume.extracted_text = text
                resume.links = [link.as_dict() for link in links]
                await resume.save()
                return
    resume.links = []
    await resume.save()


NO_RESUME_NOTE = (
    "No resume on file — a tailored resume could not be generated. "
    "Upload a resume on your Profile to enable reviewing and applying."
)


async def tailor_application(application: Application, skill_gap: SkillGapResult | None) -> tuple[TailoredResume | None, str | None]:
    """Generates (or regenerates) the TailoredResume for one application and moves it to
    READY_TO_APPLY. Shared by the pipeline node and the on-demand route
    (POST /api/applications/{id}/tailor — e.g. after uploading a resume for postings that
    were ingested before one existed). Returns (tailored, None) on success or
    (None, reason) when it couldn't — never raises, a failure here only degrades this step."""
    if any(e.stage in REVIEW_DECIDED_STAGES for e in application.status_history):
        # The user already decided on this posting (applied/skipped). Re-ingesting the
        # same posting (e.g. it reappears in tomorrow's alert digest) must never reopen
        # review — that's how a second application email would get sent.
        return None, "You've already reviewed this application."

    user_id = str(application.user_id)
    resume = await latest_resume(user_id)
    if resume is None or not resume.extracted_text.strip():
        return None, NO_RESUME_NOTE

    if not await try_consume(user_id, "tailor"):
        return None, (
            f"You've used today's {limit_for('tailor')} tailored resumes — use “Generate tailored resume” "
            "tomorrow (the limit keeps Pathlight free for everyone)."
        )

    opportunity = await Opportunity.get(application.opportunity_id)
    company = await Company.get(opportunity.company_id)
    requirements = opportunity.requirements or OpportunityRequirements()

    base_text = resume.extracted_text
    if resume.content_type == "application/pdf" and not resume.links:
        # Original file (and its links) unavailable — don't carry dead link labels over.
        base_text = drop_dead_anchors(base_text)

    try:
        result, ats, _execution = await run_resume_tailor(
            user_id,
            str(opportunity.id),
            base_text,
            opportunity.role,
            company.name if company else "the company",
            requirements,
            skill_gap,
            job_description=opportunity.description,
        )
    except Exception as e:
        # Already logged via AgentExecution (including fabrication-guard rejections).
        return None, f"Tailored resume could not be generated: {friendly_llm_error(e)}"

    tailored = await TailoredResume.find_one(TailoredResume.application_id == application.id)
    if tailored is None:
        tailored = TailoredResume(
            application_id=application.id,
            user_id=application.user_id,
            base_document_id=resume.id,
            ats=ats.as_dict(),
            **result.model_dump(),
        )
        await tailored.insert()
    else:
        for field, value in result.model_dump().items():
            setattr(tailored, field, value)
        tailored.base_document_id = resume.id
        tailored.ats = ats.as_dict()
        tailored.generated_at = datetime.now(timezone.utc)
        await tailored.save()

    # Re-fetched: the pipeline's earlier nodes saved this document after the caller loaded it.
    application = await Application.get(application.id)
    if not application.status_history or application.status_history[-1].stage != ApplicationStage.READY_TO_APPLY:
        application.status_history.append(
            ApplicationStatusEvent(
                stage=ApplicationStage.READY_TO_APPLY,
                note="Tailored resume ready — review it before anything is sent.",
            )
        )
        await application.save()
    return tailored, None


async def _resume_tailor_node(state: PipelineState) -> PipelineState:
    eligibility = state.get("eligibility")
    if eligibility is None or eligibility.decision == EligibilityDecision.NOT_ELIGIBLE:
        # No point tailoring a resume for something the user can't apply to — and if
        # eligibility itself failed, there's no basis to say they can.
        return state

    application = await Application.get(PydanticObjectId(state["application_id"]))
    if any(e.stage in REVIEW_DECIDED_STAGES for e in application.status_history):
        return state

    if state.get("defer_tailor"):
        state["tailor_deferred"] = True
        return state

    tailored, note = await tailor_application(application, state.get("skill_gap"))
    if tailored is not None:
        state["tailored_resume"] = tailored
    else:
        state["resume_tailor_note"] = note
    return state


async def recheck_application(application: Application, job_description: str | None) -> Application:
    """Re-evaluates one existing application — after the user pastes the full job
    description (alert emails only carry title/company/location), or after they update
    their profile. With a JD: re-extracts requirements with the Discovery Agent and merges
    them into the opportunity (keeping apply email/link/deadline the JD doesn't mention).
    Then re-runs Eligibility, Skill Gap and Planner on the current data.

    Raises RuntimeError if Discovery can't read the pasted text."""
    user_id = str(application.user_id)
    opportunity = await Opportunity.get(application.opportunity_id)

    if job_description and job_description.strip():
        extraction, _ = await run_discovery(job_description, "manual_recheck", user_id)
        old = opportunity.requirements or OpportunityRequirements()
        opportunity.requirements = OpportunityRequirements(
            min_cgpa=extraction.min_cgpa,
            allowed_branches=extraction.allowed_branches,
            required_skills=extraction.required_skills or old.required_skills,
            preferred_skills=extraction.preferred_skills or old.preferred_skills,
            compensation=extraction.compensation or old.compensation,
            raw_eligibility_text=extraction.raw_eligibility_text,
            min_experience_years=extraction.min_experience_years,
            apply_email=extraction.apply_email or old.apply_email,
            application_url=extraction.application_url or old.application_url,
        )
        opportunity.description = job_description.strip()[:MAX_DESCRIPTION_CHARS]
        if extraction.deadline and opportunity.deadline is None:
            opportunity.deadline = extraction.deadline
        await opportunity.save()

    state: PipelineState = {
        "user_id": user_id,
        "opportunity_id": str(opportunity.id),
        "application_id": str(application.id),
        "source": opportunity.source,
    }
    state = await _eligibility_node(state)
    if state.get("needs_human_review"):
        raise RuntimeError(state.get("error") or "Eligibility check failed")
    state = await _skill_gap_node(state)
    await _planner_node(state)
    return await Application.get(application.id)


async def _needs_human_review_node(state: PipelineState) -> PipelineState:
    # Terminal node: the pipeline gave up after retries. Every attempt was already
    # logged via AgentExecution — this just ends the graph cleanly instead of raising,
    # so the API layer can return a normal (if unhappy) response rather than a 500.
    return state


def _route_after_discovery(state: PipelineState) -> str:
    return "needs_human_review" if state.get("needs_human_review") else "persist_opportunity"


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("discovery", _discovery_node)
    graph.add_node("persist_opportunity", _persist_opportunity_node)
    graph.add_node("eligibility", _eligibility_node)
    graph.add_node("skill_gap", _skill_gap_node)
    graph.add_node("planner", _planner_node)
    graph.add_node("resume_tailor", _resume_tailor_node)
    graph.add_node("needs_human_review", _needs_human_review_node)

    graph.set_entry_point("discovery")
    graph.add_conditional_edges(
        "discovery",
        _route_after_discovery,
        {"persist_opportunity": "persist_opportunity", "needs_human_review": "needs_human_review"},
    )
    graph.add_edge("persist_opportunity", "eligibility")
    graph.add_edge("eligibility", "skill_gap")
    graph.add_edge("skill_gap", "planner")
    graph.add_edge("planner", "resume_tailor")
    graph.add_edge("resume_tailor", END)
    graph.add_edge("needs_human_review", END)

    return graph.compile()


_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


async def tailor_in_background(application_id: str) -> None:
    """Runs the tailor for an application after the request that created it returned.
    Never raises (it runs detached); failures are logged as AgentExecutions already."""
    try:
        application = await Application.get(PydanticObjectId(application_id))
        if application is not None:
            await tailor_application(application, application.skill_gap)
    except Exception:
        logging.getLogger(__name__).exception("background tailoring failed for %s", application_id)


async def run_opportunity_pipeline(
    raw_text: str,
    source: str,
    user_id: str,
    extraction: ExtractedOpportunity | None = None,
    defer_tailor: bool = False,
) -> PipelineState:
    pipeline = get_pipeline()
    initial_state: PipelineState = {
        "raw_text": raw_text, "source": source, "user_id": user_id, "defer_tailor": defer_tailor,
    }
    if extraction is not None:
        initial_state["extraction"] = extraction
    return await pipeline.ainvoke(initial_state)
