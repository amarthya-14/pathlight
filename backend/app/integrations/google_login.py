"""
"Continue with Google" — sign-in only (openid email profile). Separate from the Gmail
integration on purpose: these scopes are non-sensitive, so they don't fall under Google's
restricted-scope verification that caps the Gmail integration at 100 test users.

GOOGLE_LOGIN_CLIENT_ID/SECRET default to the Gmail OAuth client; use a separate,
published OAuth client in production so sign-in works for everyone while Gmail access
stays in testing. The redirect URI must be registered on that client.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from app.core.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
STATE_PURPOSE = "google_login"


def client_id() -> str:
    return settings.GOOGLE_LOGIN_CLIENT_ID or settings.GMAIL_MCP_CLIENT_ID


def client_secret() -> str:
    return settings.GOOGLE_LOGIN_CLIENT_SECRET or settings.GMAIL_MCP_CLIENT_SECRET


def redirect_uri() -> str:
    if settings.GOOGLE_LOGIN_REDIRECT_URI:
        return settings.GOOGLE_LOGIN_REDIRECT_URI
    # Same backend host as the Gmail callback.
    return settings.GMAIL_OAUTH_REDIRECT_URI.replace("/api/integrations/gmail/callback", "/api/auth/google/callback")


def login_configured() -> bool:
    return bool(client_id() and client_secret())


def build_login_url() -> str:
    state = jwt.encode(
        {"purpose": STATE_PURPOSE, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    params = {
        "client_id": client_id(),
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def verify_login_state(state: str) -> bool:
    try:
        payload = jwt.decode(state, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return False
    return payload.get("purpose") == STATE_PURPOSE


async def fetch_google_identity(code: str) -> dict:
    """Exchanges the code and returns Google's userinfo (sub, email, email_verified,
    name). Raises on any failure."""
    async with httpx.AsyncClient(timeout=10.0) as http:
        token = await http.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id(),
                "client_secret": client_secret(),
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
        token.raise_for_status()
        info = await http.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {token.json()['access_token']}"})
        info.raise_for_status()
        return info.json()
