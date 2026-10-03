"""
Per-user daily limits on AI-heavy actions, and plain-language LLM errors.

Pathlight runs on one shared Gemini key. Without limits, one enthusiastic user tracking
fifty jobs in an hour would exhaust the free quota for everyone (the strong model allows
~20 requests a day per project — docs/DEPLOYMENT.md). Limits are counted per user per
IST day in MongoDB (works across processes and restarts).

Background work started by the system (Gmail alerts, autopilot) uses `try_consume`,
which never raises — it just skips when the budget is spent.
"""
from datetime import datetime, timedelta, timezone

from beanie import Document, PydanticObjectId
from fastapi import HTTPException, status
from pydantic import Field
from pymongo import ASCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

IST = timezone(timedelta(hours=5, minutes=30))

# Actions per user per day. "analyse" = a pasted JD / tracked job (Discovery + eligibility);
# "tailor" = one tailored resume (up to 3 strong-model calls in the ATS loop).
DAILY_LIMITS = {"analyse": 25, "tailor": 12, "autopilot": 3}


class UsageCounter(Document):
    user_id: PydanticObjectId
    day: str  # YYYY-MM-DD in IST — students think in IST days, not UTC
    kind: str
    used: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "usage_counters"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("day", ASCENDING), ("kind", ASCENDING)], unique=True, name="uq_usage"),
        ]


def today_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


async def used_today(user_id, kind: str) -> int:
    row = await UsageCounter.find_one(
        UsageCounter.user_id == PydanticObjectId(str(user_id)), UsageCounter.day == today_ist(), UsageCounter.kind == kind
    )
    return row.used if row else 0


# Students who added their own Gemini key spend their own quota, so they get more.
OWN_KEY_MULTIPLIER = 4


def limit_for(kind: str) -> int:
    from app.agents.llm_client import using_own_key  # local: llm_client imports nothing from here

    return DAILY_LIMITS[kind] * (OWN_KEY_MULTIPLIER if using_own_key() and kind != "autopilot" else 1)


async def try_consume(user_id, kind: str) -> bool:
    """Atomically takes one unit of today's budget. False if the budget is spent."""
    limit = limit_for(kind)
    uid = PydanticObjectId(str(user_id))
    day = today_ist()
    collection = UsageCounter.get_motor_collection()
    try:
        await collection.update_one(
            {"user_id": uid, "day": day, "kind": kind},
            {"$setOnInsert": {"used": 0, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
    except DuplicateKeyError:
        pass  # a concurrent request created it
    updated = await collection.find_one_and_update(
        {"user_id": uid, "day": day, "kind": kind, "used": {"$lt": limit}},
        {"$inc": {"used": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    return updated is not None


async def consume_or_429(user_id, kind: str) -> None:
    if not await try_consume(user_id, kind):
        what = {"analyse": "jobs analysed", "tailor": "tailored resumes", "autopilot": "autopilot runs"}[kind]
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You've reached today's limit of {limit_for(kind)} {what}. It resets at midnight IST. "
            + (
                "Add your own free AI key (e.g. Gemini) in Profile → Your AI keys to get "
                f"{OWN_KEY_MULTIPLIER}x the daily limit."
                if limit_for(kind) == DAILY_LIMITS[kind] and kind != "autopilot"
                else "This keeps Pathlight free for every student."
            ),
        )


def friendly_llm_error(error: Exception | str) -> str:
    """Turns provider errors into something a student can act on."""
    text = str(error)
    low = text.lower()
    if "resource_exhausted" in low or "429" in low or "quota" in low:
        return (
            "Pathlight's AI has hit its daily limit (shared free quota). Try again in a few hours — or add your "
            "own free AI key in Profile → Your AI keys so you never wait on the shared quota."
        )
    if "unavailable" in low or "503" in low or "overloaded" in low:
        return "The AI service is busy right now. Please try again in a minute."
    if "fabrication_guard" in low:
        return "The AI kept adding skills that aren't on your resume, so Pathlight rejected its output. Try again."
    if "deadline" in low or "timeout" in low:
        return "The AI took too long to respond. Please try again."
    return text if len(text) < 200 else "Something went wrong while generating — please try again."
