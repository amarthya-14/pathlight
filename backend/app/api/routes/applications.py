"""
Application routes (Gate 8) — added because the frontend dashboard needs to list a
user's Applications with their Opportunity context and most recent Eligibility/Skill Gap
results/status history. Nothing before this gate exposed that after ingestion time
(IngestResponse only returns it once, per docs/API.md).

Gate 10 adds the human review gate (docs/AUTONOMOUS_APPLICATIONS.md §7):
GET /{id}/tailored-resume and POST /{id}/review. The review route is the ONLY code path
in this project that can send an email on the user's behalf.
"""
import re
from datetime import datetime, timezone

from beanie import PydanticObjectId
from beanie.operators import In
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.integrations.google_oauth import get_gmail_integration
from app.mcp.gmail_client import mcp_send_application_email
from app.models.application import Application, ApplicationStage, ApplicationStatusEvent
from app.models.document import Document
from app.models.opportunity import Company, Opportunity
from app.models.tailored_resume import TailoredResume
from app.models.user import User
from app.retrieval.vector_store import user_has_indexed_resume
from app.schemas.application import ApplicationOut, ReviewRequest, ReviewResponse, TailoredResumeOut

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"

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
        source=opportunity.source if opportunity else None,
        apply_email=opportunity.requirements.apply_email if opportunity and opportunity.requirements else None,
        application_url=(
            opportunity.requirements.application_url if opportunity and opportunity.requirements else None
        ),
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


async def _get_owned_application(application_id: str, current_user: User) -> Application:
    try:
        oid = PydanticObjectId(application_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    application = await Application.get(oid)
    # 404, not 403, for someone else's application — don't confirm the ID exists.
    if application is None or application.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


async def _application_out(application: Application, current_user: User) -> ApplicationOut:
    opportunity = await Opportunity.get(application.opportunity_id)
    company = await Company.get(opportunity.company_id) if opportunity else None
    out = build_application_out(application, opportunity, company)
    await attach_skill_gap_notes([out], current_user.id)
    return out


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(application_id: str, current_user: User = Depends(get_current_user)):
    application = await _get_owned_application(application_id, current_user)
    return await _application_out(application, current_user)


@router.get("/{application_id}/tailored-resume", response_model=TailoredResumeOut)
async def get_tailored_resume(application_id: str, current_user: User = Depends(get_current_user)):
    application = await _get_owned_application(application_id, current_user)
    tailored = await TailoredResume.find_one(TailoredResume.application_id == application.id)
    if tailored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tailored resume exists yet for this application.",
        )
    base = await Document.get(tailored.base_document_id)
    return TailoredResumeOut(
        **tailored.model_dump(exclude={"id", "user_id", "revision_id"}),
        base_resume_text=base.extracted_text if base and base.owner_id == current_user.id else None,
    )


async def _claim_review(application_id: PydanticObjectId) -> bool:
    """Atomically marks the application as reviewed. Exactly one concurrent request can
    win this (a single find_one_and_update conditioned on reviewed_at being unset) — so
    a double-clicked Approve, or two open tabs, can never send two emails."""
    claimed = await Application.get_motor_collection().find_one_and_update(
        {"_id": application_id, "reviewed_at": None},
        {"$set": {"reviewed_at": datetime.now(timezone.utc)}},
    )
    return claimed is not None


async def _release_review(application_id: PydanticObjectId) -> None:
    await Application.get_motor_collection().update_one(
        {"_id": application_id}, {"$set": {"reviewed_at": None}}
    )


async def _record_outcome(application_id: PydanticObjectId, stage: ApplicationStage, note: str) -> Application:
    # Re-fetched after the claim: the in-memory copy from before the claim doesn't have
    # reviewed_at set, and save()-ing it would silently un-claim the review.
    application = await Application.get(application_id)
    application.status_history.append(ApplicationStatusEvent(stage=stage, note=note))
    await application.save()
    return application


def _attachment_filename(user: User, role: str) -> str:
    base = (user.full_name or user.email.split("@")[0]).strip()
    safe = re.sub(r"[^A-Za-z0-9]+", "_", f"{base} Resume {role}").strip("_")
    return f"{safe[:80] or 'Resume'}.txt"


@router.post("/{application_id}/review", response_model=ReviewResponse)
async def review_application(
    application_id: str, payload: ReviewRequest, current_user: User = Depends(get_current_user)
):
    """The human approval gate. approve=false records SKIPPED_BY_USER and never touches
    Gmail. approve=true sends the tailored resume + cover note to the posting's
    apply_email via Gmail MCP (APPLIED), or — if the posting gave no email — records
    MANUAL_APPLY_REQUIRED and returns the posting link instead. Never silently fails."""
    application = await _get_owned_application(application_id, current_user)

    if not application.status_history or application.status_history[-1].stage != ApplicationStage.READY_TO_APPLY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This application isn't awaiting review (it must be READY_TO_APPLY).",
        )
    tailored = await TailoredResume.find_one(TailoredResume.application_id == application.id)
    if tailored is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No tailored resume to review yet.")

    opportunity = await Opportunity.get(application.opportunity_id)
    requirements = opportunity.requirements if opportunity else None
    apply_email = requirements.apply_email if requirements else None
    application_url = requirements.application_url if requirements else None

    # Pre-flight BEFORE claiming, so "connect Gmail first" leaves the application exactly
    # as it was — the user connects and clicks Approve again.
    if payload.approve and apply_email:
        integration = await get_gmail_integration(str(current_user.id))
        if integration is None or integration.status != "connected" or GMAIL_SEND_SCOPE not in integration.scopes:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Connect Gmail (with send permission) on the Integrations page before approving.",
            )

    if not await _claim_review(application.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This application was already reviewed.")

    if not payload.approve:
        application = await _record_outcome(
            application.id, ApplicationStage.SKIPPED_BY_USER, "Reviewed the tailored resume and chose not to apply."
        )
        return ReviewResponse(
            outcome="skipped",
            detail="Skipped — nothing was sent.",
            application=await _application_out(application, current_user),
        )

    if not apply_email:
        note = (
            f"No application email in the posting — apply at {application_url}"
            if application_url
            else "No application email or link in the posting — apply through the original source."
        )
        application = await _record_outcome(application.id, ApplicationStage.MANUAL_APPLY_REQUIRED, note)
        return ReviewResponse(
            outcome="manual_apply_required",
            detail=note,
            application_url=application_url,
            application=await _application_out(application, current_user),
        )

    company = await Company.get(opportunity.company_id)
    try:
        sent = await mcp_send_application_email(
            user_id=str(current_user.id),
            to=apply_email,
            subject=f"Application for {opportunity.role}" + (f" at {company.name}" if company else ""),
            body_text=tailored.cover_note,
            attachment_filename=_attachment_filename(current_user, opportunity.role),
            attachment_text=tailored.tailored_text,
        )
    except Exception as e:
        # Un-claim so the user can retry; the application stays READY_TO_APPLY. Not
        # auto-retried — see app/mcp/gmail_client.py for why a send is never retried.
        await _release_review(application.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gmail send failed — nothing was recorded as applied. You can try again. ({e})",
        )

    application = await _record_outcome(
        application.id,
        ApplicationStage.APPLIED,
        f"Sent tailored resume to {apply_email} via Gmail (message {sent.get('id')}).",
    )
    return ReviewResponse(
        outcome="applied",
        detail=f"Application sent to {apply_email}.",
        sent_to=apply_email,
        application_url=application_url,
        application=await _application_out(application, current_user),
    )
