"""Resume links (dead "GitHub Repo" anchors), ATS scoring, and the tailor's ATS loop."""
import io

import pypdf
import pytest
from fpdf import FPDF

from app.agents.resume_tailor import run_resume_tailor
from app.agents.schemas import TailoredResumeResult
from app.core.ats import has_skill, score_resume
from app.core.resume_links import ResumeLink, drop_dead_anchors, extract_pdf, resolve_links, visible_urls
from app.core.resume_pdf import render_resume_pdf
from app.models.opportunity import OpportunityRequirements


def _pdf_with_links() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 8, "Asha Rao", new_x="LMARGIN", new_y="NEXT")
    pdf.write(6, "asha@example.com | ")
    pdf.write(6, "GitHub", link="https://github.com/asha")
    pdf.ln(8)
    pdf.cell(0, 8, "Projects", new_x="LMARGIN", new_y="NEXT")
    pdf.write(6, "- Built a parser [Code: ")
    pdf.write(6, "GitHub Repo", link="https://github.com/asha/parser")
    pdf.write(6, "] Tech: Python")
    pdf.ln(8)
    pdf.cell(0, 8, "Certifications", new_x="LMARGIN", new_y="NEXT")
    pdf.write(6, "- AWS Cloud Practitioner [")
    pdf.write(6, "View Badge", link="https://www.credly.com/badges/abc/public_url")
    pdf.write(6, "]")
    return bytes(pdf.output())


def test_pdf_links_become_visible_urls_and_badges_are_dropped():
    text, links = extract_pdf(_pdf_with_links())

    assert "github.com/asha" in text
    assert "Code: github.com/asha/parser" in text
    assert "GitHub Repo" not in text
    assert "View Badge" not in text and "credly" not in text
    assert "AWS Cloud Practitioner" in text
    assert {l.kind for l in links} == {"web", "credential"}


def test_repeated_anchor_maps_each_occurrence_to_its_own_url():
    text = "• A [Code: GitHub Repo]\n• B [Code: GitHub Repo]"
    links = [ResumeLink("GitHub Repo", "https://github.com/u/a", "web"), ResumeLink("GitHub Repo", "https://github.com/u/b", "web")]
    out = resolve_links(text, links)
    assert out == "• A Code: github.com/u/a\n• B Code: github.com/u/b"


def test_dead_anchors_are_removed_when_links_are_unknown():
    assert drop_dead_anchors("• AWS CCP[View Badge]\n• [Code:GitHub Repo]Tech: React") == "• AWS CCP\n• Tech: React"


def test_rendered_pdf_has_clickable_links_and_fits_one_page():
    text = "Asha Rao\nasha@example.com | github.com/asha\nProjects\n• Built a parser | Code: github.com/asha/parser"
    reader = pypdf.PdfReader(io.BytesIO(render_resume_pdf(text)))
    uris = {a.get_object()["/A"]["/URI"] for a in reader.pages[0]["/Annots"]}
    assert uris == {"mailto:asha@example.com", "https://github.com/asha", "https://github.com/asha/parser"}
    assert len(reader.pages) == 1


def test_aliases_count_as_having_the_skill():
    assert has_skill("Built RESTful API endpoints", "REST APIs")
    assert not has_skill("Built RESTful API endpoints", "Kubernetes")


GOOD = """Asha Rao
asha@example.com | +91 98765 43210 | github.com/asha
Summary
Backend Developer with Python, Django and REST APIs experience.
Education
ABC College, B.Tech CSE 2022 – 2026
Experience
Intern, XYZ 2025
• Built REST APIs in Django serving 2 internal teams
• Designed SQL schemas for reporting
• Improved test coverage with Pytest
Technical Skills
Languages: Python, SQL
Projects
Parser
• Developed a log parser in Python"""


def test_ats_scores_full_marks_when_everything_honest_is_there():
    report = score_resume(GOOD, "Backend Developer", ["Python", "Django", "REST APIs"], ["SQL"])
    assert report.score == 100
    assert report.suggestions == []


def test_ats_separates_fixable_from_blocked_keywords():
    base = GOOD.replace("REST APIs", "RESTful services")
    report = score_resume(base, "Backend Developer", ["Python", "REST APIs", "Kubernetes"], [], base_text=base)
    assert report.fixable_keywords == ["REST APIs"]
    assert report.missing_keywords == ["Kubernetes"]
    assert report.blocked_points == 15  # 45 * 2/(2+2+2) -> one of three required skills
    assert any("exact wording" in s for s in report.suggestions)


class _Sequence:
    """LLM double returning a different canned result per call, recording messages."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return self.results.pop(0)


async def test_tailor_revises_until_honest_maximum(client, monkeypatch):
    base = GOOD.replace("Backend Developer with", "Student with").replace("REST APIs", "RESTful services")
    weak = TailoredResumeResult(tailored_text=base, cover_note="Dear Hiring Team,", confidence=0.7)
    strong = TailoredResumeResult(tailored_text=GOOD, cover_note="Dear Hiring Team,", confidence=0.8)
    llm = _Sequence([weak, strong, strong])
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: llm)

    result, ats, _ = await run_resume_tailor(
        "64b7f0000000000000000001", "64b7f0000000000000000002", base, "Backend Developer", "Co",
        OpportunityRequirements(required_skills=["Python", "Django", "REST APIs"], preferred_skills=["SQL"]),
        None, job_description="We need REST APIs in Django.",
    )

    assert len(llm.calls) == 2  # stopped as soon as the honest maximum was reached
    assert ats.score == 100
    assert result.tailored_text == GOOD
    feedback = llm.calls[1][-1].content
    assert "REST APIs" in feedback and "Backend Developer" in feedback
    assert "We need REST APIs in Django." in llm.calls[0][1].content


async def test_tailor_prefers_version_that_keeps_every_link(client, monkeypatch):
    base = GOOD
    dropped = TailoredResumeResult(tailored_text=GOOD.replace(" | github.com/asha", ""), cover_note="x", confidence=0.8)
    kept = TailoredResumeResult(tailored_text=GOOD, cover_note="x", confidence=0.8)
    llm = _Sequence([dropped, kept])
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: llm)

    result, _ats, _ = await run_resume_tailor(
        "64b7f0000000000000000001", "64b7f0000000000000000002", base, "Backend Developer", "Co",
        OpportunityRequirements(required_skills=["Python"]), None,
    )

    assert "github.com/asha" in visible_urls(result.tailored_text)
    assert "github.com/asha" in llm.calls[1][-1].content


async def test_tailor_rejects_a_version_that_deletes_content(client, monkeypatch):
    trimmed = "\n".join(l for l in GOOD.split("\n") if "Pytest" not in l and "SQL schemas" not in l and "Parser" not in l and "log parser" not in l)
    short = TailoredResumeResult(tailored_text=trimmed, cover_note="x", confidence=0.8)
    full = TailoredResumeResult(tailored_text=GOOD, cover_note="x", confidence=0.8)
    llm = _Sequence([short, full])
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: llm)

    result, _ats, _ = await run_resume_tailor(
        "64b7f0000000000000000001", "64b7f0000000000000000002", GOOD, "Backend Developer", "Co",
        OpportunityRequirements(required_skills=["Python"]), None,
    )

    assert result.tailored_text == GOOD
    assert "deleted content" in llm.calls[1][-1].content


def test_inflation_and_lost_skill_lines_are_detected():
    from app.agents.resume_tailor import find_inflation, missing_skill_lines

    base = "Skills\nLanguages: Python\nAI/ML & Agentic Systems: LangGraph\n• Built an app"
    puffed = TailoredResumeResult(tailored_text="Languages: Python\n• Built a scalable app", cover_note="I am an expert.", confidence=1)
    assert find_inflation(base, puffed) == ["scalable", "expert"]
    assert missing_skill_lines(base, puffed.tailored_text) == ["AI/ML & Agentic Systems"]


def test_skills_implied_by_the_resume_are_fixable_not_blocked():
    base = "Jane Doe\nSkills: Django, PostgreSQL, PyTorch\nProjects\n• Built a Django app"
    report = score_resume(base, "Backend Developer", ["Python", "SQL", "Machine Learning", "Kubernetes"], [], base)
    assert set(report.fixable_keywords) == {"Python", "SQL", "Machine Learning"}
    assert report.missing_keywords == ["Kubernetes"]
    # React does not imply Redux — implication stays near-certain.
    assert not has_skill("Skills: React", "Redux")
    assert has_skill("Skills: React", "JavaScript")


async def test_confirmed_skills_may_be_added_and_earn_keyword_points(client, monkeypatch):
    base = GOOD
    with_k8s = GOOD.replace("Technical Skills", "Technical Skills\nDevOps: Kubernetes")
    llm = _Sequence([TailoredResumeResult(tailored_text=with_k8s, cover_note="Dear Hiring Team,", confidence=0.8)] * 3)
    monkeypatch.setattr("app.agents.resume_tailor.get_strong_llm", lambda: llm)
    requirements = OpportunityRequirements(required_skills=["Python", "Kubernetes"])

    # Without confirmation, adding Kubernetes is fabrication.
    with pytest.raises(RuntimeError):
        await run_resume_tailor(
            "64b7f0000000000000000001", "64b7f0000000000000000002", base, "Backend Developer", "Co",
            requirements, None,
        )

    llm.results = [TailoredResumeResult(tailored_text=with_k8s, cover_note="Dear Hiring Team,", confidence=0.8)] * 3
    result, ats, _ = await run_resume_tailor(
        "64b7f0000000000000000001", "64b7f0000000000000000002", base, "Backend Developer", "Co",
        requirements, None, confirmed_skills=["Kubernetes"],
    )
    assert "Kubernetes" in ats.matched_keywords and ats.blocked_points == 0
    assert not any("Kubernetes" in w for w in result.warnings)
    assert "SKILLS THE CANDIDATE CONFIRMED" in llm.calls[-1][1].content
