"""Login lockout, password reset, Google sign-in callback, usage limits."""
from app.api.routes import auth as auth_routes
from app.core.usage import DAILY_LIMITS, try_consume


def _register(client, email, password="testpass123"):
    client.post("/api/auth/register", json={"email": email, "password": password, "full_name": "Test User"})


def test_repeated_failed_logins_lock_the_account_temporarily(client):
    auth_routes._failures.clear()
    _register(client, "lock@example.com")
    for _ in range(auth_routes.MAX_FAILURES):
        assert client.post("/api/auth/login", data={"username": "lock@example.com", "password": "wrong-pass"}).status_code == 401
    locked = client.post("/api/auth/login", data={"username": "lock@example.com", "password": "testpass123"})
    assert locked.status_code == 429
    auth_routes._failures.clear()


async def test_reset_token_works_once_and_changes_the_password(client):
    from app.models.user import User

    _register(client, "reset@example.com")
    user = await User.find_one(User.email == "reset@example.com")
    token = auth_routes._reset_token(user)

    resp = client.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-pass"})
    assert resp.status_code == 200 and resp.json()["access_token"]
    assert client.post("/api/auth/login", data={"username": "reset@example.com", "password": "brand-new-pass"}).status_code == 200
    # Same link again: the password hash changed, so the token is dead.
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "another-pass1"}).status_code == 400


def test_reset_token_is_not_a_login_token():
    from jose import jwt

    from app.core.config import settings
    from app.core.security import decode_access_token

    forged = jwt.encode({"sub": "x", "purpose": "password_reset"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    assert decode_access_token(forged) is None


def test_forgot_password_explains_when_email_is_not_configured(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.SMTP_HOST", "")
    resp = client.post("/api/auth/forgot-password", json={"email": "anyone@example.com"})
    assert resp.status_code == 503 and "Google" in resp.json()["detail"]


async def test_google_callback_creates_account_and_redirects_with_token(client, monkeypatch):
    from app.models.user import User

    monkeypatch.setattr("app.api.routes.auth.verify_login_state", lambda s: True)

    async def identity(code):
        return {"email": "New.Student@Gmail.com", "email_verified": True, "name": "New Student"}

    monkeypatch.setattr("app.api.routes.auth.fetch_google_identity", identity)
    resp = client.get("/api/auth/google/callback?code=abc&state=s", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/callback#token=" in resp.headers["location"]
    user = await User.find_one(User.email == "new.student@gmail.com")
    assert user.full_name == "New Student"
    token = resp.headers["location"].split("#token=")[1]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_google_callback_rejects_unverified_email(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.auth.verify_login_state", lambda s: True)

    async def identity(code):
        return {"email": "x@example.com", "email_verified": False}

    monkeypatch.setattr("app.api.routes.auth.fetch_google_identity", identity)
    resp = client.get("/api/auth/google/callback?code=abc&state=s", follow_redirects=False)
    assert "google=unverified" in resp.headers["location"]


async def test_daily_usage_limit_stops_at_the_limit(client):
    user_id = "64b7f0000000000000000009"
    results = [await try_consume(user_id, "autopilot") for _ in range(DAILY_LIMITS["autopilot"] + 2)]
    assert results.count(True) == DAILY_LIMITS["autopilot"]
    assert results[-1] is False
