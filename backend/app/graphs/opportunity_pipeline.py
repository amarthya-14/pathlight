"""
Opportunity ingestion pipeline (LangGraph) — Discovery -> persist -> Eligibility ->
Skill Gap -> Planner.

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
from datetime import datetime, timezone
from typing import Optional, TypedDict

from beanie import PydanticObjectId
from langgraph.graph import END, StateGraph
from pymongo.errors import DuplicateKeyError

from app.agents.discovery import run_discovery
from app.agents.eligibility import run_eligibility
from app.agents.planner import DEFAULT_HOURS_PER_DAY, run_planner
from app.agents.schemas import EligibilityResult, ExtractedOpportunity, SkillGapResult
from app.agents.skill_gap import run_skill_gap
from app.core.dedupe import role_hash as compute_role_hash
from app.mcp.calendar_client import mcp_create_reminder
from app.models.application import Application, ApplicationStage, ApplicationStatusEvent
from app.models.opportunity import Company, Opportunity, OpportunityRequirements
from app.models.preparation import PreparationPlan
from app.models.user import Profile
from app.retrieval.vector_store import user_has_indexed_resume

MAX_ATTEMPTS = 2


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
    error: Optional[str]
    needs_human_review: bool


async def _discovery_node(state: PipelineState) -> PipelineState:
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
        await opportunity.save()
    else:
        opportunity = Opportunity(
            company_id=company.id,
            role=extraction.role,
            role_hash=hashed_role,
            deadline=extraction.deadline,
            source=state["source"],
            requirements=requirements,
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
                requirements, profile, state["user_id"], str(opportunity.id)
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

    available_hours = None
    if deadline_aware is not None:
        now = datetime.now(timezone.utc)
        days_remaining = max((deadline_aware - now).total_seconds() / 86400, 0)
        # First-pass estimate only, using a default hours/day assumption — a real value
        # should come from the user via the preparation-plan API and regenerate this
        # plan (see app/agents/planner.py's DEFAULT_HOURS_PER_DAY docstring).
        available_hours = round(days_remaining * DEFAULT_HOURS_PER_DAY, 1)

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
    graph.add_edge("planner", END)
    graph.add_edge("needs_human_review", END)

    return graph.compile()


_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


async def run_opportunity_pipeline(raw_text: str, source: str, user_id: str) -> PipelineState:
    pipeline = get_pipeline()
    initial_state: PipelineState = {"raw_text": raw_text, "source": source, "user_id": user_id}
    return await pipeline.ainvoke(initial_state)
