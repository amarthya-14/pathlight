"""
End-to-end pipeline tests (Discovery -> persist -> Eligibility -> Skill Gap -> Planner),
with LLM calls faked (this sandbox cannot reach Gemini). Verifies dedupe behavior,
Application creation/reuse, and the needs_human_review fallback when Discovery keeps
failing.
"""
import httpx
from beanie import PydanticObjectId

from app.agents.schemas import EligibilityDecision, ExtractedOpportunity
from app.graphs.opportunity_pipeline import run_opportunity_pipeline
from app.models.application import Application, ApplicationStage
from app.models.calendar_event import CalendarEvent
from app.models.opportunity import Company, Opportunity
from app.models.preparation import PreparationPlan
from tests.fakes import FakeLLM


def _register_and_get_user_id(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123"})
    login = client.post("/api/auth/login", data={"username": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    return user_id, headers


async def test_pipeline_creates_company_opportunity_application(client, monkeypatch):
    user_id, headers = _register_and_get_user_id(client, "pipeline-user@example.com")
    client.put("/api/profile", json={"cgpa": 8.5, "branch": "CSE"}, headers=headers)

    extracted = ExtractedOpportunity(
        company_name="Acme Corp", role="Backend Intern", min_cgpa=7.0, allowed_branches=["CSE"]
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))

    def _fail(*a, **k):
        raise AssertionError("Should not call LLM for deterministic eligibility")

    monkeypatch.setattr("app.agents.eligibility.get_strong_llm", _fail)

    result = await run_opportunity_pipeline("Acme Corp is hiring a Backend Intern...", "manual", user_id)

    assert not result.get("needs_human_review")
    assert result["eligibility"].decision == EligibilityDecision.ELIGIBLE

    company = await Company.find_one(Company.name == "Acme Corp")
    assert company is not None

    opportunity = await Opportunity.get(PydanticObjectId(result["opportunity_id"]))
    assert opportunity.role == "Backend Intern"
    assert opportunity.requirements.min_cgpa == 7.0

    application = await Application.get(PydanticObjectId(result["application_id"]))
    assert application.eligibility.decision == EligibilityDecision.ELIGIBLE
    stages = [e.stage for e in application.status_history]
    assert ApplicationStage.DISCOVERED in stages
    assert ApplicationStage.ELIGIBILITY_CHECKED in stages


async def test_pipeline_dedupes_same_opportunity_reingested(client, monkeypatch):
    user_id, headers = _register_and_get_user_id(client, "dedupe-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)

    extracted = ExtractedOpportunity(company_name="DedupeCo", role="SWE Intern")
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))

    result1 = await run_opportunity_pipeline("DedupeCo hiring SWE Intern", "manual", user_id)
    result2 = await run_opportunity_pipeline("DedupeCo is hiring for a SWE Intern role again", "manual", user_id)

    assert result1["opportunity_id"] == result2["opportunity_id"]
    assert result1["application_id"] == result2["application_id"]

    opportunities = await Opportunity.find(Opportunity.role == "SWE Intern").to_list()
    assert len(opportunities) == 1


async def test_pipeline_routes_to_needs_human_review_on_repeated_discovery_failure(client, monkeypatch):
    user_id, _headers = _register_and_get_user_id(client, "fail-user@example.com")

    monkeypatch.setattr(
        "app.agents.discovery.get_small_llm", lambda: FakeLLM(raise_exc=RuntimeError("Gemini down"))
    )

    result = await run_opportunity_pipeline("some raw text", "manual", user_id)

    assert result.get("needs_human_review") is True
    assert "error" in result
    # opportunity_id must not be set -- the pipeline gave up before persisting anything
    assert "opportunity_id" not in result


async def test_pipeline_runs_skill_gap_with_resume_on_file(client, monkeypatch):
    user_id, headers = _register_and_get_user_id(client, "skillgap-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)
    client.post(
        "/api/documents/paste",
        json={"doc_type": "resume", "title": "My Resume", "text": "Experienced with Python."},
        headers=headers,
    )

    extracted = ExtractedOpportunity(
        company_name="SkillGapCo", role="Backend Intern", required_skills=["Python", "AWS"]
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))

    result = await run_opportunity_pipeline("SkillGapCo hiring Backend Intern", "manual", user_id)

    assert result["skill_gap"].matched == ["Python"]
    assert result["skill_gap"].missing == ["AWS"]
    assert result.get("skill_gap_note") is None

    application = await Application.get(PydanticObjectId(result["application_id"]))
    assert application.skill_gap.matched == ["Python"]


async def test_pipeline_skill_gap_notes_missing_resume(client, monkeypatch):
    user_id, headers = _register_and_get_user_id(client, "noresume-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)
    # deliberately no resume uploaded

    extracted = ExtractedOpportunity(company_name="NoResumeCo", role="Intern", required_skills=["Python"])
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))

    result = await run_opportunity_pipeline("NoResumeCo hiring Intern", "manual", user_id)

    assert result["skill_gap"].missing == ["Python"]
    assert "No resume on file" in result["skill_gap_note"]


async def test_pipeline_skips_skill_gap_when_no_skills_extracted(client, monkeypatch):
    user_id, headers = _register_and_get_user_id(client, "noskills-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)

    extracted = ExtractedOpportunity(company_name="NoSkillsCo", role="Intern")  # no skills at all
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))

    result = await run_opportunity_pipeline("NoSkillsCo hiring Intern", "manual", user_id)

    assert "skill_gap" not in result
    assert "skill_gap_note" not in result
    assert "preparation_plan" not in result


async def test_pipeline_generates_plan_and_calendar_reminder_when_deadline_present(client, monkeypatch):
    user_id, headers = _register_and_get_user_id(client, "planner-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)

    extracted = ExtractedOpportunity(
        company_name="PlannerCo",
        role="Backend Intern",
        deadline="2027-06-01T00:00:00",
        required_skills=["Python", "Django"],
    )
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))

    result = await run_opportunity_pipeline("PlannerCo hiring Backend Intern", "manual", user_id)

    plan = result["preparation_plan"]
    assert plan.total_estimated_hours > 0
    assert {t.skill for t in plan.tasks} == {"Python", "Django"}
    assert plan.available_hours is not None
    assert plan.feasible is not None

    stored_plan = await PreparationPlan.find_one(
        PreparationPlan.application_id == PydanticObjectId(result["application_id"])
    )
    assert stored_plan is not None

    application = await Application.get(PydanticObjectId(result["application_id"]))
    assert ApplicationStage.PREPARING in [e.stage for e in application.status_history]

    reminder = await CalendarEvent.find_one(CalendarEvent.user_id == PydanticObjectId(user_id))
    assert reminder is not None
    assert reminder.title == "Application deadline: Backend Intern"
    assert reminder.application_id == PydanticObjectId(result["application_id"])


async def test_pipeline_planner_noop_when_all_skills_matched(client, monkeypatch):
    user_id, headers = _register_and_get_user_id(client, "allmatched-user@example.com")
    client.put("/api/profile", json={"cgpa": 9.0, "branch": "CSE"}, headers=headers)
    client.post(
        "/api/documents/paste",
        json={"doc_type": "resume", "title": "Resume", "text": "Experienced with Python."},
        headers=headers,
    )

    extracted = ExtractedOpportunity(company_name="MatchedCo", role="Intern", required_skills=["Python"])
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))

    result = await run_opportunity_pipeline("MatchedCo hiring Intern", "manual", user_id)

    assert result["skill_gap"].matched == ["Python"]
    assert "preparation_plan" not in result


async def test_pipeline_passes_profile_github_username_to_skill_gap(client, monkeypatch):
    async def _fake_get(self, url, params=None, headers=None):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            json=[{"name": "aws-demo", "description": "", "language": "Python", "topics": ["aws"]}],
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    user_id, headers = _register_and_get_user_id(client, "githubprofile-user@example.com")
    client.put(
        "/api/profile",
        json={"cgpa": 9.0, "branch": "CSE", "github_username": "octocat"},
        headers=headers,
    )

    extracted = ExtractedOpportunity(company_name="GithubCo", role="Intern", required_skills=["AWS"])
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))

    result = await run_opportunity_pipeline("GithubCo hiring Intern", "manual", user_id)

    assert result["skill_gap"].github_evidence.get("AWS") == ["aws-demo (Python)"]
