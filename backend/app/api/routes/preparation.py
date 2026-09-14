"""
Preparation Plan routes (Gate 6) — regenerate/fetch the Preparation Planner Agent's
output for a given Application. Regeneration takes a real user-supplied hours_per_day
(via PreparationPlanRequest) rather than relying on the pipeline's first-pass
DEFAULT_HOURS_PER_DAY guess (see app/agents/planner.py) — this is the real value path
the pipeline's auto-generated plan is explicitly meant to be replaced by.
"""
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.planner import compute_available_hours, run_planner
from app.api.deps import get_current_user
from app.models.application import Application
from app.models.opportunity import Opportunity
from app.models.preparation import PreparationPlan
from app.models.user import User
from app.schemas.preparation import PreparationPlanOut, PreparationPlanRequest

router = APIRouter(prefix="/api/applications/{application_id}/preparation-plan", tags=["preparation"])


async def _get_owned_application(application_id: str, current_user: User) -> Application:
    try:
        oid = PydanticObjectId(application_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    application = await Application.get(oid)
    # 404, not 403, if it exists but isn't owned by this user — same "don't confirm the
    # ID is valid to an attacker" reasoning as GET /api/documents/{id}.
    if application is None or application.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.post("", response_model=PreparationPlanOut, status_code=status.HTTP_200_OK)
async def regenerate_preparation_plan(
    application_id: str,
    payload: PreparationPlanRequest,
    current_user: User = Depends(get_current_user),
):
    application = await _get_owned_application(application_id, current_user)

    if application.skill_gap is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Skill Gap result yet for this application — ingest/re-run the pipeline first.",
        )
    if not (application.skill_gap.missing or application.skill_gap.weak):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No missing or weak skills to prepare for — nothing to plan.",
        )

    opportunity = await Opportunity.get(application.opportunity_id)
    deadline = opportunity.deadline if opportunity else None
    available_hours = compute_available_hours(deadline, payload.hours_per_day)

    plan, _execution = await run_planner(
        str(current_user.id),
        str(application.opportunity_id),
        str(application.id),
        application.skill_gap.missing,
        application.skill_gap.weak,
        deadline,
        available_hours,
    )

    existing = await PreparationPlan.find_one(PreparationPlan.application_id == application.id)
    if existing:
        existing.deadline = plan.deadline
        existing.available_hours = plan.available_hours
        existing.total_estimated_hours = plan.total_estimated_hours
        existing.feasible = plan.feasible
        existing.tasks = plan.tasks
        existing.generated_at = plan.generated_at
        await existing.save()
        return existing

    await plan.insert()
    return plan


@router.get("", response_model=PreparationPlanOut)
async def get_preparation_plan(application_id: str, current_user: User = Depends(get_current_user)):
    application = await _get_owned_application(application_id, current_user)

    plan = await PreparationPlan.find_one(PreparationPlan.application_id == application.id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preparation plan exists yet for this application.",
        )
    return plan
