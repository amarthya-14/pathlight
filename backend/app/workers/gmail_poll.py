"""
Gmail job-alert poller — Gate 10 (docs/AUTONOMOUS_APPLICATIONS.md §5). The sourcing half
of "autonomous": a new *caller* of the existing run_opportunity_pipeline entry point, not
a new graph node.

Runs once a day (GMAIL_POLL_INTERVAL_SECONDS, plus a daily GitHub Actions cron that wakes
the free-tier server) and whenever the user presses "Check now". It walks every connected
Gmail Integration and, for each NEW message from a GMAIL_ALERT_SENDERS address, splits the
email into the jobs it lists (alert digests carry several) and runs each through the full
pipeline with source="gmail_mcp" — ending at READY_TO_APPLY with a tailored resume
waiting for the user's review. Nothing is ever sent from here: this module only
imports the read-side Gmail client functions (enforced by
tests/test_gmail_mcp.py::test_send_is_only_reachable_from_review_route).

Dedupe: processed message IDs are remembered per integration (capped), so overlapping
search windows never re-run the pipeline on the same email. Same posting arriving in two
different emails is then deduped one level down, by the pipeline's own company+role_hash.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.config import settings
from app.agents.discovery import run_digest_discovery
from beanie import PydanticObjectId

from app.graphs.opportunity_pipeline import latest_resume, run_opportunity_pipeline
from app.agents.llm_client import llm_for_user
from app.core.usage import try_consume
from app.models.user import Profile
from app.sources.job_matching import Student, alert_job_unfit, skills_in
from app.sources.job_signals import user_families
from app.integrations.google_oauth import GmailNotConnected, oauth_configured
from app.workers.autopilot import run_autopilot_once
from app.mcp.gmail_client import mcp_get_message, mcp_list_recent_messages
from app.models.integration import MAX_PROCESSED_MESSAGE_IDS, Integration

logger = logging.getLogger(__name__)

FIRST_POLL_LOOKBACK = "newer_than:3d"
# Overlap window on later polls — Gmail's `after:` is coarse in practice, and the
# processed-ID list makes overlap free.
REPOLL_LOOKBACK = "newer_than:2d"
MAX_MESSAGES_PER_POLL = 10


@dataclass
class PollResult:
    messages_seen: int = 0
    opportunities_ingested: int = 0
    skipped_already_processed: int = 0
    # Jobs in alerts that clearly aren't for this student (senior titles for a fresher,
    # other fields) — not ingested, so they never cost LLM quota or clutter the pipeline.
    skipped_not_relevant: int = 0
    failures: list[str] = field(default_factory=list)


def alert_senders() -> list[str]:
    return [s.strip() for s in settings.GMAIL_ALERT_SENDERS.split(",") if s.strip()]


def build_alert_query(first_poll: bool) -> str:
    senders = " OR ".join(alert_senders())
    window = FIRST_POLL_LOOKBACK if first_poll else REPOLL_LOOKBACK
    return f"from:({senders}) {window}"


async def poll_integration(integration: Integration) -> PollResult:
    """Polls one user's Gmail once, with their own Gemini key (if any) for every AI call."""
    async with llm_for_user(integration.user_id):
        return await _poll_integration(integration)


async def _poll_integration(integration: Integration) -> PollResult:
    """Polls one user's Gmail once. Per-message failures are recorded and skipped (one
    unparseable digest must not block the rest); an auth failure stops this user's poll
    and is visible as Integration.status == "error"."""
    result = PollResult()
    user_id = str(integration.user_id)
    processed = list(integration.processed_message_ids)
    processed_set = set(processed)

    try:
        messages = await mcp_list_recent_messages(
            user_id, build_alert_query(integration.last_polled_at is None), MAX_MESSAGES_PER_POLL
        )
    except Exception as e:
        result.failures.append(f"list: {e}")
        await _record_poll(integration, processed, error=str(e))
        return result

    student = await _student(user_id)

    # Oldest first, so if a later message fails the earlier ones are already recorded.
    for message_ref in reversed(messages):
        message_id = message_ref["id"]
        result.messages_seen += 1
        if message_id in processed_set:
            result.skipped_already_processed += 1
            continue
        try:
            message = await mcp_get_message(user_id, message_id)
            raw_text = f"Subject: {message['subject']}\nFrom: {message['from']}\n\n{message['body_text']}"
            try:
                jobs = await _extract_jobs(raw_text, user_id)
            except RuntimeError as e:
                # Discovery gave up (logged via AgentExecution). Still marked processed: an
                # email it can't parse now won't parse tomorrow either, and re-running it
                # every poll would just burn LLM quota.
                jobs = []
                result.failures.append(f"{message_id}: {e}")
            for job in jobs:
                if student is not None and alert_job_unfit(job.role, student):
                    result.skipped_not_relevant += 1
                    continue
                if not await try_consume(user_id, "analyse"):
                    result.failures.append(f"{message_id}: daily analysis limit reached; remaining jobs skipped")
                    break
                pipeline_result = await run_opportunity_pipeline(
                    _job_text(job, message), "gmail_mcp", user_id, extraction=job
                )
                if pipeline_result.get("needs_human_review"):
                    result.failures.append(f"{message_id}: {pipeline_result.get('error')}")
                else:
                    result.opportunities_ingested += 1
        except Exception as e:
            # Infrastructure failure (Gmail fetch, DB) — NOT marked processed, so the
            # next poll retries it while it's still inside the lookback window.
            result.failures.append(f"{message_id}: {e}")
            continue
        processed.append(message_id)
        processed_set.add(message_id)

    await _record_poll(integration, processed, error=None)
    return result


async def _student(user_id: str) -> Student | None:
    """The student's field/level for filtering alert jobs; None (= keep everything) when
    Pathlight knows nothing about them yet."""
    profile = await Profile.find_one(Profile.user_id == PydanticObjectId(user_id))
    resume = await latest_resume(user_id)
    skills = skills_in(resume.extracted_text) if resume and resume.extracted_text else []
    roles = profile.target_roles if profile else []
    if not skills and not roles:
        return None
    return Student(
        skills=skills,
        families=user_families(roles, skills),
        experience_years=profile.experience_years if profile else None,
        graduation_year=profile.graduation_year if profile else None,
    )


async def _extract_jobs(raw_text: str, user_id: str):
    last_error = None
    for _ in range(2):
        try:
            return await run_digest_discovery(raw_text, "gmail_mcp", user_id)
        except RuntimeError as e:
            last_error = e
    raise last_error


def _job_text(job, message: dict) -> str:
    """The text stored as one digest job's description. A digest gives only title,
    company and link per job — say so plainly rather than pass off the whole digest
    (other jobs included) as this job's description."""
    lines = [f"{job.role} at {job.company_name}"]
    if job.application_url:
        lines.append(f"Posting: {job.application_url}")
    if job.required_skills:
        lines.append("Skills mentioned: " + ", ".join(job.required_skills))
    lines.append(f"(From job-alert email: {message['subject']})")
    return "\n".join(lines)


async def _record_poll(integration: Integration, processed: list[str], error: str | None) -> None:
    # Re-fetch: the integration may have been refreshed (token rotation) or disconnected
    # while the pipeline was running.
    fresh = await Integration.get(integration.id)
    if fresh is None:
        return
    fresh.processed_message_ids = processed[-MAX_PROCESSED_MESSAGE_IDS:]
    fresh.last_polled_at = datetime.now(timezone.utc)
    if error is not None and fresh.status == "connected":
        fresh.last_error = error
    elif error is None:
        fresh.last_error = None
    await fresh.save()


# The in-process loop and the cron-triggered route (Gate 11) can fire at the same time;
# one poll at a time per process keeps them from processing the same email twice.
_poll_lock = asyncio.Lock()


async def poll_all_once(only_due: bool = False) -> dict[str, PollResult]:
    async with _poll_lock:
        return await _poll_all_once_unlocked(only_due)


def is_due(integration: Integration, now: datetime | None = None) -> bool:
    """Daily schedule: due when never polled, or last polled ~a day ago (an hour of
    slack so a cron that fires slightly early still runs)."""
    if integration.last_polled_at is None:
        return True
    last = integration.last_polled_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (now - last).total_seconds() >= settings.GMAIL_POLL_INTERVAL_SECONDS - 3600


async def _poll_all_once_unlocked(only_due: bool = False) -> dict[str, PollResult]:
    results: dict[str, PollResult] = {}
    integrations = await Integration.find(
        Integration.provider == "gmail", Integration.status == "connected"
    ).to_list()
    for integration in integrations:
        if only_due and not is_due(integration):
            continue
        try:
            results[str(integration.user_id)] = await poll_integration(integration)
        except GmailNotConnected as e:
            logger.info("gmail poll skipped for user %s: %s", integration.user_id, e)
        except Exception:
            logger.exception("gmail poll crashed for user %s", integration.user_id)
    return results


async def run_manual_sync(integration_id) -> None:
    """Background body of "Check now". Records running -> done/error on the Integration
    so the UI can poll for progress; never raises (it runs after the response is sent)."""
    integration = await Integration.get(integration_id)
    if integration is None:
        return
    try:
        async with _poll_lock:
            result = await poll_integration(integration)
        state, payload = "done", result.__dict__
    except Exception as e:
        logger.exception("manual gmail sync failed for %s", integration.user_id)
        state, payload = "error", {"error": str(e)}
    fresh = await Integration.get(integration_id)
    if fresh is not None:
        fresh.sync_state = state
        fresh.last_sync_result = payload
        await fresh.save()


async def run_poll_loop() -> None:
    """Forever-loop for the lifespan background task. Never lets an exception kill the
    loop — a crashed poller would silently stop sourcing for every user."""
    # Wakes hourly but polls each user only once a day (is_due). Free hosts restart the
    # process whenever they wake from idle; checking "due" instead of polling on every
    # start keeps that from turning into a poll per visit.
    while True:
        if oauth_configured():
            try:
                await poll_all_once(only_due=True)
            except Exception:
                logger.exception("gmail poll cycle failed")
        try:
            await run_autopilot_once()
        except Exception:
            logger.exception("autopilot cycle failed")
        await asyncio.sleep(min(3600, settings.GMAIL_POLL_INTERVAL_SECONDS))
