"""
Google OAuth2 for the Gmail integration — Gate 10. Plain authorization-code flow over
httpx (no google-auth-oauthlib dependency: the whole surface is three HTTP calls, and
httpx is already how every other external API in this project is reached and mocked).

Scopes are least-privilege per docs/AUTONOMOUS_APPLICATIONS.md §2: gmail.readonly for
sourcing, gmail.send for applying — never full mailbox access (no gmail.modify, no
https://mail.google.com/).

The OAuth `state` parameter is a short-lived signed JWT carrying the user id. It has to
be: Google redirects the *browser* to the callback, which carries no Authorization
header, so the callback can only learn who started the flow from `state` — and signing
it is what stops an attacker from completing a flow into someone else's account (CSRF).
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from beanie import PydanticObjectId
from jose import JWTError, jwt

from app.core.config import settings
from app.core.crypto import decrypt_token, encrypt_token
from app.models.integration import Integration

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

STATE_TTL_MINUTES = 10
STATE_PURPOSE = "gmail_oauth"
# Refresh a little before actual expiry so a token never dies mid-request.
EXPIRY_SKEW = timedelta(seconds=60)


class GmailNotConnected(RuntimeError):
    """The user has no usable Gmail integration (never connected, or refresh failed)."""


def oauth_configured() -> bool:
    return bool(settings.GMAIL_MCP_CLIENT_ID and settings.GMAIL_MCP_CLIENT_SECRET)


def create_oauth_state(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "purpose": STATE_PURPOSE,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_oauth_state(state: str) -> str | None:
    """Returns the user id if `state` is a valid, unexpired Gmail-OAuth state token.
    The purpose claim stops a regular login access token being replayed as a state."""
    try:
        payload = jwt.decode(state, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("purpose") != STATE_PURPOSE:
        return None
    return payload.get("sub")


def build_consent_url(user_id: str) -> str:
    params = {
        "client_id": settings.GMAIL_MCP_CLIENT_ID,
        "redirect_uri": settings.GMAIL_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        # offline + consent: guarantees a refresh_token, so the background poller keeps
        # working after the ~1h access token expires.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": create_oauth_state(user_id),
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _expiry_from(expires_in: int | None) -> datetime | None:
    if not expires_in:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))


async def exchange_code_and_store(user_id: str, code: str) -> Integration:
    """Exchanges an authorization code for tokens, encrypts them, and upserts the user's
    Gmail Integration. Raises on any Google-side failure — the callback route turns that
    into a redirect with ?gmail=error rather than a raw 500 in the user's browser."""
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        token_resp = await http_client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GMAIL_MCP_CLIENT_ID,
                "client_secret": settings.GMAIL_MCP_CLIENT_SECRET,
                "redirect_uri": settings.GMAIL_OAUTH_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        access_token = tokens["access_token"]
        profile_resp = await http_client.get(
            GMAIL_PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        profile_resp.raise_for_status()
        account_email = profile_resp.json().get("emailAddress")

    granted_scopes = tokens.get("scope", " ".join(GMAIL_SCOPES)).split()
    refresh_token = tokens.get("refresh_token")

    integration = await Integration.find_one(
        Integration.user_id == PydanticObjectId(user_id), Integration.provider == "gmail"
    )
    if integration is None:
        integration = Integration(
            user_id=PydanticObjectId(user_id),
            provider="gmail",
            status="connected",
            encrypted_access_token=encrypt_token(access_token),
        )
    integration.status = "connected"
    integration.last_error = None
    integration.scopes = granted_scopes
    integration.account_email = account_email
    integration.encrypted_access_token = encrypt_token(access_token)
    # Google omits refresh_token on some re-consents — keep the one we already have.
    if refresh_token:
        integration.encrypted_refresh_token = encrypt_token(refresh_token)
    integration.token_expiry = _expiry_from(tokens.get("expires_in"))
    integration.connected_at = datetime.now(timezone.utc)
    await integration.save()
    return integration


async def get_gmail_integration(user_id: str) -> Integration | None:
    return await Integration.find_one(
        Integration.user_id == PydanticObjectId(user_id), Integration.provider == "gmail"
    )


def _is_expired(integration: Integration) -> bool:
    if integration.token_expiry is None:
        return False
    expiry = integration.token_expiry
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry - EXPIRY_SKEW <= datetime.now(timezone.utc)


async def get_valid_access_token(user_id: str) -> str:
    """Returns a usable plaintext access token for the user's Gmail, refreshing it first
    if it's (about to be) expired. Plaintext exists only in memory for the duration of
    the call — it's never written back unencrypted. A failed refresh (revoked consent,
    deleted OAuth client) marks the integration `error` so the UI can ask to reconnect."""
    integration = await get_gmail_integration(user_id)
    if integration is None or integration.status != "connected":
        raise GmailNotConnected("Gmail is not connected for this user")

    if not _is_expired(integration):
        return decrypt_token(integration.encrypted_access_token)

    if not integration.encrypted_refresh_token:
        integration.status = "error"
        integration.last_error = "Access token expired and no refresh token is stored — reconnect Gmail."
        await integration.save()
        raise GmailNotConnected(integration.last_error)

    async with httpx.AsyncClient(timeout=10.0) as http_client:
        resp = await http_client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GMAIL_MCP_CLIENT_ID,
                "client_secret": settings.GMAIL_MCP_CLIENT_SECRET,
                "refresh_token": decrypt_token(integration.encrypted_refresh_token),
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code >= 400:
        integration.status = "error"
        integration.last_error = f"Token refresh failed ({resp.status_code}) — reconnect Gmail."
        await integration.save()
        raise GmailNotConnected(integration.last_error)

    tokens = resp.json()
    access_token = tokens["access_token"]
    integration.encrypted_access_token = encrypt_token(access_token)
    integration.token_expiry = _expiry_from(tokens.get("expires_in"))
    await integration.save()
    return access_token


async def revoke_and_delete(user_id: str) -> bool:
    """Revokes the token with Google (best effort — a token that's already invalid is
    exactly what we wanted anyway) and deletes the stored Integration. Returns False if
    there was nothing to delete."""
    integration = await get_gmail_integration(user_id)
    if integration is None:
        return False

    token_ciphertext = integration.encrypted_refresh_token or integration.encrypted_access_token
    try:
        token = decrypt_token(token_ciphertext)
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            await http_client.post(GOOGLE_REVOKE_URL, data={"token": token})
    except Exception:
        pass

    await integration.delete()
    return True
