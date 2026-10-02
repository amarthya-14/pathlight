"""
Shared Gate 10 test doubles: a fake Google (OAuth + Gmail REST) installed by
monkeypatching httpx.AsyncClient.get/post — same hermetic style as test_github_mcp.py,
no real network. Records every request so tests can assert what was (and wasn't) sent.
"""
import base64
from datetime import datetime, timedelta, timezone

import httpx
from beanie import PydanticObjectId
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.crypto import encrypt_token
from app.models.integration import Integration
from app.integrations.google_oauth import GMAIL_SCOPES

ACCESS_TOKEN = "ya29.fake-access-token-PLAINTEXT"
REFRESH_TOKEN = "1//fake-refresh-token-PLAINTEXT"


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def use_test_encryption_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())


def configure_oauth(monkeypatch) -> None:
    use_test_encryption_key(monkeypatch)
    monkeypatch.setattr(settings, "GMAIL_MCP_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GMAIL_MCP_CLIENT_SECRET", "test-client-secret")


async def connect_gmail(user_id: str, expired: bool = False, scopes: list[str] | None = None) -> Integration:
    """Creates a connected Gmail Integration directly (bypassing the OAuth dance)."""
    integration = Integration(
        user_id=PydanticObjectId(user_id),
        provider="gmail",
        status="connected",
        scopes=scopes if scopes is not None else list(GMAIL_SCOPES),
        account_email="student@gmail.com",
        encrypted_access_token=encrypt_token(ACCESS_TOKEN),
        encrypted_refresh_token=encrypt_token(REFRESH_TOKEN),
        token_expiry=datetime.now(timezone.utc) + (timedelta(minutes=-5) if expired else timedelta(hours=1)),
    )
    await integration.insert()
    return integration


def gmail_message(message_id: str, subject: str, body: str, sender="jobalerts-noreply@linkedin.com", html=False) -> dict:
    return {
        "id": message_id,
        "threadId": f"t-{message_id}",
        "snippet": body[:50],
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Fri, 02 Oct 2026 09:00:00 +0530"},
            ],
            "parts": [{"mimeType": "text/html" if html else "text/plain", "body": {"data": b64(body)}}],
        },
    }


class FakeGoogle:
    def __init__(self, messages: list[dict] | None = None):
        self.messages = {m["id"]: m for m in (messages or [])}
        self.requests: list[tuple[str, str, dict]] = []  # (method, url, kwargs)
        self.fail_send = False
        self.fail_refresh = False
        self.unauthorized = False

    @property
    def sent(self) -> list[dict]:
        return [kw["json"] for method, url, kw in self.requests if url.endswith("/messages/send")]

    def install(self, monkeypatch) -> "FakeGoogle":
        fake = self

        async def _get(client, url, params=None, headers=None, **kw):
            fake.requests.append(("GET", url, {"params": params, "headers": headers}))
            request = httpx.Request("GET", url)
            if fake.unauthorized:
                return httpx.Response(401, json={"error": "invalid_token"}, request=request)
            if url.endswith("/profile"):
                return httpx.Response(200, json={"emailAddress": "student@gmail.com"}, request=request)
            if url.endswith("/messages"):
                return httpx.Response(
                    200, json={"messages": [{"id": i, "threadId": f"t-{i}"} for i in fake.messages]}, request=request
                )
            message_id = url.rsplit("/", 1)[-1]
            if message_id in fake.messages:
                return httpx.Response(200, json=fake.messages[message_id], request=request)
            return httpx.Response(404, json={"error": "not found"}, request=request)

        async def _post(client, url, data=None, json=None, headers=None, **kw):
            fake.requests.append(("POST", url, {"data": data, "json": json, "headers": headers}))
            request = httpx.Request("POST", url)
            if url.endswith("/token"):
                if data.get("grant_type") == "refresh_token":
                    if fake.fail_refresh:
                        return httpx.Response(400, json={"error": "invalid_grant"}, request=request)
                    return httpx.Response(
                        200, json={"access_token": "ya29.refreshed-PLAINTEXT", "expires_in": 3599}, request=request
                    )
                return httpx.Response(
                    200,
                    json={
                        "access_token": ACCESS_TOKEN,
                        "refresh_token": REFRESH_TOKEN,
                        "expires_in": 3599,
                        "scope": " ".join(GMAIL_SCOPES),
                    },
                    request=request,
                )
            if url.endswith("/revoke"):
                return httpx.Response(200, json={}, request=request)
            if url.endswith("/messages/send"):
                if fake.fail_send:
                    return httpx.Response(500, json={"error": "backend error"}, request=request)
                return httpx.Response(200, json={"id": "sent-123", "threadId": "t-sent"}, request=request)
            return httpx.Response(404, json={}, request=request)

        monkeypatch.setattr(httpx.AsyncClient, "get", _get)
        monkeypatch.setattr(httpx.AsyncClient, "post", _post)
        return self
