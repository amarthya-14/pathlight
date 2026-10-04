"""Jobs feed (job boards) — sources are faked; signals, matching, caching and tracking are real."""
from datetime import datetime, timedelta, timezone

from app.agents.schemas import ExtractedOpportunity, TailoredResumeResult
from app.models.job_listing import JobListing
from app.models.opportunity import Opportunity
from app.sources.job_boards import dedupe, html_to_text, relevant
from app.sources.job_signals import batch_years, classify_title, job_type, min_experience, user_families
from tests.fakes import FakeLLM

RESUME = "Asha Rao\nasha@example.com\nSkills\nPython, Django, SQL, React, REST APIs, Git\nProjects\n• Built a Django app"
NOW = datetime.now(timezone.utc)


def _listing(i, title, company, location="Bengaluru, India", remote=False, desc="Python Django REST APIs SQL", days_ago=3):
    return {
        "source": "greenhouse", "external_id": f"x:{i}", "title": title, "company": company,
        "location": location, "remote": remote, "url": f"https://jobs.example.com/{i}",
        "description": desc, "tags": [], "posted_at": NOW - timedelta(days=days_ago),
    }


FAKE_LISTINGS = [
    _listing(1, "Senior Backend Engineer", "BigCo", desc="5+ years of experience with Python and Django"),
    _listing(2, "Software Engineer Intern - Backend", "StartCo", desc="Python, Django, REST APIs, SQL. Freshers welcome."),
    _listing(3, "Data Analyst", "NumbersCo", desc="Excel Tableau statistics"),
    _listing(4, "Backend Developer", "OldCo", desc="Python Django SQL", days_ago=80),
    _listing(5, "Graduate Engineer Trainee", "BatchCo", desc="Open to 2025 batch graduates. Python, SQL, Django"),
    _listing(6, "Video Editor Intern", "MediaCo", desc="Premiere Pro"),
    _listing(7, "Backend Engineer", "MidCo", desc="2-4 years of experience in Python, Django, SQL"),
]


def _install(monkeypatch, listings=FAKE_LISTINGS):
    calls = []

    async def fake_fetch_all(queries=None):
        calls.append(queries)
        return [dict(l) for l in listings], {"fake": f"ok ({len(listings)})"}

    monkeypatch.setattr("app.api.routes.jobs.fetch_all", fake_fetch_all)
    return calls


def _user(client, email="jobs@example.com", profile=None):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123", "full_name": "Asha Rao"})
    token = client.post("/api/auth/login", data={"username": email, "password": "testpass123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/api/profile",
        json=profile or {"cgpa": 8.5, "branch": "CSE", "experience_years": 0, "graduation_year": 2027,
                         "target_roles": ["Backend Developer"]},
        headers=headers,
    )
    client.post("/api/documents/paste", json={"doc_type": "resume", "title": "Resume", "text": RESUME}, headers=headers)
    return headers


# ── signals ──────────────────────────────────────────────────────────────────

def test_titles_are_classified_into_fields():
    assert classify_title("Software Engineer Intern - Backend") == "backend"
    assert classify_title("Software Engineer, Sales Tools") == "software"  # engineering beats "sales"
    assert classify_title("Key Account Manager") == "non_tech"
    assert classify_title("Video Editor Intern") == "non_tech"
    assert classify_title("Machine Learning Engineer") == "ml_ai"
    assert classify_title("Data Analyst") == "data_analyst"


def test_experience_and_batch_are_read_from_descriptions():
    assert min_experience("We need 3+ years of experience in Java") == 3
    assert min_experience("Experience: 2-4 years") == 2
    assert min_experience("Minimum 5 years in backend") == 5
    assert min_experience("A 10 year old company. Great culture.") is None
    assert batch_years("Eligible: 2025/2026 batch") == [2025, 2026]


def test_student_field_comes_from_roles_and_resume():
    assert {"backend", "software"} <= user_families([], ["Python", "Django", "REST APIs", "SQL"])
    assert "ml_ai" in user_families(["AI Engineer"], [])


def test_html_to_text_unescapes_greenhouse_double_encoding():
    assert html_to_text("&lt;p&gt;Hello&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;") == "Hello\n\n• Python"


def test_relevance_keeps_india_and_open_remote_tech_roles_only():
    assert relevant(_listing(1, "Backend Engineer", "A"))
    assert relevant(_listing(2, "Software Engineer", "A", location="Worldwide", remote=True))
    assert not relevant(_listing(3, "Software Engineer", "A", location="USA", remote=True))
    assert not relevant(_listing(4, "Account Executive", "A"))


def test_same_role_in_several_cities_is_one_listing():
    rows = dedupe([_listing(1, "SDE Intern", "Acme", "Pune, India"), _listing(2, "SDE Intern", "Acme", "Hyderabad, India")])
    assert len(rows) == 1 and "Pune" in rows[0]["location"] and "Hyderabad" in rows[0]["location"]


# ── feed ─────────────────────────────────────────────────────────────────────

async def test_feed_shows_only_relevant_recent_entry_level_matches(client, monkeypatch):
    calls = _install(monkeypatch)
    headers = _user(client)

    feed = client.get("/api/jobs/feed", headers=headers).json()

    assert len(calls) == 1
    assert "Backend Developer" in calls[0]  # students' target roles are searched on aggregators
    titles = [i["title"] for i in feed["items"]]
    assert titles == ["Software Engineer Intern - Backend"]
    top = feed["items"][0]
    assert top["match"] >= 60 and "Entry-level" in top["reasons"]
    assert feed["hidden"]["experience"] == 2  # senior title + "2-4 years"
    assert feed["hidden"]["field"] == 2  # data analyst, video editor
    assert feed["hidden"]["old"] == 1
    assert feed["hidden"]["batch"] == 1  # 2025 batch, student is 2027

    client.get("/api/jobs/feed", headers=headers)
    assert len(calls) == 1  # fresh cache -> no refetch


async def test_filters_can_be_loosened(client, monkeypatch):
    _install(monkeypatch)
    headers = _user(client, "loose@example.com")
    feed = client.get("/api/jobs/feed?days=90&include_experienced=true&min_match=0", headers=headers).json()
    titles = {i["title"] for i in feed["items"]}
    assert {"Backend Developer", "Backend Engineer", "Senior Backend Engineer"} <= titles
    assert "Video Editor Intern" not in titles  # field is never loosened


async def test_dismissed_jobs_stay_hidden(client, monkeypatch):
    _install(monkeypatch)
    headers = _user(client, "dismiss@example.com")
    item = client.get("/api/jobs/feed", headers=headers).json()["items"][0]
    assert client.post(f"/api/jobs/{item['id']}/dismiss", headers=headers).status_code == 204
    feed = client.get("/api/jobs/feed", headers=headers).json()
    assert feed["items"] == [] and feed["hidden"]["dismissed"] == 1


async def test_track_listing_runs_pipeline_and_keeps_listing_link(client, monkeypatch):
    _install(monkeypatch)
    headers = _user(client, "track@example.com")
    extracted = ExtractedOpportunity(company_name="StartCo", role="Software Engineer Intern - Backend",
                                     required_skills=["Python"], application_url="https://elsewhere.example.com")
    monkeypatch.setattr("app.agents.discovery.get_small_llm", lambda: FakeLLM(canned_result=extracted))
    tailored = TailoredResumeResult(tailored_text=RESUME, cover_note="Dear Hiring Team,", confidence=0.8)
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: FakeLLM(canned_result=tailored))

    item = client.get("/api/jobs/feed", headers=headers).json()["items"][0]
    resp = client.post(f"/api/jobs/{item['id']}/track", headers=headers)

    assert resp.status_code == 202, resp.text
    opportunity = await Opportunity.find_one(Opportunity.role == "Software Engineer Intern - Backend")
    assert opportunity.source == "web:greenhouse"
    assert opportunity.requirements.application_url == item["url"]
    assert "Freshers welcome" in opportunity.description
    apps = client.get("/api/applications", headers=headers).json()
    again = client.get("/api/jobs/feed", headers=headers).json()["items"]
    assert again[0]["tracked_application_id"] == apps[0]["id"]


async def test_track_unknown_listing_is_404(client, monkeypatch):
    _install(monkeypatch)
    headers = _user(client, "missing@example.com")
    assert client.post("/api/jobs/64b7f0000000000000000000/track", headers=headers).status_code == 404
    assert await JobListing.count() == 0


async def test_refresh_does_not_loop_on_listings_it_no_longer_sees(client, monkeypatch):
    calls = _install(monkeypatch)
    headers = _user(client, "loop@example.com")
    # A listing cached before signals were precomputed, and gone from the boards since.
    await JobListing.get_motor_collection().insert_one(
        {"source": "greenhouse", "external_id": "old:1", "title": "Old Role", "company": "Gone",
         "location": "Pune, India", "remote": False, "url": "https://x/old", "description": "",
         "tags": [], "posted_at": None, "fetched_at": datetime.now(timezone.utc)}
    )

    client.get("/api/jobs/feed", headers=headers)  # sees a row without signals -> refresh
    client.get("/api/jobs/feed", headers=headers)
    client.get("/api/jobs/feed", headers=headers)

    assert len(calls) == 1


# ── job type ─────────────────────────────────────────────────────────────────

def test_job_type_reads_title_board_field_and_description():
    assert job_type("Software Engineer Intern") == "internship"
    assert job_type("SDE", hint="Intern") == "internship"
    assert job_type("Backend Intern", hint="full time") == "internship"  # boards file interns as full time
    assert job_type("Data Analyst (Part Time)") == "part_time"
    assert job_type("Research Analyst - 15 Hours/Week") == "part_time"
    assert job_type("Developer", hint="freelance") == "contract"
    assert job_type("Developer", hint="FullTime") == "full_time"
    assert job_type("Developer", description="This is a 6-month internship with a stipend.") == "internship"
    assert job_type("Developer", description="Our interns love it here. Full-time role.") == "full_time"
    assert job_type("Template Engineer") == "full_time"


async def test_feed_filters_by_job_type_and_counts_each_type(client, monkeypatch):
    _install(monkeypatch, FAKE_LISTINGS + [
        _listing(8, "Junior Backend Developer (Part Time)", "SideCo", desc="Python Django REST APIs SQL. Freshers welcome."),
    ])
    headers = _user(client, "types@example.com")

    feed = client.get("/api/jobs/feed", headers=headers).json()
    assert feed["job_types"]["internship"] == 1 and feed["job_types"]["part_time"] == 1
    assert {i["job_type"] for i in feed["items"]} == {"internship", "part_time"}

    interns = client.get("/api/jobs/feed?job_type=internship", headers=headers).json()
    assert [i["title"] for i in interns["items"]] == ["Software Engineer Intern - Backend"]
    assert interns["hidden"]["job_type"] == 1
    assert interns["job_types"] == feed["job_types"]  # counts ignore the type filter

    assert client.get("/api/jobs/feed?job_type=gig", headers=headers).status_code == 422


async def test_search_words_match_skills_and_skip_type_words(client, monkeypatch):
    _install(monkeypatch)
    headers = _user(client, "words@example.com")
    titles = [i["title"] for i in client.get("/api/jobs/feed?q=django%20internship", headers=headers).json()["items"]]
    assert titles == ["Software Engineer Intern - Backend"]  # "django" is a skill, not in the title


async def test_web_search_adds_new_listings_to_the_feed(client, monkeypatch):
    _install(monkeypatch)
    headers = _user(client, "web@example.com")
    client.get("/api/jobs/feed", headers=headers)  # warm the cache
    searched = []

    async def fake_search(q, job_type=None):
        searched.append((q, job_type))
        found = _listing(20, "Python Developer Intern", "WebCo", desc="Python Django SQL REST APIs. 6-month internship.")
        return [{**found, "source": "remotive", "employment": ""}], {"remotive": "ok (1)"}

    monkeypatch.setattr("app.api.routes.jobs.search_web", fake_search)
    resp = client.post("/api/jobs/search", json={"q": "python", "job_type": "internship"}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["found"] == 1 and body["new"] == 1 and len(body["new_ids"]) == 1
    assert searched == [("python", "internship")]

    feed = client.get("/api/jobs/feed?job_type=internship&q=python", headers=headers).json()
    assert body["new_ids"][0] in {i["id"] for i in feed["items"]}

    # Same search again soon: throttled per user, then answered from the cache.
    assert client.post("/api/jobs/search", json={"q": "python", "job_type": "internship"}, headers=headers).status_code == 429
    monkeypatch.setattr("app.api.routes.jobs.SEARCH_COOLDOWN", 0)
    assert client.post("/api/jobs/search", json={"q": "python", "job_type": "internship"}, headers=headers).json()["cached"]
    assert len(searched) == 1
