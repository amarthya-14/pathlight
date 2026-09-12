"""
End-to-end pipeline tests (Discovery -> persist -> Eligibility), with LLM calls faked
(this sandbox cannot reach Gemini). Verifies dedupe behavior, Application creation/reuse,
and the needs_human_review fallback when Discovery keeps failing.
"""
from beanie import PydanticObjectId

from app.agents.schemas import EligibilityDecision, ExtractedOpportunity
from app.graphs.opportunity_pipeline import run_opportunity_pipeline
from app.models.application import Application, ApplicationStage
from app.models.opportunity import Company, Opportunity
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
