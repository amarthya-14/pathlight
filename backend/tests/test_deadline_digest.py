"""
Deadline digest (app/core/deadlines.py, app/workers/deadline_reminders.py): one drive
arriving from several channels is one entry with one deadline, IST deadlines are read as
IST, and reminders go out once, 24h and 3h before, only while the student still has to act.
"""
from datetime import datetime, timedelta, timezone

from beanie import PydanticObjectId

from app.agents.discovery import system_prompt
from app.agents.schemas import ExtractedOpportunity
from app.core.deadlines import (
    IST,
    is_open,
    looks_like_whatsapp,
    merge_deadline,
    normalize_deadline,
    reminder_due,
    reminder_key,
)
from app.graphs.opportunity_pipeline import run_opportunity_pipeline
from app.models.application import Application, ApplicationStage, ApplicationStatusEvent
from app.models.user import Profile
from app.workers.deadline_reminders import run_deadline_reminders_once
from tests.fakes import FakeLLM

NOW = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)  # 11:30 IST


# ── Rules ────────────────────────────────────────────────────────────────────────────

def test_deadline_without_time_zone_is_indian_time():
    assert normalize_deadline(datetime(2026, 10, 25, 17, 0)) == datetime(2026, 10, 25, 11, 30, tzinfo=timezone.utc)
    utc = datetime(2026, 10, 25, 11, 30, tzinfo=timezone.utc)
    assert normalize_deadline(utc) == utc
    assert normalize_deadline(None) is None


def test_merge_keeps_the_earlier_deadline_unless_it_has_passed():
    early, late = NOW + timedelta(days=1), NOW + timedelta(days=3)
    assert merge_deadline(None, early, NOW) == early
    assert merge_deadline(late, None, NOW) == late
    assert merge_deadline(late, early, NOW) == early
    assert merge_deadline(early, late, NOW) == early
    # A notice with a later date for a drive that already closed: extended or reopened.
    passed = NOW - timedelta(hours=2)
    assert merge_deadline(passed, late, NOW) == late
    assert merge_deadline(passed, NOW - timedelta(days=1), NOW) == NOW - timedelta(days=1)


def test_reminders_fire_once_per_window():
    assert reminder_due(NOW + timedelta(hours=30), [], NOW) is None
    deadline = NOW + timedelta(hours=20)
    assert reminder_due(deadline, [], NOW) == "24h"
    assert reminder_due(deadline, [reminder_key("24h", deadline)], NOW) is None
    # Found late: only the tightest window, not both.
    assert reminder_due(NOW + timedelta(hours=2), [], NOW) == "3h"
    assert reminder_due(NOW - timedelta(minutes=1), [], NOW) is None
    # A changed deadline re-arms its reminders.
    assert reminder_due(deadline + timedelta(hours=1), [reminder_key("24h", deadline)], NOW) == "24h"


def test_only_open_applications_need_the_deadline():
    assert is_open(["DISCOVERED", "ELIGIBILITY_CHECKED", "READY_TO_APPLY"])
    assert is_open(["READY_TO_APPLY", "MANUAL_APPLY_REQUIRED"])  # approved, still has to apply by hand
    assert not is_open(["READY_TO_APPLY", "APPLIED"])
    assert not is_open(["READY_TO_APPLY", "SKIPPED_BY_USER"])


def test_whatsapp_copies_are_recognised():
    assert looks_like_whatsapp("[20/10/26, 4:05 pm] TPO Sir: Infosys drive, register by tomorrow 5 PM")
    assert looks_like_whatsapp("20/10/2026, 16:05 - Placement Cell: TCS Ninja registrations open")
    assert not looks_like_whatsapp("Acme is hiring. Apply by 30/10/2026: send your resume to jobs@acme.dev")


def test_discovery_prompt_knows_today():
    today = datetime.now(IST).strftime("%d %B %Y")
    assert today in system_prompt()
    assert "+05:30" in system_prompt()


# ── Pipeline ─────────────────────────────────────────────────────────────────────────

def _user(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123"})
    login = client.post("/api/auth/login", data={"username": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return client.get("/api/auth/me", headers=headers).json()["id"], headers


def _drive(deadline=None):
    return ExtractedOpportunity(company_name="Infosys", role="Systems Engineer", deadline=deadline)


async def test_one_drive_from_three_channels_is_one_entry(client):
    user_id, headers = _user(client, "digest@example.com")
    future = datetime.now(IST).replace(microsecond=0) + timedelta(days=3)
    naive_5pm = future.replace(hour=17, minute=0, second=0, tzinfo=None)

    first = await run_opportunity_pipeline("Infosys SE alert", "gmail_mcp", user_id, extraction=_drive())
    second = await run_opportunity_pipeline("[..] TPO: Infosys", "whatsapp", user_id, extraction=_drive(naive_5pm))
    third = await run_opportunity_pipeline(
        "T&P email", "email_forward", user_id, extraction=_drive(naive_5pm + timedelta(days=2))
    )

    assert first["application_id"] == second["application_id"] == third["application_id"]
    application = await Application.get(PydanticObjectId(first["application_id"]))
    assert application.sources == ["gmail_mcp", "whatsapp", "email_forward"]
    # 5 PM IST, and the earlier of the two dates.
    assert application.deadline == naive_5pm.replace(tzinfo=IST).astimezone(timezone.utc)

    out = client.get(f"/api/applications/{first['application_id']}", headers=headers).json()
    assert out["sources"] == ["gmail_mcp", "whatsapp", "email_forward"]
    assert datetime.fromisoformat(out["deadline"]) == application.deadline


async def test_each_student_keeps_their_own_deadline(client):
    # Same company and role at two colleges: one shared posting, two different dates.
    a_id, a_headers = _user(client, "college-a@example.com")
    b_id, b_headers = _user(client, "college-b@example.com")
    soon, later = NOW + timedelta(days=400), NOW + timedelta(days=403)
    a = await run_opportunity_pipeline("A", "manual", a_id, extraction=_drive(soon))
    b = await run_opportunity_pipeline("B", "manual", b_id, extraction=_drive(later))

    assert a["opportunity_id"] == b["opportunity_id"]
    a_out = client.get(f"/api/applications/{a['application_id']}", headers=a_headers).json()
    b_out = client.get(f"/api/applications/{b['application_id']}", headers=b_headers).json()
    assert datetime.fromisoformat(a_out["deadline"]) == soon
    assert datetime.fromisoformat(b_out["deadline"]) == later


def test_pasted_whatsapp_message_is_tagged(client, monkeypatch):
    _user_id, headers = _user(client, "paste@example.com")
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=_drive()))
    resp = client.post(
        "/api/opportunities/ingest",
        json={"raw_text": "[20/10/26, 4:05 pm] TPO Sir: Infosys SE drive, register by 25 Oct", "source": "manual"},
        headers=headers,
    )
    assert resp.status_code == 200
    out = client.get(f"/api/applications/{resp.json()['application_id']}", headers=headers).json()
    assert out["sources"] == ["whatsapp"]


async def test_closing_soon_leaves_out_what_is_already_applied(client):
    user_id, headers = _user(client, "closing@example.com")
    soon = datetime.now(timezone.utc) + timedelta(days=2)
    open_one = await run_opportunity_pipeline(
        "x", "manual", user_id, extraction=ExtractedOpportunity(company_name="OpenCo", role="SDE", deadline=soon)
    )
    applied = await run_opportunity_pipeline(
        "y", "manual", user_id, extraction=ExtractedOpportunity(company_name="DoneCo", role="SDE", deadline=soon)
    )
    application = await Application.get(PydanticObjectId(applied["application_id"]))
    application.status_history.append(ApplicationStatusEvent(stage=ApplicationStage.APPLIED))
    await application.save()

    urgent = client.get("/api/dashboard/home", headers=headers).json()["urgent_deadlines"]
    assert [a["id"] for a in urgent] == [open_one["application_id"]]


# ── Reminder emails ──────────────────────────────────────────────────────────────────

class _Outbox:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    async def __call__(self, to, subject, body):
        if self.fail:
            raise OSError("SMTP down")
        self.sent.append((to, subject, body))


def _mail(monkeypatch, fail=False):
    monkeypatch.setattr("app.core.config.settings.SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr("app.core.config.settings.SMTP_FROM", "Pathlight <noreply@example.com>")
    outbox = _Outbox(fail)
    monkeypatch.setattr("app.workers.deadline_reminders.send_mail", outbox)
    return outbox


async def test_reminders_24h_then_3h_then_nothing(client, monkeypatch):
    outbox = _mail(monkeypatch)
    user_id, _ = _user(client, "remind@example.com")
    deadline = NOW + timedelta(hours=20)
    await run_opportunity_pipeline(
        "x", "manual", user_id,
        extraction=ExtractedOpportunity(
            company_name="Infosys", role="Systems Engineer", deadline=deadline, application_url="https://infy.example/apply"
        ),
    )

    assert await run_deadline_reminders_once(NOW) == 1
    to, subject, body = outbox.sent[0]
    assert to == "remind@example.com"
    assert subject == "Closes in 20 hours: Systems Engineer at Infosys"
    assert "Closes Fri 23 Oct, 07:30 AM IST" in body
    assert "https://infy.example/apply" in body

    assert await run_deadline_reminders_once(NOW + timedelta(minutes=30)) == 0  # already sent
    assert await run_deadline_reminders_once(NOW + timedelta(hours=18)) == 1  # 2h left
    assert outbox.sent[1][1] == "Closes in 2 hours: Systems Engineer at Infosys"
    assert await run_deadline_reminders_once(NOW + timedelta(hours=19)) == 0


async def test_one_email_lists_everything_closing(client, monkeypatch):
    outbox = _mail(monkeypatch)
    user_id, _ = _user(client, "several@example.com")
    for company, hours in (("TCS", 10), ("Wipro", 2)):
        await run_opportunity_pipeline(
            "x", "manual", user_id,
            extraction=ExtractedOpportunity(company_name=company, role="Engineer", deadline=NOW + timedelta(hours=hours)),
        )
    assert await run_deadline_reminders_once(NOW) == 1
    _to, subject, body = outbox.sent[0]
    assert subject == "2 applications close soon, the first in 2 hours"
    assert body.index("Wipro") < body.index("TCS")


async def test_no_reminder_when_applied_or_turned_off(client, monkeypatch):
    outbox = _mail(monkeypatch)
    applied_id, _ = _user(client, "applied@example.com")
    off_id, off_headers = _user(client, "off@example.com")
    for user_id in (applied_id, off_id):
        await run_opportunity_pipeline("x", "manual", user_id, extraction=_drive(NOW + timedelta(hours=5)))

    application = await Application.find_one(Application.user_id == PydanticObjectId(applied_id))
    application.status_history.append(ApplicationStatusEvent(stage=ApplicationStage.APPLIED))
    await application.save()
    resp = client.put("/api/profile", json={"deadline_reminders": False}, headers=off_headers)
    assert resp.status_code == 200 and resp.json()["deadline_reminders"] is False
    assert (await Profile.find_one(Profile.user_id == PydanticObjectId(off_id))).deadline_reminders is False

    assert await run_deadline_reminders_once(NOW) == 0
    assert outbox.sent == []


async def test_failed_send_is_retried_next_run(client, monkeypatch):
    _mail(monkeypatch, fail=True)
    user_id, _ = _user(client, "retry@example.com")
    await run_opportunity_pipeline("x", "manual", user_id, extraction=_drive(NOW + timedelta(hours=20)))

    assert await run_deadline_reminders_once(NOW) == 0
    application = await Application.find_one(Application.user_id == PydanticObjectId(user_id))
    assert application.reminders_sent == []  # released, not lost

    outbox = _mail(monkeypatch)
    assert await run_deadline_reminders_once(NOW + timedelta(hours=1)) == 1
    assert len(outbox.sent) == 1


async def test_without_smtp_nothing_is_marked_sent(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.SMTP_HOST", "")
    user_id, _ = _user(client, "nosmtp@example.com")
    await run_opportunity_pipeline("x", "manual", user_id, extraction=_drive(NOW + timedelta(hours=20)))
    assert await run_deadline_reminders_once(NOW) == 0
    application = await Application.find_one(Application.user_id == PydanticObjectId(user_id))
    assert application.reminders_sent == []


async def test_a_reminder_can_be_claimed_only_once(client):
    # The worker loop and the hourly cron can run at the same moment; only one may send.
    from app.workers.deadline_reminders import _claim

    user_id, _ = _user(client, "race@example.com")
    result = await run_opportunity_pipeline("x", "manual", user_id, extraction=_drive(NOW + timedelta(hours=20)))
    application_id = PydanticObjectId(result["application_id"])
    key = reminder_key("24h", NOW + timedelta(hours=20))
    assert await _claim(application_id, key) is True
    assert await _claim(application_id, key) is False
