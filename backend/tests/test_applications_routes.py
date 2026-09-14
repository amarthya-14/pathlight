"""
API-level Applications list/detail tests (app/api/routes/applications.py, Gate 8) —
these didn't exist before this gate; IngestResponse only ever returned eligibility/
skill_gap once, at ingest time (see docs/API.md).
"""
from app.agents.schemas import ExtractedOpportunity
from tests.fakes import FakeLLM


def _auth_headers(client, email="apps-user@example.com", password="testpass123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/api/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


def _ingest(client, monkeypatch, headers, company, required_skills=None):
    extracted = ExtractedOpportunity(
        company_name=company, role="Backend Intern", required_skills=required_skills or []
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))
    resp = client.post(
        "/api/opportunities/ingest",
        json={"raw_text": f"{company} hiring Backend Intern", "source": "manual"},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


def test_list_applications_includes_company_role_and_eligibility(client, monkeypatch):
    headers = _auth_headers(client)
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)
    _ingest(client, monkeypatch, headers, "ListCo")

    resp = client.get("/api/applications", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["company_name"] == "ListCo"
    assert body[0]["role"] == "Backend Intern"
    assert body[0]["eligibility"]["decision"] == "eligible"


def test_get_application_detail_not_owned_returns_404(client, monkeypatch):
    headers_a = _auth_headers(client, email="apps-owner-a@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers_a)
    ingest_body = _ingest(client, monkeypatch, headers_a, "OwnedCo")

    headers_b = _auth_headers(client, email="apps-owner-b@example.com")
    resp = client.get(f"/api/applications/{ingest_body['application_id']}", headers=headers_b)
    assert resp.status_code == 404


def test_skill_gap_note_recomputed_from_current_resume_state(client, monkeypatch):
    """The note isn't stored at ingest time — it's recomputed from whether a resume is
    indexed *right now*. Ingest without a resume (note should appear), then upload one
    and confirm the note disappears on a fresh fetch, without re-running the pipeline."""
    headers = _auth_headers(client, email="notes-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)
    ingest_body = _ingest(client, monkeypatch, headers, "NotesCo", required_skills=["Python"])
    application_id = ingest_body["application_id"]

    resp1 = client.get(f"/api/applications/{application_id}", headers=headers)
    assert resp1.json()["skill_gap_note"] is not None

    client.post(
        "/api/documents/paste",
        json={"doc_type": "resume", "title": "Resume", "text": "Experienced with Python."},
        headers=headers,
    )

    resp2 = client.get(f"/api/applications/{application_id}", headers=headers)
    assert resp2.json()["skill_gap_note"] is None


def test_list_applications_empty_for_new_user(client):
    headers = _auth_headers(client, email="empty-user@example.com")
    resp = client.get("/api/applications", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_applications_require_auth(client):
    resp = client.get("/api/applications")
    assert resp.status_code == 401
