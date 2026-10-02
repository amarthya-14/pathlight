"""
Gmail job-alert poller — Gate 10 (docs/AUTONOMOUS_APPLICATIONS.md §5). The sourcing half
of "autonomous": a new *caller* of the existing run_opportunity_pipeline entry point, not
a new graph node.

Runs as an in-process background task (started from app/main.py's lifespan), the same
"worker inside the same service, not a separate deployable" pattern docs/ARCHITECTURE.md
§4 describes for the outbox. Every GMAIL_POLL_INTERVAL_SECONDS it walks every connected
Gmail Integration and, for each NEW message from a GMAIL_ALERT_SENDERS address, runs the
full pipeline with source="gmail_mcp" — which ends at READY_TO_APPLY with a tailored
resume waiting for the user's review. Nothing is ever sent from here: this module only
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
from app.graphs.opportunity_pipeline import run_opportunity_pipeline
from app.integrations.google_oauth import GmailNotConnected
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
    failures: list[str] = field(default_factory=list)


def alert_senders() -> list[str]:
    return [s.strip() for s in settings.GMAIL_ALERT_SENDERS.split(",") if s.strip()]


def build_alert_query(first_poll: bool) -> str:
    senders = " OR ".join(alert_senders())
    window = FIRST_POLL_LOOKBACK if first_poll else REPOLL_LOOKBACK
    return f"from:({senders}) {window}"


async def poll_integration(integration: Integration) -> PollResult:
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
            pipeline_result = await run_opportunity_pipeline(raw_text, "gmail_mcp", user_id)
            if pipeline_result.get("needs_human_review"):
                # Discovery already retried and gave up (logged via AgentExecution). Still
                # marked processed: a digest it can't parse now won't parse in 15 minutes
                # either, and re-running it every poll would just burn LLM quota.
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


async def poll_all_once() -> dict[str, PollResult]:
    results: dict[str, PollResult] = {}
    integrations = await Integration.find(
        Integration.provider == "gmail", Integration.status == "connected"
    ).to_list()
    for integration in integrations:
        try:
            results[str(integration.user_id)] = await poll_integration(integration)
        except GmailNotConnected as e:
            logger.info("gmail poll skipped for user %s: %s", integration.user_id, e)
        except Exception:
            logger.exception("gmail poll crashed for user %s", integration.user_id)
    return results


async def run_poll_loop() -> None:
    """Forever-loop for the lifespan background task. Never lets an exception kill the
    loop — a crashed poller would silently stop sourcing for every user."""
    while True:
        try:
            await poll_all_once()
        except Exception:
            logger.exception("gmail poll cycle failed")
        await asyncio.sleep(settings.GMAIL_POLL_INTERVAL_SECONDS)
