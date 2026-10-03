"""Application kit: honest form answers from the resume, and the referral helper."""
from datetime import date
from types import SimpleNamespace

from app.core.application_kit import build_answers, experience_stints, referral_kit

RESUME = """Asha Rao
asha@example.com | +91 98765 43210 | linkedin.com/in/asha-rao | github.com/asha
Experience
Backend Intern, Acme Labs May 2025 – July 2025
• Built REST APIs in Django
Software Intern, Beta Corp Jan 2026 – Present
• Wrote Python scripts and SQL reports
Projects
Shop
• Built a React storefront
Technical Skills
Languages: Python, SQL, JavaScript"""

PROFILE = SimpleNamespace(experience_years=0, branch="CSE", college="JNTU Hyderabad", graduation_year=2027, cgpa=8.4,
                          notice_period=None, expected_ctc_lpa=None, preferred_locations=["Hyderabad"])
TODAY = date(2026, 10, 3)


def _answer(answers, question_part):
    return next(a for a in answers if question_part in a.question)


def test_internship_durations_and_skills_come_from_dated_entries():
    stints = experience_stints(RESUME, TODAY)
    assert [(s.title, s.months) for s in stints] == [("Backend Intern, Acme Labs", 3), ("Software Intern, Beta Corp", 10)]
    assert "Django" in stints[0].skills and "Python" in stints[1].skills


def test_answers_are_honest_whole_numbers():
    answers = build_answers(RESUME, PROFILE, "Asha Rao", ["Django", "Kubernetes", "React"], today=TODAY)
    assert _answer(answers, "years of work experience").answer == "0"
    django = _answer(answers, "with Django")
    assert django.answer == "0" and "3 months" in django.note
    assert "isn't on your resume" in _answer(answers, "with Kubernetes").note
    assert "projects" in _answer(answers, "with React").note
    assert _answer(answers, "Notice period").answer == "Available from June 2027, after graduation"
    assert _answer(answers, "LinkedIn").answer == "https://linkedin.com/in/asha-rao"
    assert _answer(answers, "Current CTC").answer.startswith("0")


def test_a_year_of_internships_with_a_skill_counts_as_one_year():
    long = RESUME.replace("Jan 2026 – Present", "Jan 2025 – Dec 2025")
    answers = build_answers(long, PROFILE, "Asha Rao", ["Python"], today=TODAY)
    assert _answer(answers, "with Python").answer == "1"


def test_referral_note_fits_linkedins_limit_and_searches_alumni_first():
    kit = referral_kit("Asha Rao", PROFILE, "Hevo Data", "Associate Software Development Engineer", ["Python", "Django"])
    assert len(kit["connection_note"]) <= 300
    assert "JNTU Hyderabad" in kit["connection_note"]
    assert kit["search_links"][0]["label"] == "JNTU Hyderabad alumni at Hevo Data"
    assert "Hevo+Data+JNTU+Hyderabad" in kit["search_links"][0]["url"]
