"""
API-level ingest tests, including the document_id path — the first real (non-test-
harness-direct) caller of the Filesystem MCP tool, tying Gate 3 and Gate 4 together.
"""
from app.agents.schemas import ExtractedOpportunity
from tests.fakes import FakeLLM


def _auth_headers(client, email="ingest-user@example.com", password="testpass123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/api/auth/login", data={"username": email, "password": password})
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_ingest_raw_text(client, monkeypatch):
    headers = _auth_headers(client)
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)

    extracted = ExtractedOpportunity(
        company_name="RawTextCo", role="Data Intern", min_cgpa=7.0, allowed_branches=["CSE"]
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))

    resp = client.post(
        "/api/opportunities/ingest",
        json={"raw_text": "RawTextCo hiring Data Intern", "source": "manual"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["company_name"] == "RawTextCo"
    assert body["eligibility"]["decision"] == "eligible"


def test_ingest_from_document_uses_mcp(client, monkeypatch):
    """The document_id path reads the document's content via mcp_read_document, not by
    the route touching disk directly — same Filesystem MCP tool built in Gate 3."""
    headers = _auth_headers(client, email="doc-ingest@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "ECE"}, headers=headers)

    create_resp = client.post(
        "/api/documents/paste",
        json={"doc_type": "job_description", "title": "Doc-based JD", "text": "MCPCo hiring Hardware Intern"},
        headers=headers,
    )
    document_id = create_resp.json()["id"]

    extracted = ExtractedOpportunity(company_name="MCPCo", role="Hardware Intern")
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))

    resp = client.post("/api/opportunities/ingest", json={"document_id": document_id}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["company_name"] == "MCPCo"


def test_ingest_document_not_owned_returns_404(client, monkeypatch):
    headers_a = _auth_headers(client, email="owner-a2@example.com")
    create_resp = client.post(
        "/api/documents/paste",
        json={"doc_type": "job_description", "title": "Private", "text": "secret"},
        headers=headers_a,
    )
    document_id = create_resp.json()["id"]

    headers_b = _auth_headers(client, email="owner-b2@example.com")
    resp = client.post("/api/opportunities/ingest", json={"document_id": document_id}, headers=headers_b)
    assert resp.status_code == 404


def test_ingest_requires_exactly_one_of_raw_text_or_document_id(client):
    headers = _auth_headers(client, email="badreq@example.com")

    resp = client.post("/api/opportunities/ingest", json={}, headers=headers)
    assert resp.status_code == 400

    resp2 = client.post(
        "/api/opportunities/ingest", json={"raw_text": "x", "document_id": "y"}, headers=headers
    )
    assert resp2.status_code == 400


def test_ingest_needs_human_review_returns_502(client, monkeypatch):
    headers = _auth_headers(client, email="review-user@example.com")

    monkeypatch.setattr(
        "app.agents.discovery.get_small_llm", lambda: FakeLLM(raise_exc=RuntimeError("Gemini down"))
    )

    resp = client.post(
        "/api/opportunities/ingest", json={"raw_text": "will fail", "source": "manual"}, headers=headers
    )
    assert resp.status_code == 502


def test_ingest_requires_auth(client):
    resp = client.post("/api/opportunities/ingest", json={"raw_text": "x"})
    assert resp.status_code == 401
