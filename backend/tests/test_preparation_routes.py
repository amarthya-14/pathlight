"""
API-level Preparation Plan tests (app/api/routes/preparation.py). Uses the real
/api/opportunities/ingest pipeline (with Discovery faked, per every other pipeline test
in this project) to get to a real Application with a real Skill Gap result, rather than
constructing one by hand — this also incidentally exercises the pipeline's own
auto-generated first-pass plan (Gate 6's Planner node).
"""
from app.agents.schemas import ExtractedOpportunity
from tests.fakes import FakeLLM


def _auth_headers(client, email="prep-user@example.com", password="testpass123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/api/auth/login", data={"username": email, "password": password})
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _ingest_with_skill_gap(client, monkeypatch, headers, company="PlanCo"):
    """No resume uploaded -> every skill comes back `missing`, which is exactly the
    "something to prepare for" state the Planner node needs to have run automatically."""
    extracted = ExtractedOpportunity(
        company_name=company, role="Backend Intern", required_skills=["Python", "Django"]
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))
    resp = client.post(
        "/api/opportunities/ingest",
        json={"raw_text": f"{company} hiring Backend Intern", "source": "manual"},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


def test_pipeline_auto_generates_plan_when_skills_missing(client, monkeypatch):
    headers = _auth_headers(client)
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)
    ingest_body = _ingest_with_skill_gap(client, monkeypatch, headers)
    application_id = ingest_body["application_id"]

    resp = client.get(f"/api/applications/{application_id}/preparation-plan", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["tasks"]) == 2
    assert {t["skill"] for t in body["tasks"]} == {"Python", "Django"}
    # Django depends on Python per app/agents/planner.py's SKILL_PREREQUISITES.
    tasks_by_skill = {t["skill"]: t for t in body["tasks"]}
    python_task_id = tasks_by_skill["Python"]["id"]
    assert python_task_id in tasks_by_skill["Django"]["depends_on"]


def test_regenerate_plan_with_real_hours_per_day_updates_feasibility(client, monkeypatch):
    headers = _auth_headers(client, email="regen-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)
    ingest_body = _ingest_with_skill_gap(client, monkeypatch, headers, company="RegenCo")
    application_id = ingest_body["application_id"]

    # No deadline was extracted by the fake Discovery result, so available_hours/feasible
    # should come back None regardless of hours_per_day — "unknown," not "infeasible".
    resp = client.post(
        f"/api/applications/{application_id}/preparation-plan",
        json={"hours_per_day": 3.0},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["available_hours"] is None
    assert body["feasible"] is None
    assert body["total_estimated_hours"] > 0


def test_get_plan_before_any_generated_returns_404(client, monkeypatch):
    headers = _auth_headers(client, email="noplan-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)

    # An opportunity with no required/preferred skills means Skill Gap is a no-op, so
    # the Planner node is a no-op too — no plan should exist to fetch.
    extracted = ExtractedOpportunity(company_name="NoSkillsCo", role="Intern")
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))
    ingest_resp = client.post(
        "/api/opportunities/ingest",
        json={"raw_text": "NoSkillsCo hiring Intern", "source": "manual"},
        headers=headers,
    )
    application_id = ingest_resp.json()["application_id"]

    resp = client.get(f"/api/applications/{application_id}/preparation-plan", headers=headers)
    assert resp.status_code == 404


def test_regenerate_plan_requires_existing_skill_gap(client, monkeypatch):
    headers = _auth_headers(client, email="noskillgap-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)

    extracted = ExtractedOpportunity(company_name="EmptyCo", role="Intern")
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))
    ingest_resp = client.post(
        "/api/opportunities/ingest",
        json={"raw_text": "EmptyCo hiring Intern", "source": "manual"},
        headers=headers,
    )
    application_id = ingest_resp.json()["application_id"]

    resp = client.post(
        f"/api/applications/{application_id}/preparation-plan",
        json={"hours_per_day": 2.0},
        headers=headers,
    )
    assert resp.status_code == 400


def test_preparation_plan_not_owned_returns_404(client, monkeypatch):
    headers_a = _auth_headers(client, email="prep-owner-a@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers_a)
    ingest_body = _ingest_with_skill_gap(client, monkeypatch, headers_a, company="OwnedByACo")
    application_id = ingest_body["application_id"]

    headers_b = _auth_headers(client, email="prep-owner-b@example.com")
    resp = client.get(f"/api/applications/{application_id}/preparation-plan", headers=headers_b)
    assert resp.status_code == 404


def test_preparation_plan_requires_auth(client):
    resp = client.get("/api/applications/000000000000000000000000/preparation-plan")
    assert resp.status_code == 401
