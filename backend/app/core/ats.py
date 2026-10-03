"""
Deterministic ATS (applicant tracking system) score for a resume against one posting.

Real ATS products (Workday, Greenhouse, Lever, Taleo) parse the resume as plain text and
rank it mostly on literal keyword overlap with the job description, then on whether they
could find the standard sections and contact details. This scorer models exactly those
checks — no LLM — so the same resume always gets the same score, and the Resume Tailor
can be told precisely which points it is still leaving on the table.

The score is split into points the tailor CAN earn by honest rewording (use the posting's
exact wording for a skill you have, add the target job title, keep links, lead bullets
with action verbs) and points it must NOT earn (skills that aren't on the resume at all).
`blocked_points` reports the latter so the UI can say "the rest needs skills you don't
have yet" instead of pretending 100 is always reachable.

Weights (100 total): keywords 45, job title 5, sections 15, contact 10, format 15,
impact 10.
"""
import re
from functools import lru_cache
from dataclasses import asdict, dataclass, field

from app.core.resume_pdf import is_heading

# Common spellings of the same skill. A resume saying "RESTful API" genuinely has
# "REST APIs"; an ATS doing literal matching doesn't know that, so the tailor should use
# the posting's wording — and the fabrication guard must not treat that as invented.
ALIASES: list[set[str]] = [
    {"rest", "rest api", "rest apis", "restful", "restful api", "restful apis", "restful services"},
    {"javascript", "js", "ecmascript"},
    {"typescript", "ts"},
    {"node", "node.js", "nodejs"},
    {"react", "react.js", "reactjs"},
    {"next.js", "nextjs"},
    {"vue", "vue.js", "vuejs"},
    {"postgres", "postgresql"},
    {"mongodb", "mongo"},
    {"kubernetes", "k8s"},
    {"machine learning", "ml"},
    {"artificial intelligence", "ai"},
    {"natural language processing", "nlp"},
    {"aws", "amazon web services"},
    {"gcp", "google cloud", "google cloud platform"},
    {"azure", "microsoft azure"},
    {"ci/cd", "cicd", "continuous integration"},
    {"oop", "object-oriented programming", "object oriented programming"},
    {"dsa", "data structures and algorithms", "data structures & algorithms", "data structures"},
    {"dbms", "database management systems"},
    {"llm", "llms", "large language models"},
    {"spring boot", "springboot"},
    {"c++", "cpp"},
    {"c#", "csharp"},
    {"golang", "go"},
    {"git", "github", "version control"},
    {"sql", "mysql"},
    {"html", "html5"},
    {"css", "css3"},
]

KNOWN_SECTIONS = {
    "summary": ("summary", "profile", "objective", "about me", "professional summary"),
    "education": ("education", "academic"),
    "experience": ("experience", "internship", "internships", "work experience", "employment", "projects"),
    "skills": ("skills", "technical skills", "core competencies", "technologies"),
}

ACTION_VERBS = {
    "achieved", "analyzed", "architected", "automated", "built", "collaborated", "configured", "contributed",
    "created", "debugged", "delivered", "deployed", "designed", "developed", "digitized", "drove", "engineered",
    "enhanced", "established", "evaluated", "executed", "implemented", "improved", "increased", "integrated",
    "launched", "led", "maintained", "managed", "migrated", "modeled", "optimized", "orchestrated", "organized",
    "owned", "planned", "presented", "produced", "programmed", "published", "reduced", "refactored", "researched",
    "resolved", "scaled", "secured", "shipped", "simplified", "solved", "streamlined", "tested", "trained",
    "won", "wrote", "coordinated", "conducted", "spearheaded", "mentored", "authored", "prototyped",
}

BULLET = re.compile(r"^\s*[-•*▪●◦·]\s+")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?:\+?\d[\d\s().-]{8,}\d)")
PROFILE_LINK = re.compile(r"(linkedin\.com/|github\.com/|gitlab\.com/|portfolio|\.dev\b|\.me\b|\.io/)", re.I)
# Things an ATS parser chokes on: table pipes used as columns, icon glyphs, link labels.
UNPARSEABLE = re.compile(r"[☀-➿-]|\[(?:view|code|link)[^\]]*\]", re.I)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


@lru_cache(maxsize=4096)
def _pattern(term: str) -> re.Pattern:
    term = term.strip()
    flags = 0 if len(term) <= 2 else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", flags)


def literal_mention(text: str, term: str) -> bool:
    return bool(term.strip()) and bool(_pattern(term).search(text or ""))


@lru_cache(maxsize=4096)
def aliases_of(term: str) -> frozenset[str]:
    key = _norm(term)
    for group in ALIASES:
        if key in group:
            return frozenset(group | {key})
    return frozenset({key})


def has_skill(text: str, term: str) -> bool:
    """True if the text shows this skill under ANY common spelling."""
    return any(literal_mention(text, alias) for alias in aliases_of(term)) or literal_mention(text, term)


@dataclass
class AtsReport:
    score: int
    breakdown: dict[str, int]
    matched_keywords: list[str] = field(default_factory=list)
    # On the resume under some spelling, but not the posting's exact wording yet.
    fixable_keywords: list[str] = field(default_factory=list)
    # Not on the resume at all — honest tailoring can't earn these points.
    missing_keywords: list[str] = field(default_factory=list)
    blocked_points: int = 0
    suggestions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _keywords(required: list[str], preferred: list[str]) -> list[tuple[str, float]]:
    seen: dict[str, tuple[str, float]] = {}
    for skill in required:
        if skill and skill.strip():
            seen.setdefault(_norm(skill), (skill.strip(), 2.0))
    for skill in preferred:
        if skill and skill.strip():
            seen.setdefault(_norm(skill), (skill.strip(), 1.0))
    return list(seen.values())


def _title_words(role: str) -> str:
    # "Software Engineer - Backend (2026 grads)" -> "Software Engineer"
    core = re.split(r"[-–—(|,/]", role or "")[0]
    core = re.sub(r"\b(sr|senior|jr|junior|i{1,3}|intern(ship)?|trainee|associate|graduate|fresher)\b\.?", "", core, flags=re.I)
    return re.sub(r"\s+", " ", core).strip()


def score_resume(
    text: str,
    role: str,
    required_skills: list[str],
    preferred_skills: list[str],
    base_text: str | None = None,
) -> AtsReport:
    """Scores `text` against the posting. `base_text` (the user's original resume)
    decides which missing keywords are honestly fixable: a keyword is fixable only if
    the ORIGINAL resume shows that skill under some spelling."""
    text = text or ""
    base = base_text if base_text is not None else text
    lines = [l for l in text.split("\n") if l.strip()]
    suggestions: list[str] = []
    breakdown: dict[str, int] = {}

    # ── Keywords (45) ────────────────────────────────────────────────────────────
    keywords = _keywords(required_skills, preferred_skills)
    total_weight = sum(w for _, w in keywords)
    matched, fixable, missing = [], [], []
    earned = blocked = 0.0
    for kw, weight in keywords:
        if literal_mention(text, kw):
            matched.append(kw)
            earned += weight
        elif has_skill(base, kw):
            fixable.append(kw)
        else:
            missing.append(kw)
            blocked += weight
    if total_weight:
        breakdown["keywords"] = round(45 * earned / total_weight)
        blocked_points = round(45 * blocked / total_weight)
    else:
        breakdown["keywords"] = 45  # posting lists no skills — nothing to miss
        blocked_points = 0
    if fixable:
        suggestions.append(
            "Use the posting's exact wording for skills you already have: " + ", ".join(fixable)
        )

    # ── Job title (5) ────────────────────────────────────────────────────────────
    title = _title_words(role)
    title_hit = bool(title) and literal_mention(text, title)
    breakdown["job_title"] = 5 if title_hit or not title else 0
    if not breakdown["job_title"]:
        suggestions.append(f'Name the target role "{title}" in the summary line.')

    # ── Sections (15) ────────────────────────────────────────────────────────────
    lowered_lines = [_norm(l).rstrip(":") for l in lines]
    found_sections = {
        name for name, heads in KNOWN_SECTIONS.items() if any(l in heads or l.startswith(heads) for l in lowered_lines if len(l) < 40)
    }
    breakdown["sections"] = round(15 * len(found_sections) / len(KNOWN_SECTIONS))
    for name in KNOWN_SECTIONS:
        if name not in found_sections and name in {"summary", "skills"}:
            suggestions.append(f'Add a standard "{name.title()}" heading — ATS parsers look for it by name.')

    # ── Contact (10) ─────────────────────────────────────────────────────────────
    head = "\n".join(lines[:6])
    contact = 0
    contact += 4 if EMAIL.search(head) else 0
    contact += 3 if PHONE.search(head) else 0
    contact += 3 if PROFILE_LINK.search(head) else 0
    breakdown["contact"] = contact
    # Only what the original resume had can be asked for — never invent contact details.
    if contact < 10 and (EMAIL.search(base) or PHONE.search(base) or PROFILE_LINK.search(base)):
        if (EMAIL.search(base) and not EMAIL.search(head)) or (PROFILE_LINK.search(base) and not PROFILE_LINK.search(head)):
            suggestions.append("Keep email, phone and profile links together in the header, right under the name.")

    # ── Format (15) ──────────────────────────────────────────────────────────────
    bullets = [l for l in lines if BULLET.match(l)]
    fmt = 5  # single-column plain text — always true for Pathlight's PDF
    fmt += 5 if len(bullets) >= 3 else 0
    fmt += 5 if not UNPARSEABLE.search(text) else 0
    breakdown["format"] = fmt
    if UNPARSEABLE.search(text):
        suggestions.append("Remove icons and link labels like [View Badge] — ATS parsers read them as noise.")

    # ── Impact (10) ──────────────────────────────────────────────────────────────
    def first_word(line: str) -> str:
        return re.sub(r"[^a-z]", "", BULLET.sub("", line).split(" ")[0].lower()) if line.strip() else ""

    # Only Experience/Projects bullets are achievements; "• CGPA: 8.5" is not.
    content_bullets, section = [], ""
    for line in lines:
        if is_heading(line):
            section = _norm(line).rstrip(":")
        elif BULLET.match(line) and any(k in section for k in ("experience", "project", "intern", "work")):
            if not re.match(r"^\s*[-•*▪●◦·]\s+(code|tech|stack|link|github)\s*:", line, re.I):
                content_bullets.append(line)
    verb_ratio = (
        sum(first_word(b) in ACTION_VERBS for b in content_bullets) / len(content_bullets) if content_bullets else 0
    )
    impact = 6 if verb_ratio >= 0.8 else 4 if verb_ratio >= 0.5 else 0
    words = len(text.split())
    # Too long hurts (recruiters skim; some ATS truncate). Short is fine for a student and
    # can't be fixed honestly anyway — padding is exactly what the tailor must not do.
    impact += 4 if words <= 900 else 2 if words <= 1200 else 0
    breakdown["impact"] = impact
    if verb_ratio < 0.8 and content_bullets:
        suggestions.append("Start every bullet with a strong past-tense action verb (Built, Designed, Improved…).")

    score = min(100, sum(breakdown.values()))
    return AtsReport(
        score=score,
        breakdown=breakdown,
        matched_keywords=matched,
        fixable_keywords=fixable,
        missing_keywords=missing,
        blocked_points=blocked_points,
        suggestions=suggestions,
    )
