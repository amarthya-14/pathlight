"""
Gate 10: the human review gate — GET /tailored-resume and POST /review
(app/api/routes/applications.py). The properties that matter: skip never touches Gmail,
approve sends exactly once, nothing is sent without an explicit approval, and a missing
apply email is surfaced (MANUAL_APPLY_REQUIRED), never silently swallowed.
"""
from app.agents.schemas import ExtractedOpportunity, TailoredResumeResult
from tests.fakes import FakeLLM
from tests.gmail_fakes import FakeGoogle, configure_oauth, connect_gmail

RESUME = "Sam Lee\nSkills: Python, FastAPI, SQL\nProject: FastAPI service for campus events."


def _user(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123"})
    login = client.post("/api/auth/login", data={"username": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)
    client.post("/api/documents/paste", json={"doc_type": "resume", "title": "Resume", "text": RESUME}, headers=headers)
    return user_id, headers


def _ingest_ready(client, monkeypatch, headers, apply_email="careers@reviewco.dev", application_url=None):
    extracted = ExtractedOpportunity(
        company_name="ReviewCo",
        role="Backend Intern",
        required_skills=["Python"],
        apply_email=apply_email,
        application_url=application_url,
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))
    tailored = TailoredResumeResult(
        tailored_text=RESUME.replace("Skills: Python", "Skills: Python (primary)"),
        cover_note="Dear Hiring Team, I'd like to apply for the Backend Intern role.",
        changes_summary=["Highlighted Python as primary skill"],
        skills_emphasized=["Python"],
        confidence=0.85,
    )
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: FakeLLM(canned_result=tailored))
    resp = client.post("/api/opportunities/ingest", json={"raw_text": "ReviewCo hiring"}, headers=headers)
    assert resp.status_code == 200
    application_id = resp.json()["application_id"]
    detail = client.get(f"/api/applications/{application_id}", headers=headers).json()
    assert detail["status_history"][-1]["stage"] == "READY_TO_APPLY"
    return application_id


async def test_tailored_resume_returns_base_text_for_diff(client, monkeypatch):
    _uid, headers = _user(client, "review-get@example.com")
    application_id = _ingest_ready(client, monkeypatch, headers)

    resp = client.get(f"/api/applications/{application_id}/tailored-resume", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_resume_text"] == RESUME
    assert "Python (primary)" in body["tailored_text"]
    assert body["cover_note"].startswith("Dear Hiring Team")


async def test_skip_records_skipped_and_never_calls_gmail(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    user_id, headers = _user(client, "review-skip@example.com")
    await connect_gmail(user_id)
    application_id = _ingest_ready(client, monkeypatch, headers)

    resp = client.post(f"/api/applications/{application_id}/review", json={"approve": False}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "skipped"
    assert resp.json()["application"]["status_history"][-1]["stage"] == "SKIPPED_BY_USER"
    assert google.sent == []
    assert not any("gmail.googleapis.com" in url for _m, url, _kw in google.requests)


async def test_approve_sends_tailored_resume_exactly_once(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    user_id, headers = _user(client, "review-approve@example.com")
    await connect_gmail(user_id)
    application_id = _ingest_ready(client, monkeypatch, headers)

    resp = client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "applied"
    assert body["sent_to"] == "careers@reviewco.dev"
    assert body["application"]["status_history"][-1]["stage"] == "APPLIED"
    assert len(google.sent) == 1

    # Double-click / second tab: rejected, still exactly one email.
    again = client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)
    assert again.status_code == 409
    assert len(google.sent) == 1


async def test_approve_without_apply_email_requires_manual_apply(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    _uid, headers = _user(client, "review-manual@example.com")
    application_id = _ingest_ready(
        client, monkeypatch, headers, apply_email=None, application_url="https://www.linkedin.com/jobs/view/42"
    )

    resp = client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "manual_apply_required"
    assert body["application_url"] == "https://www.linkedin.com/jobs/view/42"
    assert body["application"]["status_history"][-1]["stage"] == "MANUAL_APPLY_REQUIRED"
    assert google.sent == []


async def test_approve_requires_connected_gmail_and_leaves_state_untouched(client, monkeypatch):
    _uid, headers = _user(client, "review-noconn@example.com")
    application_id = _ingest_ready(client, monkeypatch, headers)

    resp = client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)
    assert resp.status_code == 409
    assert "Connect Gmail" in resp.json()["detail"]
    detail = client.get(f"/api/applications/{application_id}", headers=headers).json()
    assert detail["status_history"][-1]["stage"] == "READY_TO_APPLY"


async def test_approve_requires_send_scope(client, monkeypatch):
    configure_oauth(monkeypatch)
    FakeGoogle().install(monkeypatch)
    user_id, headers = _user(client, "review-readonly@example.com")
    await connect_gmail(user_id, scopes=["https://www.googleapis.com/auth/gmail.readonly"])
    application_id = _ingest_ready(client, monkeypatch, headers)

    resp = client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)
    assert resp.status_code == 409


async def test_failed_send_is_reported_and_can_be_retried(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    google.fail_send = True
    user_id, headers = _user(client, "review-sendfail@example.com")
    await connect_gmail(user_id)
    application_id = _ingest_ready(client, monkeypatch, headers)

    resp = client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)
    assert resp.status_code == 502
    detail = client.get(f"/api/applications/{application_id}", headers=headers).json()
    assert detail["status_history"][-1]["stage"] == "READY_TO_APPLY"

    google.fail_send = False
    retry = client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)
    assert retry.status_code == 200
    assert retry.json()["outcome"] == "applied"


async def test_review_other_users_application_returns_404(client, monkeypatch):
    _uid, headers_a = _user(client, "review-owner-a@example.com")
    application_id = _ingest_ready(client, monkeypatch, headers_a)
    _uid_b, headers_b = _user(client, "review-owner-b@example.com")

    assert client.post(
        f"/api/applications/{application_id}/review", json={"approve": False}, headers=headers_b
    ).status_code == 404
    assert client.get(f"/api/applications/{application_id}/tailored-resume", headers=headers_b).status_code == 404


async def test_review_rejected_when_not_ready(client, monkeypatch):
    _uid, headers = _user(client, "review-notready@example.com")
    extracted = ExtractedOpportunity(company_name="EarlyCo", role="Intern")
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))
    # default conftest tailor LLM raises -> tailoring degrades, never READY_TO_APPLY
    application_id = client.post(
        "/api/opportunities/ingest", json={"raw_text": "EarlyCo hiring"}, headers=headers
    ).json()["application_id"]

    resp = client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)
    assert resp.status_code == 409


async def test_review_claim_is_atomic(client, monkeypatch):
    """The stage check above can't stop two requests that both read READY_TO_APPLY before
    either writes — the atomic claim is what does. Exercised directly here."""
    import asyncio

    from beanie import PydanticObjectId

    from app.api.routes.applications import _claim_review, _release_review

    _uid, headers = _user(client, "review-claim@example.com")
    application_id = PydanticObjectId(_ingest_ready(client, monkeypatch, headers))

    results = await asyncio.gather(*[_claim_review(application_id) for _ in range(5)])
    assert results.count(True) == 1

    await _release_review(application_id)
    assert await _claim_review(application_id) is True


async def test_tailor_on_demand_after_uploading_resume(client, monkeypatch):
    """Applications ingested before any resume existed (the real-world case that showed up
    with the first live Gmail sync) can be tailored afterwards without re-ingesting."""
    client.post("/api/auth/register", json={"email": "late-resume@example.com", "password": "testpass123"})
    login = client.post("/api/auth/login", data={"username": "late-resume@example.com", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)

    extracted = ExtractedOpportunity(company_name="LateCo", role="Backend Intern", required_skills=["Python"])
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))
    application_id = client.post(
        "/api/opportunities/ingest", json={"raw_text": "LateCo hiring"}, headers=headers
    ).json()["application_id"]

    no_resume = client.post(f"/api/applications/{application_id}/tailor", headers=headers)
    assert no_resume.status_code == 400
    assert "No resume on file" in no_resume.json()["detail"]

    client.post("/api/documents/upload", data={"doc_type": "resume"},
                files={"file": ("resume.txt", RESUME.encode(), "text/plain")}, headers=headers)
    tailored = TailoredResumeResult(tailored_text=RESUME, cover_note="Dear Hiring Team,", confidence=0.7)
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: FakeLLM(canned_result=tailored))

    resp = client.post(f"/api/applications/{application_id}/tailor", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["base_resume_text"] == RESUME
    detail = client.get(f"/api/applications/{application_id}", headers=headers).json()
    assert detail["status_history"][-1]["stage"] == "READY_TO_APPLY"

    # Regenerating doesn't stack duplicate READY_TO_APPLY events.
    client.post(f"/api/applications/{application_id}/tailor", headers=headers)
    detail = client.get(f"/api/applications/{application_id}", headers=headers).json()
    assert [e["stage"] for e in detail["status_history"]].count("READY_TO_APPLY") == 1


async def test_sent_application_attaches_a_pdf_resume(client, monkeypatch):
    import base64
    import email
    import email.policy

    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    user_id, headers = _user(client, "review-pdf@example.com")
    await connect_gmail(user_id)
    application_id = _ingest_ready(client, monkeypatch, headers)

    client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)

    parsed = email.message_from_bytes(base64.urlsafe_b64decode(google.sent[0]["raw"] + "=="), policy=email.policy.default)
    attachment = list(parsed.iter_parts())[1]
    assert attachment.get_content_type() == "application/pdf"
    assert attachment.get_filename().endswith(".pdf")
    assert attachment.get_content().startswith(b"%PDF")


async def test_assisted_apply_pdf_download_and_mark_applied(client, monkeypatch):
    from io import BytesIO

    from pypdf import PdfReader

    _uid, headers = _user(client, "assisted@example.com")
    application_id = _ingest_ready(
        client, monkeypatch, headers, apply_email=None, application_url="https://www.linkedin.com/jobs/view/7"
    )

    pdf = client.get(f"/api/applications/{application_id}/tailored-resume.pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert ".pdf" in pdf.headers["content-disposition"]
    assert "Python (primary)" in PdfReader(BytesIO(pdf.content)).pages[0].extract_text()

    # Can't mark applied before approving.
    assert client.post(f"/api/applications/{application_id}/mark-applied", headers=headers).status_code == 409

    approved = client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)
    assert approved.json()["outcome"] == "manual_apply_required"

    marked = client.post(f"/api/applications/{application_id}/mark-applied", headers=headers)
    assert marked.status_code == 200
    assert marked.json()["status_history"][-1]["stage"] == "APPLIED"
    # ...and only once.
    assert client.post(f"/api/applications/{application_id}/mark-applied", headers=headers).status_code == 409


async def test_recheck_with_full_job_description_catches_experience_requirement(client, monkeypatch):
    """The real-world flow: an alert-sourced application, then the user pastes the full
    JD that says 7+ years. The re-check must flip it to not eligible."""
    _uid, headers = _user(client, "recheck@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE", "experience_years": 0}, headers=headers)
    application_id = _ingest_ready(client, monkeypatch, headers, apply_email=None,
                                   application_url="https://www.linkedin.com/jobs/view/99")

    full_jd = ExtractedOpportunity(
        company_name="ReviewCo", role="Backend Intern", required_skills=["Python", "Kafka"], min_experience_years=7
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=full_jd))

    resp = client.post(
        f"/api/applications/{application_id}/recheck",
        json={"job_description": "Backend role. 7+ years of experience required. Python, Kafka."},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["eligibility"]["decision"] == "not_eligible"
    assert "Kafka" in body["skill_gap"]["missing"]
    # The posting link from the original alert is kept.
    assert body["application_url"] == "https://www.linkedin.com/jobs/view/99"


async def test_post_apply_status_tracking(client, monkeypatch):
    _uid, headers = _user(client, "status-track@example.com")
    application_id = _ingest_ready(client, monkeypatch, headers, apply_email=None,
                                   application_url="https://www.linkedin.com/jobs/view/5")

    # Can't record an interview for something not applied to yet.
    early = client.post(f"/api/applications/{application_id}/status", json={"stage": "INTERVIEW"}, headers=headers)
    assert early.status_code == 409

    client.post(f"/api/applications/{application_id}/review", json={"approve": True}, headers=headers)
    client.post(f"/api/applications/{application_id}/mark-applied", headers=headers)

    resp = client.post(
        f"/api/applications/{application_id}/status", json={"stage": "INTERVIEW", "note": "Round 1 on Monday"}, headers=headers
    )
    assert resp.status_code == 200
    last = resp.json()["status_history"][-1]
    assert last["stage"] == "INTERVIEW" and last["note"] == "Round 1 on Monday"

    bad = client.post(f"/api/applications/{application_id}/status", json={"stage": "DISCOVERED"}, headers=headers)
    assert bad.status_code == 422
