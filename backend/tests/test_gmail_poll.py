"""
Gate 10: Gmail job-alert poller (app/workers/gmail_poll.py) + POST /api/integrations/gmail/sync.
End to end through the real pipeline with faked Gmail + faked LLMs: an alert email
becomes an Opportunity with source=gmail_mcp, a tailored resume, and READY_TO_APPLY —
and nothing is ever sent.
"""
from beanie import PydanticObjectId

from app.agents.schemas import ExtractedOpportunity, TailoredResumeResult
from app.models.application import Application, ApplicationStage
from app.models.integration import Integration
from app.models.opportunity import Opportunity
from app.workers.gmail_poll import build_alert_query, poll_all_once
from tests.fakes import FakeLLM
from tests.gmail_fakes import FakeGoogle, configure_oauth, connect_gmail, gmail_message

RESUME = "Ana Roy\nSkills: Python, Django\nProject: Django marketplace."


def _user(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123"})
    login = client.post("/api/auth/login", data={"username": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)
    client.post("/api/documents/paste", json={"doc_type": "resume", "title": "Resume", "text": RESUME}, headers=headers)
    return user_id, headers


def _fake_llms(monkeypatch):
    extracted = ExtractedOpportunity(
        company_name="AlertCo",
        role="Python Developer Intern",
        required_skills=["Python"],
        application_url="https://www.linkedin.com/jobs/view/987",
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))
    tailored = TailoredResumeResult(
        tailored_text=RESUME, cover_note="Dear Hiring Team, ...", skills_emphasized=["Python"], confidence=0.7
    )
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: FakeLLM(canned_result=tailored))


def test_alert_query_only_targets_allowlisted_senders():
    query = build_alert_query(first_poll=True)
    assert query.startswith("from:(")
    assert "jobalerts-noreply@linkedin.com" in query
    assert "newer_than:" in query


async def test_poll_ingests_alert_to_ready_to_apply_and_never_sends(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle([gmail_message("m1", "Python Developer Intern at AlertCo", "AlertCo is hiring...")]).install(
        monkeypatch
    )
    _fake_llms(monkeypatch)
    user_id, _headers = _user(client, "poll-user@example.com")
    await connect_gmail(user_id)

    results = await poll_all_once()

    assert results[user_id].opportunities_ingested == 1
    opportunity = await Opportunity.find_one(Opportunity.role == "Python Developer Intern")
    assert opportunity.source == "gmail_mcp"
    application = await Application.find_one(Application.user_id == PydanticObjectId(user_id))
    assert application.status_history[-1].stage == ApplicationStage.READY_TO_APPLY
    assert google.sent == []

    integration = await Integration.find_one(Integration.user_id == PydanticObjectId(user_id))
    assert integration.processed_message_ids == ["m1"]
    assert integration.last_polled_at is not None


async def test_poll_does_not_reprocess_seen_messages(client, monkeypatch):
    configure_oauth(monkeypatch)
    FakeGoogle([gmail_message("m1", "Alert", "AlertCo is hiring...")]).install(monkeypatch)
    _fake_llms(monkeypatch)
    user_id, _headers = _user(client, "poll-dedupe@example.com")
    await connect_gmail(user_id)

    await poll_all_once()
    second = await poll_all_once()

    assert second[user_id].opportunities_ingested == 0
    assert second[user_id].skipped_already_processed == 1


async def test_sync_route_runs_poll_for_current_user(client, monkeypatch):
    configure_oauth(monkeypatch)
    FakeGoogle([gmail_message("m9", "Alert", "AlertCo is hiring...")]).install(monkeypatch)
    _fake_llms(monkeypatch)
    user_id, headers = _user(client, "poll-sync@example.com")

    assert client.post("/api/integrations/gmail/sync", headers=headers).status_code == 409

    await connect_gmail(user_id)
    resp = client.post("/api/integrations/gmail/sync", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["opportunities_ingested"] == 1

    apps = client.get("/api/applications", headers=headers).json()
    assert apps[0]["source"] == "gmail_mcp"
    assert apps[0]["application_url"] == "https://www.linkedin.com/jobs/view/987"
