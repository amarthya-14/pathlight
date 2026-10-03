"""
Admin — the founder's view of the product: growth, the funnel, AI health, job sources.
Only for emails listed in ADMIN_EMAILS (404 for everyone else, so the route doesn't
advertise itself). Aggregates only — no admin endpoint reads a student's resume.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.api.routes.jobs import _last_status
from app.core.config import settings
from app.core.usage import UsageCounter, today_ist
from app.models.agent_execution import AgentExecution
from app.models.application import Application
from app.models.integration import Integration
from app.models.job_listing import JobListing
from app.models.tailored_resume import TailoredResume
from app.models.user import Profile, User

router = APIRouter(prefix="/api/admin", tags=["admin"], include_in_schema=False)


def is_admin(user: User) -> bool:
    admins = {e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()}
    return user.email.lower() in admins


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return current_user


async def _group(collection, pipeline) -> dict:
    return {row["_id"]: row["n"] async for row in collection.aggregate(pipeline)}


@router.get("/stats")
async def stats(_: User = Depends(require_admin)):
    now = datetime.now(timezone.utc)
    week = now - timedelta(days=7)
    day = now - timedelta(days=1)

    active_users = await AgentExecution.get_motor_collection().distinct("user_id", {"created_at": {"$gte": week}})
    stage_counts = await _group(
        Application.get_motor_collection(),
        [{"$project": {"last": {"$arrayElemAt": ["$status_history.stage", -1]}}}, {"$group": {"_id": "$last", "n": {"$sum": 1}}}],
    )
    ever_applied = await Application.get_motor_collection().count_documents({"status_history.stage": "APPLIED"})
    ats = [
        row["avg"] async for row in TailoredResume.get_motor_collection().aggregate(
            [{"$match": {"ats.score": {"$exists": True}}}, {"$group": {"_id": None, "avg": {"$avg": "$ats.score"}}}]
        )
    ]
    agents = {}
    async for row in AgentExecution.get_motor_collection().aggregate([
        {"$match": {"created_at": {"$gte": day}}},
        {"$group": {"_id": {"agent": "$agent_name", "status": "$status"}, "n": {"$sum": 1}}},
    ]):
        agents.setdefault(row["_id"]["agent"], {})[row["_id"]["status"]] = row["n"]
    recent_errors = [
        {"agent": e.agent_name, "at": e.created_at, "error": (e.error_message or "")[:300]}
        for e in await AgentExecution.find(AgentExecution.status == "error").sort(-AgentExecution.created_at).limit(8).to_list()
    ]
    return {
        "users": {
            "total": await User.count(),
            "new_7d": await User.find(User.created_at >= week).count(),
            "active_7d": len(active_users),
            "with_resume_profile": await Profile.find(Profile.target_roles != []).count(),
            "autopilot_on": await Profile.find(Profile.autopilot_enabled == True).count(),  # noqa: E712
            "gmail_connected": await Integration.find(Integration.status == "connected").count(),
            "gmail_errors": await Integration.find(Integration.status == "error").count(),
        },
        "funnel": {
            "applications": await Application.count(),
            "tailored": await TailoredResume.count(),
            "ever_applied": ever_applied,
            "by_current_stage": stage_counts,
            "avg_ats_score": round(ats[0], 1) if ats and ats[0] is not None else None,
        },
        "ai_last_24h": agents,
        "recent_errors": recent_errors,
        "usage_today": await _group(
            UsageCounter.get_motor_collection(),
            [{"$match": {"day": today_ist()}}, {"$group": {"_id": "$kind", "n": {"$sum": "$used"}}}],
        ),
        "jobs": {
            "listings": await JobListing.count(),
            "by_source": await _group(JobListing.get_motor_collection(), [{"$group": {"_id": "$source", "n": {"$sum": 1}}}]),
            "last_refresh": _last_status,
        },
    }
