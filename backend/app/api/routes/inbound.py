"""
Forwarded job alerts (see app/models/inbound.py).

- POST /api/inbound/email          : called by the inbound-email service with the raw
                                     message. Guarded by INBOUND_WEBHOOK_SECRET; answers
                                     fast and processes in the background.
- GET  /api/inbound/address        : the student's forwarding address + recent activity
                                     (including Gmail's confirmation code during setup).
- POST /api/inbound/address/rotate : a fresh address, if the old one gets spammed.
"""
import hmac
import logging
import secrets

from beanie import PydanticObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from app.agents.llm_client import llm_for_user
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.inbound_mail import gmail_confirmation, is_gmail_confirmation, is_job_alert, parse_mime, token_for
from app.models.inbound import AlertAddress, InboundEmail
from app.models.user import User
from app.workers.gmail_poll import PollResult, _student, alert_senders, ingest_alert_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inbound", tags=["inbound"])

MAX_EMAIL_BYTES = 3 * 1024 * 1024
TOKEN_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o/1/l/i — read aloud safely
FORWARD_SOURCE = "email_forward"


def inbound_enabled() -> bool:
    return bool(settings.INBOUND_EMAIL_DOMAIN and settings.INBOUND_WEBHOOK_SECRET)


def _new_token() -> str:
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(10))


async def address_for(user_id) -> AlertAddress:
    existing = await AlertAddress.find_one(AlertAddress.user_id == PydanticObjectId(str(user_id)))
    if existing:
        return existing
    address = AlertAddress(user_id=PydanticObjectId(str(user_id)), token=_new_token())
    await address.insert()
    return address


# ── Inbound webhook ──────────────────────────────────────────────────────────────────

@router.post("/email", status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
async def receive_email(
    request: Request,
    background: BackgroundTasks,
    x_inbound_secret: str | None = Header(default=None),
    x_pathlight_to: str | None = Header(default=None),
):
    # 404 rather than 401 on a bad secret, so the route doesn't advertise itself.
    if not inbound_enabled() or not x_inbound_secret or not hmac.compare_digest(
        x_inbound_secret, settings.INBOUND_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    raw = await request.body()
    if len(raw) > MAX_EMAIL_BYTES:
        return {"status": "ignored", "reason": "too large"}

    mail = parse_mime(raw, envelope_to=x_pathlight_to)
    token = token_for(mail.recipients, settings.INBOUND_EMAIL_DOMAIN)
    address = await AlertAddress.find_one(AlertAddress.token == token) if token else None
    if address is None:
        return {"status": "ignored", "reason": "unknown address"}  # never reveal which exist

    user_id = address.user_id
    if await InboundEmail.find_one(InboundEmail.user_id == user_id, InboundEmail.message_hash == mail.fingerprint):
        return {"status": "duplicate"}

    if is_gmail_confirmation(mail):
        code, link = gmail_confirmation(mail)
        await InboundEmail(
            user_id=user_id, kind="gmail_confirmation", status="done", sender=mail.sender,
            subject=mail.subject[:200], message_hash=mail.fingerprint, confirmation_code=code, confirmation_link=link,
        ).insert()
        return {"status": "confirmation"}

    if not (is_job_alert(mail) or mail.sender in alert_senders()):
        # Not a job alert (a mis-set filter, or spam): don't keep its subject or body.
        await InboundEmail(user_id=user_id, kind="ignored", status="ignored", message_hash=mail.fingerprint).insert()
        return {"status": "ignored", "reason": "not a job-alert sender"}

    record = InboundEmail(
        user_id=user_id, kind="job_alert", status="processing", sender=mail.sender,
        subject=mail.subject[:200], message_hash=mail.fingerprint,
    )
    await record.insert()
    background.add_task(_process_alert, record.id, str(user_id), mail.sender, mail.subject, mail.text)
    return {"status": "accepted"}


async def _process_alert(record_id, user_id: str, sender: str, subject: str, text: str) -> None:
    result = PollResult(messages_seen=1)
    error = None
    try:
        async with llm_for_user(user_id):
            await ingest_alert_email(user_id, subject, sender, text, FORWARD_SOURCE, await _student(user_id), result, subject[:60])
    except Exception as e:
        logger.exception("forwarded alert failed for %s", user_id)
        error = str(e)[:300]
    record = await InboundEmail.get(record_id)
    if record is not None:
        record.status = "failed" if error else "done"
        record.jobs_ingested = result.opportunities_ingested
        record.skipped_not_relevant = result.skipped_not_relevant
        record.error = error or ("; ".join(result.failures)[:300] if result.failures and not result.opportunities_ingested else None)
        await record.save()


# ── Student-facing ───────────────────────────────────────────────────────────────────

class InboundActivity(BaseModel):
    kind: str
    status: str
    subject: str | None
    jobs_ingested: int
    skipped_not_relevant: int
    error: str | None
    confirmation_code: str | None
    confirmation_link: str | None
    received_at: str


class AlertAddressOut(BaseModel):
    enabled: bool
    address: str | None
    activity: list[InboundActivity]


async def _address_out(user: User) -> AlertAddressOut:
    if not inbound_enabled():
        return AlertAddressOut(enabled=False, address=None, activity=[])
    address = await address_for(user.id)
    recent = await InboundEmail.find(InboundEmail.user_id == user.id).sort(-InboundEmail.received_at).limit(8).to_list()
    return AlertAddressOut(
        enabled=True,
        address=f"{address.token}@{settings.INBOUND_EMAIL_DOMAIN}",
        activity=[
            InboundActivity(
                kind=r.kind, status=r.status, subject=r.subject, jobs_ingested=r.jobs_ingested,
                skipped_not_relevant=r.skipped_not_relevant, error=r.error, confirmation_code=r.confirmation_code,
                confirmation_link=r.confirmation_link, received_at=r.received_at.isoformat(),
            )
            for r in recent
        ],
    )


@router.get("/address", response_model=AlertAddressOut)
async def get_address(current_user: User = Depends(get_current_user)):
    return await _address_out(current_user)


@router.post("/address/rotate", response_model=AlertAddressOut)
async def rotate_address(current_user: User = Depends(get_current_user)):
    if not inbound_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Alert forwarding isn't set up on this server.")
    address = await address_for(current_user.id)
    address.token = _new_token()
    await address.save()
    return await _address_out(current_user)
