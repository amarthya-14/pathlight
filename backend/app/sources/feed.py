"""
Shared feed logic: who the student is (field, level, skills) and which cached listings
match them. Used by the Jobs page (app/api/routes/jobs.py) and Autopilot
(app/workers/autopilot.py), so both always agree on what "a match" means.
"""
import asyncio
import logging

from beanie import PydanticObjectId
from beanie.operators import In

from app.graphs.opportunity_pipeline import latest_resume, run_opportunity_pipeline
from app.models.application import Application
from app.models.job_listing import JobListing, JobListingCard
from app.models.opportunity import Opportunity
from app.models.user import Profile
from app.sources.job_boards import search_keywords
from app.sources.job_matching import Filters, Student, rank, skills_in
from app.sources.job_signals import user_families

logger = logging.getLogger(__name__)


async def student_for(user_id) -> tuple[Student, Profile | None, bool]:
    """(student, profile, personalized) — personalized is False when Pathlight knows
    neither the student's resume skills nor their target roles."""
    uid = PydanticObjectId(str(user_id))
    profile = await Profile.find_one(Profile.user_id == uid)
    resume = await latest_resume(str(uid))
    skills = await asyncio.to_thread(skills_in, resume.extracted_text) if resume and resume.extracted_text else []
    roles = profile.target_roles if profile else []
    student = Student(
        skills=skills,
        families=user_families(roles, skills),
        experience_years=profile.experience_years if profile else None,
        graduation_year=profile.graduation_year if profile else None,
        locations=profile.preferred_locations if profile else [],
        open_to_remote=profile.open_to_remote if profile else True,
    )
    return student, profile, bool(skills or roles)


async def tracked_urls(user_id) -> dict[str, str]:
    """Posting URL -> application id, for everything the student already tracks."""
    uid = PydanticObjectId(str(user_id))
    apps = await Application.find(Application.user_id == uid).to_list()
    if not apps:
        return {}
    opps = await Opportunity.find(In(Opportunity.id, [a.opportunity_id for a in apps])).to_list()
    app_by_opp = {a.opportunity_id: str(a.id) for a in apps}
    return {
        o.requirements.application_url: app_by_opp.get(o.id)
        for o in opps
        if o.requirements and o.requirements.application_url
    }


async def matches_for(user_id, filters: Filters, query: str | None = None, limit: int = 80):
    student, profile, personalized = await student_for(user_id)
    listings = await JobListing.find_all().project(JobListingCard).to_list()
    words = search_keywords(query or "").lower().split()
    if words:
        # Every word must appear somewhere: "python bangalore" finds a Bengaluru role that
        # asks for Python even though neither word is in its title. Job-type words
        # ("intern") are left to the type filter.
        def haystack(l) -> str:
            return " ".join([l.title, l.company, l.location, " ".join(l.skills)]).lower().replace("bengaluru", "bengaluru bangalore")

        listings = [l for l in listings if all(w in haystack(l) for w in words)]
    matches, hidden, matching, by_type = rank(listings, student, filters, set(profile.dismissed_jobs) if profile else set(), limit)
    return matches, hidden, matching, by_type, student, personalized, listings


async def track_listing_for(listing: JobListing, user_id: str) -> None:
    """Runs one job-board listing through the full pipeline for a student (Discovery reads
    the posting; eligibility, skill gap, plan and the tailored resume follow)."""
    raw_text = "\n".join([
        f"{listing.title} at {listing.company}",
        f"Location: {listing.location}" + (" (remote)" if listing.remote else ""),
        f"Apply at: {listing.url}",
        "",
        listing.description,
    ])
    try:
        result = await run_opportunity_pipeline(raw_text, f"web:{listing.source}", user_id)
        if result.get("needs_human_review") or not result.get("opportunity_id"):
            return  # Discovery failure is already logged as an AgentExecution.
        opportunity = await Opportunity.get(PydanticObjectId(result["opportunity_id"]))
        # The listing's own link is authoritative for where to apply — Discovery may have
        # picked up some other URL from the description, or none at all.
        if opportunity.requirements is not None and opportunity.requirements.application_url != listing.url:
            opportunity.requirements.application_url = listing.url
            await opportunity.save()
    except Exception:
        logger.exception("tracking listing %s failed", listing.id)
