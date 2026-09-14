"""API-level dashboard home aggregation tests (app/api/routes/dashboard.py, Gate 8)."""
from app.agents.schemas import ExtractedOpportunity
from tests.fakes import FakeLLM


def _auth_headers(client, email="dash-user@example.com", password="testpass123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/api/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


def _ingest(client, monkeypatch, headers, company, required_skills=None, deadline=None):
    extracted = ExtractedOpportunity(
        company_name=company, role="Intern", required_skills=required_skills or [], deadline=deadline
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))
    resp = client.post(
        "/api/opportunities/ingest", json={"raw_text": f"{company} hiring", "source": "manual"}, headers=headers
    )
    assert resp.status_code == 200
    return resp.json()


def test_dashboard_home_empty_for_new_user(client):
    headers = _auth_headers(client)
    resp = client.get("/api/dashboard/home", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["recent_applications"] == []
    assert body["urgent_deadlines"] == []
    assert body["has_profile"] is False
    assert body["has_resume"] is False


def test_dashboard_home_surfaces_urgent_deadline_and_skill_summary(client, monkeypatch):
    import datetime as dt

    headers = _auth_headers(client, email="urgent-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)

    soon = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)).isoformat()
    far = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=90)).isoformat()

    _ingest(client, monkeypatch, headers, "SoonCo", required_skills=["Python", "AWS"], deadline=soon)
    _ingest(client, monkeypatch, headers, "FarCo", required_skills=["Python"], deadline=far)

    resp = client.get("/api/dashboard/home", headers=headers)
    body = resp.json()

    assert len(body["urgent_deadlines"]) == 1
    assert body["urgent_deadlines"][0]["company_name"] == "SoonCo"
    assert len(body["recent_applications"]) == 2
    assert body["total_missing_skills"] > 0
    assert "Python" in body["most_common_missing_skills"]
    assert body["has_profile"] is True


def test_dashboard_home_requires_auth(client):
    resp = client.get("/api/dashboard/home")
    assert resp.status_code == 401
