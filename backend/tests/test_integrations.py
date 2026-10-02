"""
Gate 10: token encryption at rest + the Gmail OAuth connect/callback/disconnect routes.
Google is faked at the httpx level (tests/gmail_fakes.py) — no real network.
"""
from urllib.parse import parse_qs, urlparse

import pytest
from beanie import PydanticObjectId

from app.core.crypto import TokenEncryptionUnavailable, decrypt_token, encrypt_token
from app.integrations.google_oauth import (
    GmailNotConnected,
    create_oauth_state,
    get_valid_access_token,
)
from app.core.security import create_access_token
from app.models.integration import Integration
from tests.gmail_fakes import (
    ACCESS_TOKEN,
    REFRESH_TOKEN,
    FakeGoogle,
    configure_oauth,
    connect_gmail,
    use_test_encryption_key,
)


def _register(client, email="integrations-user@example.com"):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123"})
    login = client.post("/api/auth/login", data={"username": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    return user_id, headers


# --- crypto -----------------------------------------------------------------------


def test_encrypt_decrypt_round_trip(monkeypatch):
    use_test_encryption_key(monkeypatch)
    ciphertext = encrypt_token("secret-token")
    assert ciphertext != "secret-token"
    assert "secret-token" not in ciphertext
    assert decrypt_token(ciphertext) == "secret-token"


def test_encryption_refuses_without_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.TOKEN_ENCRYPTION_KEY", "")
    with pytest.raises(TokenEncryptionUnavailable):
        encrypt_token("secret-token")


def test_decrypt_with_wrong_key_fails_loudly(monkeypatch):
    use_test_encryption_key(monkeypatch)
    ciphertext = encrypt_token("secret-token")
    use_test_encryption_key(monkeypatch)  # rotate to a different key
    with pytest.raises(TokenEncryptionUnavailable):
        decrypt_token(ciphertext)


# --- connect / callback -------------------------------------------------------------


def test_connect_returns_503_when_oauth_not_configured(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.GMAIL_MCP_CLIENT_ID", "")
    _user_id, headers = _register(client)
    resp = client.get("/api/integrations/gmail/connect", headers=headers)
    assert resp.status_code == 503


def test_connect_returns_503_without_encryption_key_rather_than_storing_plaintext(client, monkeypatch):
    configure_oauth(monkeypatch)
    monkeypatch.setattr("app.core.config.settings.TOKEN_ENCRYPTION_KEY", "")
    _user_id, headers = _register(client)
    resp = client.get("/api/integrations/gmail/connect", headers=headers)
    assert resp.status_code == 503
    assert "encryption" in resp.json()["detail"].lower()


def test_connect_url_requests_least_privilege_scopes_and_offline_access(client, monkeypatch):
    configure_oauth(monkeypatch)
    _user_id, headers = _register(client)
    resp = client.get("/api/integrations/gmail/connect", headers=headers)
    assert resp.status_code == 200

    query = parse_qs(urlparse(resp.json()["auth_url"]).query)
    scopes = query["scope"][0].split()
    assert set(scopes) == {
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    }
    assert query["access_type"] == ["offline"]
    assert query["state"][0]


async def test_callback_stores_only_encrypted_tokens(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    user_id, headers = _register(client)

    resp = client.get(
        "/api/integrations/gmail/callback",
        params={"code": "auth-code", "state": create_oauth_state(user_id)},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/integrations?gmail=connected")

    integration = await Integration.find_one(Integration.user_id == PydanticObjectId(user_id))
    assert integration.status == "connected"
    assert integration.account_email == "student@gmail.com"

    # The regression this test exists for: no plaintext token anywhere in the stored doc.
    stored = str(integration.model_dump())
    assert ACCESS_TOKEN not in stored
    assert REFRESH_TOKEN not in stored
    assert decrypt_token(integration.encrypted_access_token) == ACCESS_TOKEN

    # ...and none in any API response either.
    listed = client.get("/api/integrations", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "connected"
    assert "token" not in str(listed.json()).lower()
    assert any(url.endswith("/token") for _m, url, _kw in google.requests)


def test_callback_rejects_forged_state(client, monkeypatch):
    configure_oauth(monkeypatch)
    FakeGoogle().install(monkeypatch)
    user_id, _headers = _register(client)

    resp = client.get(
        "/api/integrations/gmail/callback",
        params={"code": "auth-code", "state": "not-a-real-state"},
        follow_redirects=False,
    )
    assert "gmail=error" in resp.headers["location"]


def test_callback_rejects_a_login_token_replayed_as_state(client, monkeypatch):
    """A normal access token is signed with the same secret — the purpose claim is what
    stops it being accepted as an OAuth state."""
    configure_oauth(monkeypatch)
    FakeGoogle().install(monkeypatch)
    user_id, _headers = _register(client)

    resp = client.get(
        "/api/integrations/gmail/callback",
        params={"code": "auth-code", "state": create_access_token(user_id)},
        follow_redirects=False,
    )
    assert "gmail=error" in resp.headers["location"]


def test_callback_relays_user_denial(client):
    resp = client.get(
        "/api/integrations/gmail/callback", params={"error": "access_denied"}, follow_redirects=False
    )
    assert "gmail=error" in resp.headers["location"]
    assert "access_denied" in resp.headers["location"]


# --- disconnect / refresh -----------------------------------------------------------


async def test_disconnect_revokes_and_deletes(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    user_id, headers = _register(client)
    await connect_gmail(user_id)

    resp = client.delete("/api/integrations/gmail", headers=headers)
    assert resp.status_code == 204
    assert await Integration.find_one(Integration.user_id == PydanticObjectId(user_id)) is None
    revoke_calls = [kw for _m, url, kw in google.requests if url.endswith("/revoke")]
    assert revoke_calls and revoke_calls[0]["data"]["token"] == REFRESH_TOKEN

    assert client.delete("/api/integrations/gmail", headers=headers).status_code == 404


async def test_expired_token_is_refreshed_and_re_encrypted(client, monkeypatch):
    configure_oauth(monkeypatch)
    FakeGoogle().install(monkeypatch)
    user_id, _headers = _register(client)
    await connect_gmail(user_id, expired=True)

    token = await get_valid_access_token(user_id)
    assert token == "ya29.refreshed-PLAINTEXT"

    integration = await Integration.find_one(Integration.user_id == PydanticObjectId(user_id))
    assert "refreshed-PLAINTEXT" not in str(integration.model_dump())
    assert decrypt_token(integration.encrypted_access_token) == "ya29.refreshed-PLAINTEXT"


async def test_failed_refresh_marks_integration_error(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    google.fail_refresh = True
    user_id, headers = _register(client)
    await connect_gmail(user_id, expired=True)

    with pytest.raises(GmailNotConnected):
        await get_valid_access_token(user_id)

    listed = client.get("/api/integrations", headers=headers).json()
    assert listed[0]["status"] == "error"
    assert "reconnect" in listed[0]["last_error"].lower()
