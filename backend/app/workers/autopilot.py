"""
Autopilot — the "autonomous" half of off-campus, opt-in per student.

Once a day (IST), for every student with autopilot on: take the best NEW matches from the
job feed (posted in the last week, at or above their autopilot threshold, not already
tracked or hidden) and run each through the full pipeline, so they wake up to tailored
applications waiting for review. Capped (DAILY_LIMITS["autopilot"]) so the shared AI
quota lasts. It never applies — approval stays with the student (docs/AUTONOMOUS_APPLICATIONS.md §1).
"""
import logging

from app.core.usage import DAILY_LIMITS, today_ist, try_consume
from app.models.job_listing import JobListing
from app.models.user import Profile
from app.sources.feed import matches_for, track_listing_for, tracked_urls
from app.sources.job_matching import Filters

logger = logging.getLogger(__name__)


async def run_autopilot_for(profile: Profile) -> int:
    """Prepares up to the daily cap of new matches for one student. Returns how many."""
    user_id = str(profile.user_id)
    matches, *_ = await matches_for(user_id, Filters(min_match=profile.autopilot_min_match, days=7))
    already = await tracked_urls(user_id)
    prepared = 0
    for match in matches:
        if prepared >= DAILY_LIMITS["autopilot"]:
            break
        if match.listing.url in already:
            continue
        if not await try_consume(user_id, "autopilot") or not await try_consume(user_id, "analyse"):
            break
        listing = await JobListing.get(match.listing.id)
        if listing is None:
            continue
        await track_listing_for(listing, user_id)
        prepared += 1
    return prepared


async def run_autopilot_once() -> dict[str, int]:
    """Runs every opted-in student who hasn't had today's run. Safe to call hourly."""
    today = today_ist()
    results: dict[str, int] = {}
    async for profile in Profile.find(Profile.autopilot_enabled == True):  # noqa: E712 — Beanie query
        if profile.autopilot_last_run == today:
            continue
        # Mark first: a crash mid-run must not make the next hourly wake redo it.
        await Profile.get_motor_collection().update_one(
            {"_id": profile.id}, {"$set": {"autopilot_last_run": today}}
        )
        try:
            results[str(profile.user_id)] = await run_autopilot_for(profile)
        except Exception:
            logger.exception("autopilot failed for %s", profile.user_id)
    return results

