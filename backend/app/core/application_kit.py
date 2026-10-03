"""
Application kit — honest, ready-to-paste answers to the questions application forms ask
(LinkedIn Easy Apply screening questions, Workday/Greenhouse forms), plus a referral
helper. Deterministic: built from the resume, the profile and the posting; no LLM.

Why it exists: students reach LinkedIn's "How many years of experience do you have with
Java?" and don't know what to type. LinkedIn only takes whole numbers, and an answer that
contradicts the resume gets flagged by recruiters. The kit computes the real number from
the resume's dated internship/experience entries (2 months of Spring Boot at an
internship = 0 full years), says so, and explains the reasoning in a note.
"""
import re
from dataclasses import asdict, dataclass
from datetime import date
from urllib.parse import quote_plus

from app.core.resume_links import visible_urls
from app.core.resume_pdf import is_heading
from app.sources.job_matching import skills_in

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_DATE = r"(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?((?:19|20)\d{2})"
_RANGE = re.compile(rf"{_DATE}\s*(?:-|–|—|to)\s*(?:{_DATE}|(present|current|now|ongoing))", re.I)
_EXPERIENCE_HEADINGS = ("experience", "internship", "work", "employment")


@dataclass
class Answer:
    question: str
    answer: str
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Stint:
    title: str
    months: int
    skills: list[str]


def _month(mon: str | None, year: str, end: bool) -> tuple[int, int]:
    m = _MONTHS.get((mon or "")[:3].lower(), 12 if end else 1)
    return int(year), m


def experience_stints(resume_text: str, today: date | None = None) -> list[Stint]:
    """Dated entries under Experience/Internship headings, with their duration in months
    (inclusive: "June 2025 – July 2025" is 2 months) and the skills their bullets mention."""
    today = today or date.today()
    stints: list[Stint] = []
    section = ""
    current: Stint | None = None
    body: list[str] = []

    def close():
        if current is not None:
            current.skills = skills_in(current.title + "\n" + "\n".join(body))
            stints.append(current)

    for line in (resume_text or "").split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if is_heading(stripped):
            close()
            current, body = None, []
            section = stripped.lower()
            continue
        if not any(h in section for h in _EXPERIENCE_HEADINGS):
            continue
        m = _RANGE.search(stripped)
        if m:
            close()
            body = []
            sy, sm = _month(m.group(1), m.group(2), end=False)
            if m.group(5):
                ey, em = today.year, today.month
            else:
                ey, em = _month(m.group(3), m.group(4), end=True)
            months = max(1, (ey - sy) * 12 + (em - sm) + 1)
            current = Stint(title=stripped[: m.start()].strip(" ,|–-"), months=months, skills=[])
        elif current is not None:
            body.append(stripped)
    close()
    return stints


def _years(months: int) -> str:
    return str(months // 12)


def _contact(resume_text: str) -> dict[str, str]:
    head = "\n".join((resume_text or "").split("\n")[:6])
    out: dict[str, str] = {}
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", head)
    phone = re.search(r"\+?\d[\d\s-]{8,}\d", head)
    if email:
        out["email"] = email.group(0)
    if phone:
        out["phone"] = phone.group(0).strip()
    for url in visible_urls(resume_text):
        low = url.lower()
        if "linkedin.com/in/" in low and "linkedin" not in out:
            out["linkedin"] = f"https://{url}"
        elif re.fullmatch(r"github\.com/[^/]+", low) and "github" not in out:
            out["github"] = f"https://{url}"
        elif "portfolio" not in out and not any(h in low for h in ("github.com", "linkedin.com")):
            out["portfolio"] = f"https://{url}"
    return out


def build_answers(
    resume_text: str,
    profile,
    name: str,
    posting_skills: list[str],
    cover_note: str | None = None,
    today: date | None = None,
) -> list[Answer]:
    today = today or date.today()
    stints = experience_stints(resume_text, today)
    resume_skills = set(skills_in(resume_text))
    total_months = sum(s.months for s in stints)
    full_time_years = profile.experience_years if profile and profile.experience_years is not None else 0
    answers: list[Answer] = []

    # Overall experience — full-time only; internships explained in the note.
    intern_note = (
        "Internships: " + ", ".join(f"{s.title or 'internship'} ({s.months} mo)" for s in stints) + ". "
        if stints else ""
    )
    answers.append(Answer(
        "How many years of work experience do you have?",
        f"{full_time_years:g}",
        intern_note + "Forms mean full-time experience and take whole numbers — for a fresher, 0 is the honest "
        "answer and what recruiters expect for entry-level roles. Mention internships in the resume, not here.",
    ))

    # Per-skill experience, for the skills this posting asks about.
    for skill in list(dict.fromkeys(posting_skills))[:10]:
        months = sum(s.months for s in stints if skill in s.skills)
        if skill not in resume_skills:
            answers.append(Answer(
                f"How many years of experience do you have with {skill}?", "0",
                f"{skill} isn't on your resume. Answer 0 — claiming it gets caught at the first technical round.",
            ))
        elif months:
            answers.append(Answer(
                f"How many years of experience do you have with {skill}?", _years(months),
                f"Used for {months} month{'s' if months != 1 else ''} in internships"
                + (" plus projects" if months < 12 else "") + ". Whole years only, so this rounds down.",
            ))
        else:
            answers.append(Answer(
                f"How many years of experience do you have with {skill}?", "0",
                f"You've used {skill} in projects/coursework, not a job. If there's a text box, say "
                f"\"Academic and personal projects (see resume)\".",
            ))

    if profile is not None:
        education = ", ".join(p for p in [
            "B.Tech" + (f" in {profile.branch}" if profile.branch else ""),
            profile.college,
            str(profile.graduation_year) if profile.graduation_year else None,
        ] if p)
        answers.append(Answer("Highest level of education", education))
        if profile.cgpa is not None:
            answers.append(Answer("CGPA / GPA", f"{profile.cgpa:g} / 10"))
        grad = profile.graduation_year
        answers.append(Answer(
            "Notice period / when can you join?",
            profile.notice_period or (f"Available from June {grad}, after graduation" if grad and grad > today.year
                                      else "Immediate"),
            "Set your own wording in Profile." if not profile.notice_period else "",
        ))
        answers.append(Answer("Current CTC", "0 (student)" if full_time_years < 1 else "—",
                              "Freshers enter 0. Don't leave it blank — some forms reject that."))
        answers.append(Answer(
            "Expected CTC",
            f"{profile.expected_ctc_lpa:g} LPA" if profile.expected_ctc_lpa else "As per company standards",
            "" if profile.expected_ctc_lpa else "Add a number in Profile if the form needs one.",
        ))
        answers.append(Answer(
            "Are you willing to relocate?",
            "Yes" + (f" — preferably {', '.join(profile.preferred_locations[:3])}" if profile.preferred_locations else ""),
        ))
    answers.append(Answer("Are you legally authorized to work in India?", "Yes"))
    answers.append(Answer("Will you require visa sponsorship?", "No"))

    contact = _contact(resume_text)
    for key, label in (("linkedin", "LinkedIn profile"), ("github", "GitHub"), ("portfolio", "Portfolio / website"),
                       ("phone", "Mobile number"), ("email", "Email")):
        if key in contact:
            answers.append(Answer(label, contact[key]))

    if cover_note:
        paras = [p.strip() for p in cover_note.split("\n\n") if p.strip() and not p.strip().lower().startswith(("dear", "best", "regards", "thank"))]
        if paras:
            answers.append(Answer("Why are you interested in this role?", paras[0], "From your tailored cover note."))
    if total_months and not answers[0].note:
        answers[0].note = f"{total_months} months of internships."
    return answers


def referral_kit(name: str, profile, company: str, role: str, matched_skills: list[str]) -> dict:
    """LinkedIn people-search links (alumni first — warmest referral path for students)
    and a connection note that fits LinkedIn's 300-character limit."""
    first = (name or "").split()[0] if name else "there"
    college = profile.college if profile and profile.college else None
    year = profile.graduation_year if profile and profile.graduation_year else None
    branch = profile.branch if profile and profile.branch else None
    skills = ", ".join(matched_skills[:2])

    who = " ".join(p for p in [f"{year}" if year else None, branch, "student"] if p)
    at = f" at {college}" if college else ""
    note = (
        f"Hi! I'm {first}, a {who}{at}. I'm applying for the {role} role at {company}"
        + (f" — my {skills} work lines up with it" if skills else "")
        + ". Would you be open to a quick chat or a referral? Thank you!"
    )
    if len(note) > 300:
        note = (f"Hi! I'm {first}, a {who}{at}, applying for {role} at {company}. "
                "Would you be open to a referral? Thank you!")[:300]

    message = (
        f"Hi {{name}},\n\nI'm {name}, a {who}{at}. I came across the {role} opening at {company} and I'm applying"
        + (f" — I've worked with {skills} in my internship and projects" if skills else "")
        + ".\n\nIf you think I'd be a fit, would you be willing to refer me? I've attached my resume, and I'm "
        "happy to share anything else that helps.\n\nThank you for your time!\n" + name
    )
    base = "https://www.linkedin.com/search/results/people/?keywords="
    links = []
    if college:
        links.append({"label": f"{college} alumni at {company}", "url": base + quote_plus(f"{company} {college}")})
    links.append({"label": f"People at {company} in this team", "url": base + quote_plus(f"{company} {role}")})
    links.append({"label": f"Recruiters at {company}", "url": base + quote_plus(f"{company} recruiter")})
    return {"connection_note": note, "message": message, "search_links": links}
