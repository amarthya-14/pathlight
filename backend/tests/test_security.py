"""decode_access_token (app/core/security.py) failure branches — added at Gate 9."""
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings
from app.core.security import decode_access_token


def test_decode_rejects_garbage_token():
    assert decode_access_token("not-a-real-jwt") is None


def test_decode_rejects_expired_token():
    expired = jwt.encode(
        {"sub": "someone", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(expired) is None


def test_oauth_state_token_cannot_be_used_as_a_login(client):
    from app.integrations.google_oauth import create_oauth_state

    client.post("/api/auth/register", json={"email": "state@example.com", "password": "testpass123"})
    token = client.post("/api/auth/login", data={"username": "state@example.com", "password": "testpass123"}).json()["access_token"]
    user_id = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

    state = create_oauth_state(user_id)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {state}"}).status_code == 401
