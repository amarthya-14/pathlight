"""
Integration — Gate 10. A user's connection to an external provider that needs a real
per-user OAuth token (Gmail, for now). docs/DATABASE.md had listed this as "Planned
(Gate 4+)"; Gmail sourcing/applying is the first thing that actually needs it.

Tokens are stored ONLY as Fernet ciphertext (app/core/crypto.py) and are never returned
by any API response — IntegrationOut (app/schemas/integration.py) exposes status/scopes/
account_email/timestamps only. tests/test_integrations.py asserts no plaintext token
substring ever reaches the stored document.
"""
from datetime import datetime, timezone

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel

# Cap on remembered Gmail message IDs per integration — enough to cover several days of
# job-alert digests for overlap-dedupe, small enough that the document never grows unbounded.
MAX_PROCESSED_MESSAGE_IDS = 500


class Integration(Document):
    user_id: Indexed(PydanticObjectId)
    provider: str  # "gmail" for now
    status: str  # connected | error
    scopes: list[str] = Field(default_factory=list)
    account_email: str | None = None
    encrypted_access_token: str
    encrypted_refresh_token: str | None = None
    token_expiry: datetime | None = None
    last_polled_at: datetime | None = None
    last_error: str | None = None
    # Gmail message IDs already fed into the pipeline — last_polled_at alone isn't enough,
    # because Gmail's `after:` search operator has day-level granularity in practice.
    processed_message_ids: list[str] = Field(default_factory=list)
    connected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "integrations"
        indexes = [
            IndexModel(
                [("user_id", ASCENDING), ("provider", ASCENDING)],
                unique=True,
                name="uq_integration_user_provider",
            ),
        ]
