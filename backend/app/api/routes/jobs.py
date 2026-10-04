"""
Jobs feed — opportunities from public job boards (app/sources/job_boards.py), ranked for
the current user (app/sources/job_matching.py).

Listings are cached globally in Mongo and refreshed when older than REFRESH_AFTER: the
first feed request after that refreshes in the background and serves the cached rows
meanwhile, so nobody waits on 25 job boards. Tracking a listing runs it through the same
pipeline as a pasted job description (eligibility -> skill gap -> plan -> tailored
resume), so it lands in Applications like any other opportunity.

POST /search runs one student's search live on the keyword-searchable sources and adds
what it finds to the same cache, so the feed (and everyone else's) grows with it.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from beanie import PydanticObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.usage import consume_or_429
from app.models.job_listing import JobListing
from app.models.user import Profile, User
from app.sources.job_boards import fetch_all, search_web
from app.sources.job_signals import JOB_TYPES
from app.sources.feed import matches_for, track_listing_for, tracked_urls
from app.sources.job_matching import Filters, listing_skills, listing_type
from app.sources.job_signals import signals

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])

REFRESH_AFTER = timedelta(hours=12)
# Listings not seen in a refresh for this long are closed postings — dropped.
EXPIRE_AFTER = timedelta(days=4)

# A web search costs ~6 outbound requests: one per user every few seconds, and the same
# search within half an hour is answered from the cache it already filled.
SEARCH_COOLDOWN = 8.0
SEARCH_CACHE_FOR = 30 * 60
_last_search: dict[str, float] = {}
_recent_searches: dict[tuple[str, str], float] = {}

_refresh_lock = asyncio.Lock()
_last_status: dict[str, str] = {}


class JobFeedItem(BaseModel):
    id: str
    title: str
    company: str
    location: str
    remote: bool
    url: str
    source: str
    posted_at: datetime | None
    match: int
    matched_skills: list[str]
    missing_skills: list[str]
    reasons: list[str] = []
    min_experience: float | None = None
    entry_level: bool = False
    job_type: str = "full_time"
    tracked_application_id: str | None = None


class JobFeedOut(BaseModel):
    items: list[JobFeedItem]
    total_listings: int
    matching: int  # passed every filter (items is the top of these)
    hidden: dict[str, int]  # reason -> count, see job_matching.HIDDEN_REASONS
    refreshed_at: datetime | None
    refreshing: bool
    personalized: bool
    families: list[str]
    sources: int
    job_types: dict[str, int]  # matches per type, before the job-type filter


async def _store(listings: list[dict], now: datetime) -> int:
    """Upserts fetched listings; returns how many were new to the cache."""
    collection = JobListing.get_motor_collection()
    # CPU-bound (hundreds of listings x the skill vocabulary) — in a worker thread so
    # the event loop keeps serving requests meanwhile.
    await asyncio.to_thread(_attach_skills, listings)

    async def upsert(listing: dict) -> bool:
        result = await collection.update_one(
            {"source": listing["source"], "external_id": listing["external_id"]},
            {"$set": {**listing, "fetched_at": now}},
            upsert=True,
        )
        return result.upserted_id is not None

    new = 0
    # Chunked so a few hundred listings don't open a few hundred connections at once.
    for i in range(0, len(listings), 50):
        new += sum(await asyncio.gather(*(upsert(l) for l in listings[i:i + 50])))
    return new


async def refresh_listings() -> int:
    """Fetches every board and upserts. Serialized: two concurrent refreshes would just
    double the outbound traffic for the same rows."""
    async with _refresh_lock:
        listings, source_status = await fetch_all(await _popular_target_roles())
        _last_status.clear()
        _last_status.update(source_status)
        now = datetime.now(timezone.utc)
        if listings:
            await _store(listings, now)
            collection = JobListing.get_motor_collection()
            await collection.delete_many({"fetched_at": {"$lt": now - EXPIRE_AFTER}})
            # Rows this refresh didn't see (closed postings awaiting expiry) still need the
            # field, or the "missing skills" check below would refresh on every request.
            await collection.update_many({"family": {"$exists": False}}, {"$set": {"skills": [], "family": "other"}})
        logger.info("job listings refreshed: %d relevant", len(listings))
        return len(listings)


def _attach_skills(listings: list[dict]) -> None:
    for listing in listings:
        listing["skills"] = listing_skills(listing["title"], listing["description"])
        listing.update(signals(listing["title"], listing["description"], listing.pop("employment", "")))


async def _popular_target_roles(limit: int = 6) -> list[str]:
    """What students on this server are looking for — searched on the aggregators."""
    counts: dict[str, int] = {}
    async for profile in Profile.find(Profile.target_roles != []):
        for role in profile.target_roles:
            counts[role.strip()] = counts.get(role.strip(), 0) + 1
    return [r for r, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:limit]


async def _refresh_quietly() -> None:
    try:
        await refresh_listings()
    except Exception:
        logger.exception("job listing refresh failed")


async def _newest_fetch() -> datetime | None:
    newest = await JobListing.find_all().sort(-JobListing.fetched_at).first_or_none()
    if newest is None:
        return None
    ts = newest.fetched_at
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


@router.get("/feed", response_model=JobFeedOut)
async def job_feed(
    q: str | None = Query(default=None, max_length=80),
    min_match: int = Query(default=60, ge=0, le=100),
    days: int = Query(default=30, ge=0, le=365),  # 0 = any age
    include_experienced: bool = False,
    job_type: str | None = Query(default=None, pattern="^(internship|full_time|part_time|contract)$"),
    current_user: User = Depends(get_current_user),
):
    newest = await _newest_fetch()
    refreshing = _refresh_lock.locked()
    if newest is None:
        # Nothing cached yet (first user ever, or after expiry) — this one request waits.
        await _refresh_quietly()
        newest = await _newest_fetch()
    elif not refreshing and (
        datetime.now(timezone.utc) - newest > REFRESH_AFTER
        # Cached before skills/signals were precomputed — refresh once to fill them in.
        or await JobListing.find_one({"family": {"$exists": False}}) is not None
    ):
        asyncio.create_task(_refresh_quietly())
        refreshing = True

    matches, hidden, matching, by_type, student, personalized, listings = await matches_for(
        current_user.id,
        Filters(min_match=min_match, days=days, include_experienced=include_experienced, job_type=job_type),
        q,
    )
    tracked = await tracked_urls(current_user.id)

    return JobFeedOut(
        items=[
            JobFeedItem(
                id=str(m.listing.id),
                title=m.listing.title,
                company=m.listing.company,
                location=m.listing.location,
                remote=m.listing.remote,
                url=m.listing.url,
                source=m.listing.source,
                posted_at=m.listing.posted_at,
                match=m.score,
                matched_skills=m.matched[:8],
                missing_skills=m.missing[:6],
                reasons=m.reasons,
                min_experience=m.listing.min_experience,
                entry_level=m.listing.entry_level,
                job_type=listing_type(m.listing),
                tracked_application_id=tracked.get(m.listing.url),
            )
            for m in matches
        ],
        total_listings=await JobListing.count(),
        matching=matching,
        hidden=hidden,
        refreshed_at=newest,
        refreshing=refreshing,
        personalized=personalized,
        families=sorted(student.families),
        sources=len({l.source + l.company for l in listings}),
        job_types={t: by_type.get(t, 0) for t in JOB_TYPES},
    )


class WebSearchIn(BaseModel):
    q: str = Field(default="", max_length=80)
    job_type: str | None = Field(default=None, pattern="^(internship|full_time|part_time|contract)$")


class WebSearchOut(BaseModel):
    found: int  # relevant listings the sources returned
    new: int  # of those, not already in the feed
    new_ids: list[str]
    sources: dict[str, str]
    cached: bool = False


@router.post("/search", response_model=WebSearchOut)
async def web_search(body: WebSearchIn, current_user: User = Depends(get_current_user)):
    """Searches the job sites live for this query/type and adds the results to the feed
    cache. The client then reloads the feed, which ranks them like any other listing."""
    user_key = str(current_user.id)
    now_mono = time.monotonic()
    if now_mono - _last_search.get(user_key, 0) < SEARCH_COOLDOWN:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="One web search at a time — try again in a few seconds.")
    key = (body.q.strip().lower(), body.job_type or "")
    if now_mono - _recent_searches.get(key, -SEARCH_CACHE_FOR) < SEARCH_CACHE_FOR:
        return WebSearchOut(found=0, new=0, new_ids=[], sources={}, cached=True)
    _last_search[user_key] = now_mono

    listings, source_status = await search_web(body.q, body.job_type)
    _recent_searches[key] = now_mono
    if len(_recent_searches) > 500:
        for k, _ in sorted(_recent_searches.items(), key=lambda kv: kv[1])[:250]:
            _recent_searches.pop(k, None)
    new = 0
    new_ids: list[str] = []
    if listings:
        now = datetime.now(timezone.utc)
        before = {(l["source"], l["external_id"]) for l in listings}
        existing = {
            (d["source"], d["external_id"])
            async for d in JobListing.get_motor_collection().find(
                {"$or": [{"source": s, "external_id": e} for s, e in before]}, {"source": 1, "external_id": 1}
            )
        }
        new = await _store(listings, now)
        fresh = [l for l in listings if (l["source"], l["external_id"]) not in existing]
        if fresh:
            async for d in JobListing.get_motor_collection().find(
                {"$or": [{"source": l["source"], "external_id": l["external_id"]} for l in fresh]}, {"_id": 1}
            ):
                new_ids.append(str(d["_id"]))
    logger.info("web search %r (%s): %d found, %d new", body.q, body.job_type, len(listings), new)
    return WebSearchOut(found=len(listings), new=new, new_ids=new_ids, sources=source_status)


@router.post("/{listing_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_listing(listing_id: str, current_user: User = Depends(get_current_user)):
    """'Not for me' — hides a listing from this student's feed for good."""
    try:
        listing = await JobListing.get(PydanticObjectId(listing_id))
    except Exception:
        listing = None
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This job is no longer listed.")
    profile = await Profile.find_one(Profile.user_id == current_user.id)
    if profile is None:
        profile = Profile(user_id=current_user.id)
        await profile.insert()
    key = f"{listing.source}:{listing.external_id}"
    if key not in profile.dismissed_jobs:
        profile.dismissed_jobs = (profile.dismissed_jobs + [key])[-500:]
        await profile.save()


class TrackOut(BaseModel):
    status: str  # "processing" | "already_tracked"
    application_id: str | None = None


@router.post("/{listing_id}/track", response_model=TrackOut, status_code=status.HTTP_202_ACCEPTED)
async def track_listing(listing_id: str, background: BackgroundTasks, current_user: User = Depends(get_current_user)):
    """Adds a job-board listing to the user's pipeline. Returns at once; Discovery,
    eligibility, skill gap, prep plan and the tailored resume (an ATS revise loop —
    minutes, not seconds) run in the background and land in Applications."""
    try:
        listing = await JobListing.get(PydanticObjectId(listing_id))
    except Exception:
        listing = None
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This job is no longer listed.")
    await consume_or_429(current_user.id, "analyse")
    background.add_task(track_listing_for, listing, str(current_user.id))
    return TrackOut(status="processing")


@router.get("/sources")
async def job_sources(current_user: User = Depends(get_current_user)):
    """Per-board status of the last refresh — for checking which boards are live."""
    return {"sources": _last_status, "refreshed_at": await _newest_fetch()}
