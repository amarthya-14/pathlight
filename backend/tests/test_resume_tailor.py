"""
Gate 10: Resume Tailor Agent + its pipeline node. The headline test is the fabrication
regression (docs/AUTONOMOUS_APPLICATIONS.md §6/§9): an LLM that slips an absent skill
into the tailored resume must be rejected by code, not trusted because the prompt said so.
"""
from beanie import PydanticObjectId

from app.agents.resume_tailor import find_fabricated_skills, mentions_skill
from app.agents.schemas import ExtractedOpportunity, TailoredResumeResult
from app.graphs.opportunity_pipeline import run_opportunity_pipeline
from app.models.agent_execution import AgentExecution
from app.models.application import Application, ApplicationStage, ApplicationStatusEvent
from app.models.tailored_resume import TailoredResume
from tests.fakes import FakeLLM

BASE_RESUME = "Jane Doe\nSkills: Python, Django, SQL\nProject: Built a Django REST backend for a library."


def _tailored(text=BASE_RESUME, cover="Dear Hiring Team, I build Python backends.", emphasized=None, warnings=None):
    return TailoredResumeResult(
        tailored_text=text,
        cover_note=cover,
        changes_summary=["Moved Projects above Skills"],
        skills_emphasized=emphasized if emphasized is not None else ["Python", "Django"],
        confidence=0.8,
        warnings=warnings or [],
    )


def _setup_user(client, email, resume=BASE_RESUME, cgpa=9.0):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123"})
    login = client.post("/api/auth/login", data={"username": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    client.put("/api/profile", json={"cgpa": cgpa, "branch": "CSE"}, headers=headers)
    if resume:
        client.post(
            "/api/documents/paste", json={"doc_type": "resume", "title": "Resume", "text": resume}, headers=headers
        )
    return user_id, headers


def _discover(monkeypatch, **overrides):
    fields = {"company_name": "TailorCo", "role": "Backend Intern", "required_skills": ["Python", "Kubernetes"]}
    fields.update(overrides)
    monkeypatch.setattr(
        "app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=ExtractedOpportunity(**fields))
    )


# --- pure guard --------------------------------------------------------------------


def test_mentions_skill_handles_symbols_and_short_names():
    assert mentions_skill("Wrote C++ and Node.js services", "C++")
    assert mentions_skill("Wrote C++ and Node.js services", "node.js")
    assert not mentions_skill("Wrote Java services", "JavaScript")
    # 1-2 char skills are case-sensitive, so ordinary words don't count as mentions
    assert not mentions_skill("I go to great lengths", "Go")
    assert mentions_skill("Built a CLI in Go", "Go")


def test_guard_flags_absent_skill_added_to_text():
    result = _tailored(text=BASE_RESUME + "\nAlso experienced with Kubernetes.")
    assert find_fabricated_skills(BASE_RESUME, result, ["Python", "Kubernetes"]) == ["Kubernetes"]


def test_guard_flags_absent_skill_in_cover_note_or_emphasized_list():
    assert find_fabricated_skills(BASE_RESUME, _tailored(cover="I know Kubernetes well."), ["Kubernetes"]) == ["Kubernetes"]
    assert find_fabricated_skills(BASE_RESUME, _tailored(emphasized=["Kubernetes"]), ["Kubernetes"]) == ["Kubernetes"]


def test_guard_allows_rewording_of_existing_skills():
    reworded = "Jane Doe\nProject: Django REST backend (Python, SQL) for a library\nSkills: Python, Django, SQL"
    assert find_fabricated_skills(BASE_RESUME, _tailored(text=reworded), ["Python", "Django", "Kubernetes"]) == []


# --- pipeline node -----------------------------------------------------------------


async def test_pipeline_tailors_resume_and_marks_ready_to_apply(client, monkeypatch):
    user_id, _ = _setup_user(client, "tailor-ok@example.com")
    _discover(monkeypatch, apply_email="jobs@tailorco.dev")
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: FakeLLM(canned_result=_tailored()))

    result = await run_opportunity_pipeline("TailorCo hiring Backend Intern", "gmail_mcp", user_id)

    application = await Application.get(PydanticObjectId(result["application_id"]))
    assert application.status_history[-1].stage == ApplicationStage.READY_TO_APPLY

    tailored = await TailoredResume.find_one(TailoredResume.application_id == application.id)
    assert tailored.cover_note.startswith("Dear Hiring Team")
    # Deterministic warning for the required skill the resume lacks, even though the
    # (fake) LLM didn't add one itself.
    assert any("Kubernetes" in w for w in tailored.warnings)


async def test_fabricating_llm_is_rejected_and_application_not_ready(client, monkeypatch):
    """REGRESSION: a resume that explicitly lacks Kubernetes must never come out of the
    tailor claiming Kubernetes, no matter what the LLM returns."""
    user_id, _ = _setup_user(client, "tailor-fabricate@example.com")
    _discover(monkeypatch)
    fabricated = _tailored(text=BASE_RESUME + "\nSkills: Kubernetes (2 years)", emphasized=["Python", "Kubernetes"])
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: FakeLLM(canned_result=fabricated))

    result = await run_opportunity_pipeline("TailorCo hiring Backend Intern", "manual", user_id)

    assert "could not be generated" in result["resume_tailor_note"]
    application = await Application.get(PydanticObjectId(result["application_id"]))
    assert ApplicationStage.READY_TO_APPLY not in [e.stage for e in application.status_history]
    assert await TailoredResume.find_one(TailoredResume.application_id == application.id) is None

    execution = await AgentExecution.find_one(AgentExecution.agent_name == "resume_tailor")
    assert execution.status == "error"
    assert "fabrication_guard" in execution.error_message


async def test_no_resume_is_a_noop_with_note(client, monkeypatch):
    user_id, _ = _setup_user(client, "tailor-noresume@example.com", resume=None)
    _discover(monkeypatch)

    def _fail():
        raise AssertionError("tailor must not call the LLM without a resume")

    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", _fail)

    result = await run_opportunity_pipeline("TailorCo hiring Backend Intern", "manual", user_id)
    assert "No resume on file" in result["resume_tailor_note"]
    assert "tailored_resume" not in result


async def test_not_eligible_is_not_tailored(client, monkeypatch):
    user_id, _ = _setup_user(client, "tailor-ineligible@example.com", cgpa=6.0)
    _discover(monkeypatch, min_cgpa=8.0)

    def _fail():
        raise AssertionError("tailor must not run for a NOT_ELIGIBLE opportunity")

    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", _fail)

    result = await run_opportunity_pipeline("TailorCo hiring Backend Intern", "manual", user_id)
    assert result["eligibility"].decision == "not_eligible"
    assert "tailored_resume" not in result


async def test_reingesting_an_already_applied_posting_never_reopens_review(client, monkeypatch):
    user_id, _ = _setup_user(client, "tailor-reingest@example.com")
    _discover(monkeypatch)
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: FakeLLM(canned_result=_tailored()))

    first = await run_opportunity_pipeline("TailorCo hiring Backend Intern", "gmail_mcp", user_id)
    application = await Application.get(PydanticObjectId(first["application_id"]))
    application.status_history.append(ApplicationStatusEvent(stage=ApplicationStage.APPLIED))
    await application.save()

    await run_opportunity_pipeline("TailorCo hiring Backend Intern (digest again)", "gmail_mcp", user_id)

    application = await Application.get(PydanticObjectId(first["application_id"]))
    stages = [e.stage for e in application.status_history]
    assert stages.count(ApplicationStage.READY_TO_APPLY) == 1
    assert ApplicationStage.READY_TO_APPLY not in stages[stages.index(ApplicationStage.APPLIED):]


async def test_llm_warning_in_its_own_words_is_not_duplicated(client, monkeypatch):
    """Found in a real Gemini run: the LLM's own warning ("Posting requires Kubernetes —
    not on your resume; not added.") is worded differently from the deterministic one,
    so exact-text dedupe produced two warnings for one skill."""
    user_id, _ = _setup_user(client, "tailor-warn-dedupe@example.com")
    _discover(monkeypatch)
    llm_result = _tailored(warnings=["Posting requires Kubernetes — not on your resume; not added."])
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: FakeLLM(canned_result=llm_result))

    result = await run_opportunity_pipeline("TailorCo hiring Backend Intern", "manual", user_id)

    warnings = result["tailored_resume"].warnings
    assert sum("Kubernetes" in w for w in warnings) == 1
