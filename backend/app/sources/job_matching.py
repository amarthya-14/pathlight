"""
Matches job-board listings to ONE student's resume — deterministic, no LLM, so the feed is
instant and costs no quota.

A listing is shown only if it passes every gate:
1. Field:      the role's family (app/sources/job_signals.py) fits the student's — from
               their resume skills and target roles. A backend student never sees
               "Video Editor Intern" or "Account Manager".
2. Level:      a fresher never sees "3+ years", senior/staff titles, or level-II roles.
3. Batch:      "2025 batch only" is hidden from the 2027 batch.
4. Freshness:  posted within the chosen window (default 30 days).
5. Match %:    at or above the chosen threshold (default 60%).
6. Job type:   internship / full-time / part-time, when the student picks one. Counted
               per type before this gate, so the UI can show "Internships 12".

Match % (0-100) is about the RESUME: 55% skill coverage (skills the posting asks for that
the resume shows), 30% field fit, 15% level fit. Every hidden listing is counted by reason,
so the UI can say what was filtered out instead of silently showing less.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.ats import has_skill
from app.sources.job_signals import _TITLE_ENTRY, classify_title, compatible, is_senior_title, job_type

# No one- or two-letter languages ("R", "Go"): they match "R&D" and "Go beyond" in prose.
SKILL_VOCAB = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Golang", "Rust", "Kotlin", "Swift", "Scala", "Ruby",
    "PHP", "SQL", "Dart", "Bash", "HTML", "CSS",
    "React", "Angular", "Vue", "Next.js", "Node.js", "Express", "Django", "Flask", "FastAPI", "Spring Boot",
    "Spring", "Hibernate", ".NET", "Rails", "Laravel", "Flutter", "React Native", "Android", "iOS",
    "REST APIs", "GraphQL", "gRPC", "Microservices", "System Design", "Distributed Systems",
    "MongoDB", "PostgreSQL", "MySQL", "Redis", "Elasticsearch", "Cassandra", "DynamoDB", "Kafka", "RabbitMQ",
    "Spark", "Hadoop", "Airflow", "dbt", "Snowflake", "BigQuery", "Databricks", "ETL", "Data Warehousing",
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "CI/CD", "Linux", "Git",
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision", "PyTorch", "TensorFlow", "scikit-learn",
    "Pandas", "NumPy", "LLM", "LangChain", "LangGraph", "Generative AI", "Prompt Engineering", "MLOps",
    "Data Structures", "Algorithms", "OOP", "DBMS", "Operating Systems", "Computer Networks",
    "Selenium", "Cypress", "Jest", "JUnit", "Pytest", "Testing", "Automation",
    "Power BI", "Tableau", "Excel", "Statistics", "Figma",
    "Security", "Networking", "Agile",
]


def skills_in(text: str) -> list[str]:
    return [s for s in SKILL_VOCAB if has_skill(text, s)]


def listing_skills(title: str, description: str) -> list[str]:
    """Computed once per listing at fetch time (stored on JobListing.skills) — matching
    the vocabulary against every description on every feed request pinned the CPU."""
    return skills_in(f"{title}\n{(description or '')[:6000]}")


@dataclass
class Student:
    skills: list[str]
    families: set[str]
    experience_years: float | None
    graduation_year: int | None
    locations: list[str] = field(default_factory=list)
    open_to_remote: bool = True

    @property
    def fresher(self) -> bool:
        return self.experience_years is None or self.experience_years < 1


@dataclass
class Filters:
    min_match: int = 60
    days: int = 30
    include_experienced: bool = False
    job_type: str | None = None  # None = every type


@dataclass
class Match:
    listing: object
    score: int
    matched: list[str]
    missing: list[str]
    reasons: list[str]


HIDDEN_REASONS = {
    "field": "outside your field",
    "experience": "need more experience",
    "batch": "for other batches",
    "old": "posted too long ago",
    "low_match": "below your match threshold",
    "job_type": "a different job type",
    "dismissed": "you hid",
}


def _level(listing, student: Student) -> tuple[float | None, str]:
    """(fit 0-1, reason) — None fit means the listing is hidden for its level."""
    need = listing.min_experience
    have = student.experience_years or 0
    # Rows cached before signals existed carry defaults; the title still tells a lot.
    senior = listing.senior or is_senior_title(listing.title)
    entry = listing.entry_level or bool(_TITLE_ENTRY.search(listing.title))
    if student.fresher:
        if entry and (need is None or need <= 1):
            return 1.0, "Entry-level"
        if senior or (need is not None and need > have + 1):
            return None, f"Needs {need:g}+ yrs" if need else "Senior role"
        if need is not None:
            return 0.85, f"Asks {need:g} yr" if need <= 1 else f"Asks {need:g} yrs"
        return 0.75, "Level not stated"
    if need is not None and need > have + 1.5:
        return None, f"Needs {need:g}+ yrs"
    return (1.0 if not entry else 0.6), (f"Asks {need:g} yrs" if need else "Your level")


def evaluate(listing, student: Student, filters: Filters, now: datetime) -> tuple[Match | None, str | None]:
    """Returns (match, None) when shown, or (None, hidden_reason_key)."""
    family = listing.family
    if family == "other":
        # Cached before signals existed (or truly unclassifiable): classify by title now.
        family = classify_title(listing.title)
    fit = compatible(student.families, family)
    if fit == 0:
        return None, "field"

    level_fit, level_reason = _level(listing, student)
    if level_fit is None and not filters.include_experienced:
        return None, "experience"
    level_fit = level_fit if level_fit is not None else 0.3

    if student.graduation_year and listing.batch_years and student.graduation_year not in listing.batch_years:
        return None, "batch"

    posted = listing.posted_at
    if posted is not None and posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    if filters.days and (posted is None or (now - posted).days > filters.days):
        return None, "old"

    wanted = listing.skills
    have = set(student.skills)
    matched = [s for s in wanted if s in have]
    missing = [s for s in wanted if s not in have]
    # Laplace-smoothed coverage, so "asks 1 skill, you have it" isn't an automatic 100%.
    # No readable skills at all = no evidence of a resume match, so it scores low rather
    # than a free 50% ("RPA Developer" with an empty description isn't a 69% match).
    skill_fit = (len(matched) + 1) / (len(wanted) + 2) if wanted else 0.2
    field_fit = 1.0 if fit == 2 else 0.7
    score = round(100 * (0.55 * skill_fit + 0.30 * field_fit + 0.15 * level_fit))
    if score < filters.min_match:
        return None, "low_match"

    reasons = []
    if wanted:
        reasons.append(f"{len(matched)} of {len(wanted)} skills")
    reasons.append(level_reason)
    if posted is not None:
        days = max(0, (now - posted).days)
        reasons.append("Posted today" if days == 0 else f"Posted {days}d ago")
    return Match(listing, score, matched, missing, reasons), None


def alert_job_unfit(title: str, student: Student) -> str | None:
    """For jobs from alert emails, where only the title is known: the reason to skip it
    (clearly senior for a fresher, or outside the student's field), or None to keep it."""
    from app.sources.job_signals import signals

    s = signals(title, "")
    if compatible(student.families, s["family"]) == 0:
        return "outside your field"
    need = s["min_experience"]
    if student.fresher and (s["senior"] or (need is not None and need > (student.experience_years or 0) + 1)):
        return "needs experience"
    return None


def _location_boost(listing, student: Student) -> int:
    loc = (listing.location or "").lower()
    if any(city.lower() in loc for city in student.locations if city.strip()):
        return 2
    if listing.remote and not student.open_to_remote:
        return -1
    return 0


def listing_type(listing) -> str:
    return listing.job_type or job_type(listing.title)


def rank(listings, student: Student, filters: Filters, dismissed: set[str], limit: int = 80):
    """Returns (shown matches, hidden counts by reason, total that passed, matches per
    job type before the type filter)."""
    now = datetime.now(timezone.utc)
    shown: list[Match] = []
    hidden = {key: 0 for key in HIDDEN_REASONS}
    by_type: dict[str, int] = {}
    for listing in listings:
        if f"{listing.source}:{listing.external_id}" in dismissed:
            hidden["dismissed"] += 1
            continue
        match, reason = evaluate(listing, student, filters, now)
        if match is None:
            hidden[reason] += 1
            continue
        kind = listing_type(listing)
        by_type[kind] = by_type.get(kind, 0) + 1
        if filters.job_type and kind != filters.job_type:
            hidden["job_type"] += 1
            continue
        shown.append(match)

    def recency(m: Match) -> float:
        p = m.listing.posted_at
        return p.timestamp() if p else 0

    shown.sort(key=lambda m: (m.score + 3 * _location_boost(m.listing, student), recency(m)), reverse=True)
    # Variety: at most 4 roles per company at the top of the feed.
    per_company: dict[str, int] = {}
    out = []
    for m in shown:
        company = re.sub(r"\W+", "", m.listing.company.lower())
        if per_company.get(company, 0) >= 4:
            continue
        per_company[company] = per_company.get(company, 0) + 1
        out.append(m)
        if len(out) >= limit:
            break
    return out, hidden, len(shown), by_type
