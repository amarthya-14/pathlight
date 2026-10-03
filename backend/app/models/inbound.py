"""
Forwarded job alerts — the inbox-free way to get LinkedIn/Naukri alerts into Pathlight.

Each student gets a private address (<token>@INBOUND_EMAIL_DOMAIN). A Gmail filter
forwards only their job-alert emails there; an inbound-email service (e.g. a Cloudflare
Email Worker, infra/email-worker/) POSTs each message to /api/inbound/email. No access to
the student's mailbox is ever requested, so this works for everyone — unlike the Gmail
integration, which Google limits to test users until its restricted-scope review.
"""
from datetime import datetime, timezone

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field


class AlertAddress(Document):
    user_id: Indexed(PydanticObjectId, unique=True)
    # Random, unguessable local part. Rotatable if the address ever gets spammed.
    token: Indexed(str, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "alert_addresses"


class InboundEmail(Document):
    """What arrived at a student's address, for their status view. Bodies are never
    stored; non-alert mail is logged only as "ignored", without its subject."""
    user_id: Indexed(PydanticObjectId)
    kind: str  # job_alert | gmail_confirmation | ignored
    status: str  # processing | done | failed | ignored
    sender: str | None = None
    subject: str | None = None
    message_hash: Indexed(str)
    jobs_ingested: int = 0
    skipped_not_relevant: int = 0
    error: str | None = None
    # Gmail's "confirm forwarding" email: shown to the student so setup can't get stuck.
    confirmation_code: str | None = None
    confirmation_link: str | None = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "inbound_emails"
