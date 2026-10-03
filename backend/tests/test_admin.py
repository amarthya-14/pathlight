"""Admin stats: only for ADMIN_EMAILS, aggregates only."""


def _login(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123"})
    token = client.post("/api/auth/login", data={"username": email, "password": "testpass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_stats_are_hidden_from_non_admins(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ADMIN_EMAILS", "founder@example.com")
    headers = _login(client, "student@example.com")
    assert client.get("/api/admin/stats", headers=headers).status_code == 404
    assert client.get("/api/auth/me", headers=headers).json()["is_admin"] is False


def test_admin_sees_aggregates(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ADMIN_EMAILS", "Founder@example.com")
    _login(client, "someone@example.com")
    headers = _login(client, "founder@example.com")
    assert client.get("/api/auth/me", headers=headers).json()["is_admin"] is True
    stats = client.get("/api/admin/stats", headers=headers).json()
    assert stats["users"]["total"] == 2
    assert "funnel" in stats and "jobs" in stats
