"""
Integration routes — Gate 10 (docs/AUTONOMOUS_APPLICATIONS.md §5/§7). Gmail connect /
callback / disconnect via real per-user Google OAuth2, plus a manual "sync now" that runs
the same poll the background worker runs — useful for a demo, and for a user who just
connected and doesn't want to wait up to GMAIL_POLL_INTERVAL_SECONDS.

No route here ever returns a token. Responses go through IntegrationOut, which has no
token fields at all.
"""
import hmac
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.crypto import encryption_available
from app.integrations.google_oauth import (
    build_consent_url,
    exchange_code_and_store,
    get_gmail_integration,
    oauth_configured,
    revoke_and_delete,
    verify_oauth_state,
)
from app.models.integration import Integration
from app.models.user import User
from app.schemas.integration import GmailConnectOut, GmailSyncOut, GmailSyncStatus, IntegrationOut
from app.workers.autopilot import run_autopilot_once
from app.workers.gmail_poll import poll_all_once, run_manual_sync

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
internal_router = APIRouter(prefix="/api/internal", include_in_schema=False)


@internal_router.post("/gmail/poll")
async def cron_gmail_poll(x_cron_secret: str | None = Header(default=None)):
    """Gate 11: called once a day by .github/workflows/gmail-poll.yml. On a free host
    that sleeps when idle, the request itself wakes the server, then this runs the same
    poll the in-process loop would have. 404 (not 401/403) when the secret is missing or
    wrong, so the route doesn't advertise its existence."""
    if not settings.CRON_SECRET or not x_cron_secret or not hmac.compare_digest(x_cron_secret, settings.CRON_SECRET):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    results = await poll_all_once(only_due=True) if oauth_configured() else {}
    autopilot = await run_autopilot_once()
    return {
        "users_polled": len(results),
        "opportunities_ingested": sum(r.opportunities_ingested for r in results.values()),
        "autopilot_prepared": sum(autopilot.values()),
    }


def _frontend_redirect(**params: str) -> RedirectResponse:
    return RedirectResponse(
        f"{settings.FRONTEND_URL.rstrip('/')}/integrations?{urlencode(params)}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(current_user: User = Depends(get_current_user)):
    return await Integration.find(Integration.user_id == current_user.id).to_list()


@router.get("/gmail/connect", response_model=GmailConnectOut)
async def gmail_connect(current_user: User = Depends(get_current_user)):
    if not oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail integration isn't configured on this server (GMAIL_MCP_CLIENT_ID/SECRET).",
        )
    if not encryption_available():
        # Refuse rather than store tokens unencrypted — see app/core/crypto.py.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token encryption isn't configured on this server (TOKEN_ENCRYPTION_KEY).",
        )
    return GmailConnectOut(auth_url=build_consent_url(str(current_user.id)))


@router.get("/gmail/callback", include_in_schema=False)
async def gmail_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Google redirects the user's browser here — so there's no bearer token; the user is
    identified only by the signed `state` (see app/integrations/google_oauth.py). Always
    ends in a redirect back to the frontend, never a raw JSON error page."""
    if error:
        return _frontend_redirect(gmail="error", reason=error)
    user_id = verify_oauth_state(state or "")
    if user_id is None or not code:
        return _frontend_redirect(gmail="error", reason="invalid_state")
    try:
        await exchange_code_and_store(user_id, code)
    except Exception:
        return _frontend_redirect(gmail="error", reason="token_exchange_failed")
    return _frontend_redirect(gmail="connected")


@router.delete("/gmail", status_code=status.HTTP_204_NO_CONTENT)
async def gmail_disconnect(current_user: User = Depends(get_current_user)):
    if not await revoke_and_delete(str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail is not connected.")


# A sync stuck in "running" this long is assumed dead (server restarted mid-run).
STALE_SYNC = timedelta(minutes=20)


def _sync_status(integration: Integration) -> GmailSyncStatus:
    return GmailSyncStatus(
        state=integration.sync_state,
        started_at=integration.sync_started_at,
        result=GmailSyncOut(**integration.last_sync_result)
        if integration.sync_state == "done" and integration.last_sync_result
        else None,
        error=(integration.last_sync_result or {}).get("error") if integration.sync_state == "error" else None,
    )


@router.post("/gmail/sync", response_model=GmailSyncStatus, status_code=status.HTTP_202_ACCEPTED)
async def gmail_sync(background: BackgroundTasks, current_user: User = Depends(get_current_user)):
    """Starts a check of the inbox in the background and returns at once — processing
    every job in every new alert can take minutes, longer than a request should hang
    (and longer than free hosts let one). Poll GET /gmail/sync for the outcome."""
    integration = await get_gmail_integration(str(current_user.id))
    if integration is None or integration.status != "connected":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connect Gmail first.")
    started = integration.sync_started_at
    if started is not None and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if integration.sync_state == "running" and started and datetime.now(timezone.utc) - started < STALE_SYNC:
        return _sync_status(integration)
    integration.sync_state = "running"
    integration.sync_started_at = datetime.now(timezone.utc)
    integration.last_sync_result = None
    await integration.save()
    background.add_task(run_manual_sync, integration.id)
    return _sync_status(integration)


@router.get("/gmail/sync", response_model=GmailSyncStatus)
async def gmail_sync_status(current_user: User = Depends(get_current_user)):
    integration = await get_gmail_integration(str(current_user.id))
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail is not connected.")
    return _sync_status(integration)
