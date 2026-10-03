"""
Integration schemas (Gate 10). IntegrationOut is deliberately an allowlist of fields —
it has no token fields at all, so a stored token can't leak through a response even by
accident (e.g. a future `**integration.model_dump()`).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    provider: str
    status: str
    scopes: list[str]
    account_email: str | None
    connected_at: datetime
    last_polled_at: datetime | None
    last_error: str | None


class GmailConnectOut(BaseModel):
    auth_url: str


class GmailSyncOut(BaseModel):
    messages_seen: int
    opportunities_ingested: int
    skipped_already_processed: int
    skipped_not_relevant: int = 0
    failures: list[str]


class GmailSyncStatus(BaseModel):
    state: str  # idle | running | done | error
    started_at: datetime | None = None
    result: GmailSyncOut | None = None
    error: str | None = None
