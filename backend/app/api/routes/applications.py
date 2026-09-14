"""
Application routes (Gate 8) — added because the frontend dashboard needs to list a
user's Applications with their Opportunity context and most recent Eligibility/Skill Gap
results/status history. Nothing before this gate exposed that after ingestion time
(IngestResponse only returns it once, per docs/API.md).
"""
from beanie import PydanticObjectId
from beanie.operators import In
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.application import Application
from app.models.opportunity import Company, Opportunity
from app.models.user import User
from app.retrieval.vector_store import user_has_indexed_resume
from app.schemas.application import ApplicationOut

router = APIRouter(prefix="/api/applications", tags=["applications"])


def build_application_out(application: Application, opportunity: Opportunity | None, company: Company | None) -> ApplicationOut:
    # skill_gap_note is NOT stored on Application (see docs/API.md) — recomputed here
    # from current resume-indexed state rather than left stale from ingest time, so a
    # user who uploads a resume after ingestion sees that reflected without needing to
    # re-run the whole pipeline. Non-negotiable per docs/AI_DESIGN.md: never let a
    # resume-less skill gap render as if it were real evidence.
    note = None
    return ApplicationOut(
        id=application.id,
        opportunity_id=application.opportunity_id,
        company_name=company.name if company else "Unknown",
        role=opportunity.role if opportunity else "Unknown",
        deadline=opportunity.deadline if opportunity else None,
        eligibility=application.eligibility,
        skill_gap=application.skill_gap,
        skill_gap_note=note,
        status_history=application.status_history,
        created_at=application.created_at,
    )


async def attach_skill_gap_notes(applications_out: list[ApplicationOut], user_id: PydanticObjectId) -> None:
    if not any(a.skill_gap is not None for a in applications_out):
        return
    has_resume = await user_has_indexed_resume(str(user_id))
    if has_resume:
        return
    for application_out in applications_out:
        if application_out.skill_gap is not None:
            application_out.skill_gap_note = (
                "No resume on file for this user — skill gap is not based on real evidence. "
                "Upload a resume to enable this."
            )


async def fetch_opportunities_and_companies(
    applications: list[Application],
) -> tuple[dict[PydanticObjectId, Opportunity], dict[PydanticObjectId, Company]]:
    if not applications:
        return {}, {}
    opportunity_ids = list({a.opportunity_id for a in applications})
    opportunities = {o.id: o for o in await Opportunity.find(In(Opportunity.id, opportunity_ids)).to_list()}
    company_ids = list({o.company_id for o in opportunities.values()})
    companies = {c.id: c for c in await Company.find(In(Company.id, company_ids)).to_list()}
    return opportunities, companies


@router.get("", response_model=list[ApplicationOut])
async def list_applications(current_user: User = Depends(get_current_user)):
    applications = await Application.find(Application.user_id == current_user.id).sort(-Application.created_at).to_list()
    opportunities, companies = await fetch_opportunities_and_companies(applications)

    out = [
        build_application_out(a, opportunities.get(a.opportunity_id), companies.get(opportunities[a.opportunity_id].company_id))
        if a.opportunity_id in opportunities
        else build_application_out(a, None, None)
        for a in applications
    ]
    await attach_skill_gap_notes(out, current_user.id)
    return out


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(application_id: str, current_user: User = Depends(get_current_user)):
    try:
        oid = PydanticObjectId(application_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    application = await Application.get(oid)
    if application is None or application.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    opportunity = await Opportunity.get(application.opportunity_id)
    company = await Company.get(opportunity.company_id) if opportunity else None
    out = build_application_out(application, opportunity, company)
    await attach_skill_gap_notes([out], current_user.id)
    return out
