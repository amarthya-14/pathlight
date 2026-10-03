"""Forwarded job alerts: address, Gmail confirmation, alert ingestion, privacy, auth."""
from email.message import EmailMessage

from app.agents.schemas import ExtractedOpportunities, ExtractedOpportunity, TailoredResumeResult
from app.models.inbound import InboundEmail
from app.models.opportunity import Opportunity
from tests.fakes import FakeLLM

SECRET = "inbound-secret-123"
DOMAIN = "alerts.example.com"
RESUME = "Asha Rao\nasha@example.com\nSkills\nPython, Django, SQL\nProjects\n• Built a Django app"


def _enable(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.INBOUND_EMAIL_DOMAIN", DOMAIN)
    monkeypatch.setattr("app.core.config.settings.INBOUND_WEBHOOK_SECRET", SECRET)


def _user(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123", "full_name": "Asha Rao"})
    token = client.post("/api/auth/login", data={"username": email, "password": "testpass123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.put("/api/profile", json={"cgpa": 8.5, "branch": "CSE", "experience_years": 0, "target_roles": ["Backend Developer"]}, headers=headers)
    client.post("/api/documents/paste", json={"doc_type": "resume", "title": "Resume", "text": RESUME}, headers=headers)
    return headers


def _mail(sender, to, subject, body, msg_id="<m1@mail>"):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Message-ID"] = sender, to, subject, msg_id
    m.set_content(body)
    return bytes(m)


def _post(client, raw, to=None, secret=SECRET):
    headers = {"X-Inbound-Secret": secret, "Content-Type": "message/rfc822"}
    if to:
        headers["X-Pathlight-To"] = to
    return client.post("/api/inbound/email", content=raw, headers=headers)


def test_address_is_private_stable_and_rotatable(client, monkeypatch):
    _enable(monkeypatch)
    headers = _user(client, "addr@example.com")
    first = client.get("/api/inbound/address", headers=headers).json()
    assert first["enabled"] and first["address"].endswith("@" + DOMAIN)
    assert client.get("/api/inbound/address", headers=headers).json()["address"] == first["address"]
    rotated = client.post("/api/inbound/address/rotate", headers=headers).json()
    assert rotated["address"] != first["address"]


def test_feature_off_without_configuration(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.INBOUND_EMAIL_DOMAIN", "")
    headers = _user(client, "off@example.com")
    assert client.get("/api/inbound/address", headers=headers).json() == {"enabled": False, "address": None, "activity": []}
    assert _post(client, b"x").status_code == 404


def test_webhook_requires_the_secret(client, monkeypatch):
    _enable(monkeypatch)
    assert _post(client, b"x", secret="wrong").status_code == 404


def test_gmail_confirmation_code_is_shown_to_the_student(client, monkeypatch):
    _enable(monkeypatch)
    headers = _user(client, "confirm@example.com")
    address = client.get("/api/inbound/address", headers=headers).json()["address"]
    body = (
        "asha@gmail.com has requested to automatically forward mail to your email address.\n"
        "Confirmation code: 123456789\n"
        "To allow asha@gmail.com to automatically forward mail, click the link below:\n"
        "https://mail-settings.google.com/mail/vf-%5BANGjdJ%5D-abc\n"
    )
    resp = _post(client, _mail("Gmail Team <forwarding-noreply@google.com>", address, "(#123456789) Gmail Forwarding Confirmation", body))
    assert resp.json()["status"] == "confirmation"
    activity = client.get("/api/inbound/address", headers=headers).json()["activity"][0]
    assert activity["confirmation_code"] == "123456789"
    assert activity["confirmation_link"].startswith("https://mail-settings.google.com/mail/")


async def test_forwarded_linkedin_alert_becomes_opportunities(client, monkeypatch):
    _enable(monkeypatch)
    digest = ExtractedOpportunities(opportunities=[
        ExtractedOpportunity(company_name="FwdCo", role="Python Developer Intern", application_url="https://www.linkedin.com/jobs/view/1"),
        ExtractedOpportunity(company_name="SalesCo", role="Key Account Manager"),
    ])
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=digest))
    tailored = TailoredResumeResult(tailored_text=RESUME, cover_note="Dear Hiring Team,", confidence=0.8)
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: FakeLLM(canned_result=tailored))
    headers = _user(client, "fwd@example.com")
    address = client.get("/api/inbound/address", headers=headers).json()["address"]

    raw = _mail("LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>", "asha@gmail.com", "2 new jobs for Backend Developer", "Python Developer Intern - FwdCo ...")
    resp = _post(client, raw, to=address)  # envelope recipient comes from the service

    assert resp.json()["status"] == "accepted"
    opp = await Opportunity.find_one(Opportunity.role == "Python Developer Intern")
    assert opp is not None and opp.source == "email_forward"
    activity = client.get("/api/inbound/address", headers=headers).json()["activity"][0]
    assert activity["status"] == "done" and activity["jobs_ingested"] == 1 and activity["skipped_not_relevant"] == 1

    assert _post(client, raw, to=address).json()["status"] == "duplicate"


async def test_non_alert_mail_is_ignored_and_not_stored(client, monkeypatch):
    _enable(monkeypatch)
    headers = _user(client, "private@example.com")
    address = client.get("/api/inbound/address", headers=headers).json()["address"]
    resp = _post(client, _mail("friend@gmail.com", address, "Personal: my bank details", "secret stuff", "<p1@mail>"))
    assert resp.json()["status"] == "ignored"
    stored = await InboundEmail.find_one(InboundEmail.kind == "ignored")
    assert stored.subject is None and stored.sender is None


def test_unknown_address_is_ignored_quietly(client, monkeypatch):
    _enable(monkeypatch)
    resp = _post(client, _mail("jobalerts-noreply@linkedin.com", f"nobody@{DOMAIN}", "jobs", "x"))
    assert resp.status_code == 202 and resp.json()["status"] == "ignored"
