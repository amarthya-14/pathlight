"""
Dashboard home route (Gate 8) — a server-composed aggregation (recent applications,
upcoming deadlines, a skill-gap summary) so the frontend's Home screen doesn't need to
fetch everything and aggregate client-side. Per docs/ARCHITECTURE.md §1's reasoning for
dropping GraphQL, a single REST endpoint doing this one aggregation is simpler than
either a GraphQL query or several separate frontend fetches for a screen this shape.
"""
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.routes.applications import attach_skill_gap_notes, build_application_out, fetch_opportunities_and_companies
from app.models.application import Application
from app.models.user import Profile, User
from app.retrieval.vector_store import user_has_indexed_resume
from app.schemas.dashboard import DashboardHomeOut

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

RECENT_APPLICATIONS_LIMIT = 5
URGENT_DEADLINE_WINDOW_DAYS = 14
TOP_MISSING_SKILLS_LIMIT = 5


@router.get("/home", response_model=DashboardHomeOut)
async def dashboard_home(current_user: User = Depends(get_current_user)):
    applications = (
        await Application.find(Application.user_id == current_user.id).sort(-Application.created_at).to_list()
    )
    opportunities, companies = await fetch_opportunities_and_companies(applications)

    all_out = [
        build_application_out(a, opportunities.get(a.opportunity_id), companies.get(opportunities[a.opportunity_id].company_id))
        if a.opportunity_id in opportunities
        else build_application_out(a, None, None)
        for a in applications
    ]
    await attach_skill_gap_notes(all_out, current_user.id)

    recent = all_out[:RECENT_APPLICATIONS_LIMIT]

    now = datetime.now(timezone.utc)
    urgent = []
    for application_out in all_out:
        if application_out.deadline is None:
            continue
        deadline = application_out.deadline
        deadline_aware = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
        days_until = (deadline_aware - now).total_seconds() / 86400
        if 0 <= days_until <= URGENT_DEADLINE_WINDOW_DAYS:
            urgent.append(application_out)
    urgent.sort(key=lambda a: a.deadline)

    missing_counter: Counter[str] = Counter()
    weak_counter: Counter[str] = Counter()
    for application_out in all_out:
        if application_out.skill_gap is not None:
            missing_counter.update(application_out.skill_gap.missing)
            weak_counter.update(application_out.skill_gap.weak)

    profile = await Profile.find_one(Profile.user_id == current_user.id)
    has_resume = await user_has_indexed_resume(str(current_user.id))

    return DashboardHomeOut(
        recent_applications=recent,
        urgent_deadlines=urgent,
        total_missing_skills=sum(missing_counter.values()),
        total_weak_skills=sum(weak_counter.values()),
        most_common_missing_skills=[skill for skill, _count in missing_counter.most_common(TOP_MISSING_SKILLS_LIMIT)],
        has_profile=profile is not None,
        has_resume=has_resume,
    )
