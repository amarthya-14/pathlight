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
    assert resp.status_code == 202
    assert resp.json()["state"] == "running"
    # TestClient runs the background task before returning, so the outcome is recorded.
    status = client.get("/api/integrations/gmail/sync", headers=headers).json()
    assert status["state"] == "done"
    assert status["result"]["opportunities_ingested"] == 1

    apps = client.get("/api/applications", headers=headers).json()
    assert apps[0]["source"] == "gmail_mcp"
    assert apps[0]["application_url"] == "https://www.linkedin.com/jobs/view/987"


async def test_cron_poll_requires_secret(client, monkeypatch):
    configure_oauth(monkeypatch)
    FakeGoogle([gmail_message("c1", "Alert", "AlertCo is hiring...")]).install(monkeypatch)
    _fake_llms(monkeypatch)
    user_id, _headers = _user(client, "cron@example.com")
    await connect_gmail(user_id)

    # Disabled entirely when no secret is configured.
    assert client.post("/api/internal/gmail/poll").status_code == 404

    monkeypatch.setattr("app.core.config.settings.CRON_SECRET", "s3cret-value")
    assert client.post("/api/internal/gmail/poll", headers={"X-Cron-Secret": "wrong"}).status_code == 404

    resp = client.post("/api/internal/gmail/poll", headers={"X-Cron-Secret": "s3cret-value"})
    assert resp.status_code == 200
    assert resp.json() == {"users_polled": 1, "opportunities_ingested": 1, "autopilot_prepared": 0}


async def test_digest_email_becomes_one_opportunity_per_job(client, monkeypatch):
    from app.agents.schemas import ExtractedOpportunities

    configure_oauth(monkeypatch)
    FakeGoogle([gmail_message("d1", "3 new jobs for you", "Python Dev at A... Backend at B...")]).install(monkeypatch)
    _fake_llms(monkeypatch)
    digest = ExtractedOpportunities(
        opportunities=[
            ExtractedOpportunity(company_name="DigestA", role="Python Developer", application_url="https://x.com/a"),
            ExtractedOpportunity(company_name="DigestB", role="Backend Engineer", application_url="https://x.com/b"),
            ExtractedOpportunity(company_name="DigestA", role="Python Developer"),  # duplicate in same email
        ]
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=digest))
    user_id, _headers = _user(client, "digest@example.com")
    await connect_gmail(user_id)

    results = await poll_all_once()

    assert results[user_id].opportunities_ingested == 2
    roles = sorted(o.role for o in await Opportunity.find(Opportunity.source == "gmail_mcp").to_list())
    assert roles == ["Backend Engineer", "Python Developer"]


async def test_scheduled_poll_runs_once_a_day(client, monkeypatch):
    configure_oauth(monkeypatch)
    FakeGoogle([gmail_message("s1", "Alert", "AlertCo is hiring...")]).install(monkeypatch)
    _fake_llms(monkeypatch)
    user_id, _headers = _user(client, "daily@example.com")
    await connect_gmail(user_id)

    assert user_id in await poll_all_once(only_due=True)  # never polled -> due
    assert user_id not in await poll_all_once(only_due=True)  # polled moments ago -> not due


async def test_alert_jobs_outside_the_students_field_or_level_are_skipped(client, monkeypatch):
    from app.agents.schemas import ExtractedOpportunities

    configure_oauth(monkeypatch)
    FakeGoogle([gmail_message("f1", "New jobs", "...")]).install(monkeypatch)
    _fake_llms(monkeypatch)
    digest = ExtractedOpportunities(opportunities=[
        ExtractedOpportunity(company_name="Good", role="Python Developer Intern"),
        ExtractedOpportunity(company_name="Senior", role="Senior Python Engineer"),
        ExtractedOpportunity(company_name="Sales", role="Key Account Manager"),
    ])
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=digest))
    user_id, headers = _user(client, "fit@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE", "experience_years": 0,
                                     "target_roles": ["Backend Developer"]}, headers=headers)
    await connect_gmail(user_id)

    results = await poll_all_once()

    assert results[user_id].opportunities_ingested == 1
    assert results[user_id].skipped_not_relevant == 2
