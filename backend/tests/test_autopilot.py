"""Autopilot: daily, capped, only new matches, never applies."""
from app.agents.schemas import ExtractedOpportunity, TailoredResumeResult
from app.core.usage import DAILY_LIMITS
from app.models.application import Application, ApplicationStage
from app.workers.autopilot import run_autopilot_once
from tests.fakes import FakeLLM
from tests.test_jobs import RESUME, _install, _listing, _user

GOOD = [
    _listing(i, f"Backend Developer Intern {i}", f"Co{i}", desc="Python, Django, REST APIs, SQL, Git. Freshers welcome.")
    for i in range(1, 6)
]


class _DistinctDiscovery:
    """Each call extracts a different posting, like real Discovery on different listings."""

    def __init__(self):
        self.n = 0

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages):
        self.n += 1
        return ExtractedOpportunity(company_name=f"Co{self.n}", role="Backend Developer Intern", required_skills=["Python"])


def _fake_llms(monkeypatch):
    discovery = _DistinctDiscovery()
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: discovery)
    tailored = TailoredResumeResult(tailored_text=RESUME, cover_note="Dear Hiring Team,", confidence=0.8)
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: FakeLLM(canned_result=tailored))


async def test_autopilot_prepares_top_matches_once_a_day_and_never_applies(client, monkeypatch):
    _install(monkeypatch, GOOD)
    _fake_llms(monkeypatch)
    headers = _user(client, "auto@example.com")
    client.put("/api/profile", json={"experience_years": 0, "graduation_year": 2027, "target_roles": ["Backend Developer"],
                                     "autopilot_enabled": True, "autopilot_min_match": 60}, headers=headers)
    client.get("/api/jobs/feed", headers=headers)  # warms the listing cache

    first = await run_autopilot_once()
    second = await run_autopilot_once()

    assert list(first.values()) == [DAILY_LIMITS["autopilot"]]
    assert second == {}  # already ran today
    apps = await Application.find_all().to_list()
    assert len(apps) == DAILY_LIMITS["autopilot"]
    for app in apps:
        stages = [e.stage for e in app.status_history]
        assert ApplicationStage.APPLIED not in stages


async def test_autopilot_is_off_by_default(client, monkeypatch):
    _install(monkeypatch, GOOD)
    _fake_llms(monkeypatch)
    headers = _user(client, "manual@example.com")
    client.get("/api/jobs/feed", headers=headers)
    assert await run_autopilot_once() == {}
