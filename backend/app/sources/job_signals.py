"""
What a posting is and who it's for — read from its title and description, deterministically.

- family:          which field the role belongs to (backend, frontend, ml_ai, data_analyst, ...)
                   so a backend student never sees "Video Editor Intern" or "Account Manager".
- min_experience:  the minimum years of experience the description asks for ("3+ years",
                   "2-4 years of experience", "minimum 5 years") — the root cause of
                   "LinkedIn asks me for experience I don't have" is applying to these.
- entry_level:     explicit fresher signals (intern, new grad, 0-1 years, "freshers").
- batch_years:     graduation batches the posting is limited to ("2025/2026 batch").

Used at fetch time (stored on JobListing) and for a user's own target roles/resume, so the
same classifier decides both sides of "is this job in my field?".
"""
import re

# Order matters: the first family whose pattern matches the title wins.
_FAMILY_RULES: list[tuple[str, re.Pattern]] = [
    ("non_tech", re.compile(
        r"\b(sales|account (?:manager|executive|director)|business development|bdr|sdr|marketing|growth marketer|"
        r"recruit\w*|talent|human resources|\bhr\b|people partner|payroll|finance|financial|accountant|accounting|"
        r"audit\w*|tax|legal|counsel|compliance officer|procurement|purchase|admin\w*|facilit\w*|office manager|"
        r"executive assistant|category manager|merchandis\w*|customer success|customer support|customer service|"
        r"support specialist|operations (?:executive|associate|manager|specialist)|content (?:writer|creator|strategist)|"
        r"copywriter|video editor|graphic designer|social media|public relations|community manager|"
        r"field (?:sales|executive)|delivery (?:partner|executive)|store manager|key account|"
        r"evaluator|annotator|rater|linguist|translator|transcri\w*|data labell?er|moderator)\b", re.I)),
    ("support_eng", re.compile(
        r"\b(support engineer|solutions? engineer|implementation engineer|technical consultant|sales engineer|"
        r"customer (?:experience |success )?engineer|escalation engineer|technical account manager)\b", re.I)),
    ("ml_ai", re.compile(
        r"\b(machine learning|\bml\b|\bai\b|artificial intelligence|deep learning|\bnlp\b|computer vision|\bllm\w*|"
        r"genai|generative ai|applied scientist|research scientist|ai engineer|mlops|data scientist|data science)\b", re.I)),
    ("data_eng", re.compile(r"\b(data engineer\w*|analytics engineer|etl|big data|data platform|data infrastructure)\b", re.I)),
    ("data_analyst", re.compile(r"\b(data analyst|business analyst|analytics|\bbi\b|business intelligence|insights analyst|product analyst)\b", re.I)),
    ("security", re.compile(r"\b(security|secops|appsec|infosec|penetration|threat|soc analyst|cyber)\b", re.I)),
    ("devops", re.compile(r"\b(devops|sre|site reliability|cloud engineer|infrastructure|platform engineer|kubernetes|systems engineer|network engineer)\b", re.I)),
    ("qa", re.compile(r"\b(qa|quality assurance|test(?:ing)? engineer|sdet|automation test|tester|software engineer in test)\b", re.I)),
    ("mobile", re.compile(r"\b(android|ios|mobile|flutter|react native)\b", re.I)),
    ("frontend", re.compile(r"\b(front[- ]?end|frontend|ui engineer|ui developer|web developer|react developer)\b", re.I)),
    ("fullstack", re.compile(r"\b(full[- ]?stack)\b", re.I)),
    ("backend", re.compile(r"\b(back[- ]?end|backend|api engineer|server[- ]side|java developer|python developer|golang|node(?:\.js)? developer)\b", re.I)),
    ("product", re.compile(r"\b(product manager|product management|program manager|project manager|scrum master|product owner)\b", re.I)),
    ("design", re.compile(r"\b(designer|ux|ui/ux|product design)\b", re.I)),
    ("software", re.compile(r"\b(software|sde|swe|developer|programmer|engineer|engineering)\b", re.I)),
]

# Which job families someone in family X would want to see. "software" (a generic SWE
# title) fits every engineering family; specialised roles only fit their own kind.
_COMPATIBLE: dict[str, set[str]] = {
    "backend": {"backend", "software", "fullstack"},
    "frontend": {"frontend", "software", "fullstack"},
    "fullstack": {"fullstack", "software", "backend", "frontend"},
    "software": {"software", "backend", "frontend", "fullstack", "mobile"},
    "mobile": {"mobile", "software"},
    "ml_ai": {"ml_ai", "software", "data_eng"},
    "data_eng": {"data_eng", "software", "backend", "ml_ai"},
    "data_analyst": {"data_analyst", "data_eng"},
    "devops": {"devops", "software", "backend"},
    "security": {"security", "devops"},
    "qa": {"qa", "software"},
    "product": {"product"},
    "design": {"design"},
    "support_eng": {"support_eng"},
    "non_tech": set(),
}

TECH_FAMILIES = {f for f in _COMPATIBLE if f not in {"non_tech", "product", "design"}}


def classify_title(title: str) -> str:
    """The family of one job title (or target role)."""
    t = title or ""
    # "Software Engineer, Sales Tools" is engineering, not sales: engineering words win
    # over the non-tech list.
    engineering = re.search(r"\b(engineer|developer|sde|swe|scientist|programmer)\b", t, re.I)
    for family, pattern in _FAMILY_RULES:
        if family == "non_tech" and engineering:
            continue
        if pattern.search(t):
            return family
    return "other"


def compatible(user_families: set[str], job_family: str) -> int:
    """2 = same family, 1 = compatible (e.g. backend student, generic SWE role), 0 = no."""
    if not user_families:
        return 1 if job_family in TECH_FAMILIES or job_family == "software" else 0
    if job_family in user_families:
        return 2
    return 1 if any(job_family in _COMPATIBLE.get(f, set()) for f in user_families) else 0


# Skills that say which engineering field a RESUME is in, when the user hasn't named roles.
_RESUME_FAMILY_SKILLS = {
    "backend": ["Spring Boot", "Django", "Flask", "FastAPI", "Node.js", "Express", "REST APIs", "Microservices", "Java", "Golang"],
    "frontend": ["React", "Angular", "Vue", "Next.js", "TypeScript", "HTML", "CSS"],
    "ml_ai": ["Machine Learning", "Deep Learning", "PyTorch", "TensorFlow", "NLP", "LLM", "LangChain", "LangGraph", "Generative AI", "scikit-learn"],
    "data_analyst": ["Power BI", "Tableau", "Excel", "Statistics"],
    "data_eng": ["Spark", "Airflow", "Kafka", "Hadoop", "ETL", "Snowflake", "dbt"],
    "devops": ["Kubernetes", "Terraform", "Ansible", "Jenkins", "CI/CD"],
    "mobile": ["Android", "iOS", "Flutter", "React Native", "Kotlin", "Swift"],
    "qa": ["Selenium", "Cypress", "Testing", "Automation"],
}


def resume_families(skills: list[str]) -> set[str]:
    have = set(skills)
    families = {f for f, signals in _RESUME_FAMILY_SKILLS.items() if len(have & set(signals)) >= 2}
    if {"backend", "frontend"} <= families:
        families.add("fullstack")
    if families & {"backend", "frontend", "fullstack", "mobile"}:
        families.add("software")
    return families


def user_families(target_roles: list[str], skills: list[str]) -> set[str]:
    """Target roles are what the student asked for; the resume says what they can do. Both
    count — a backend student who also lists 'AI Engineer' sees both kinds of roles."""
    families = {classify_title(r) for r in target_roles} - {"other", "non_tech"}
    families |= resume_families(skills)
    if families & {"backend", "frontend", "fullstack"}:
        families.add("software")
    return families


# ── Experience / level ─────────────────────────────────────────────────────────

_NUM = r"(\d{1,2}(?:\.\d)?)"
_EXP_PATTERNS = [
    # "3+ years of experience", "3-5 years experience", "2 to 4 yrs of relevant experience"
    re.compile(rf"{_NUM}\s*\+?\s*(?:-|–|to)?\s*(?:\d{{1,2}}\s*\+?\s*)?(?:years?|yrs?)\b[^.\n]{{0,40}}?\bexperience", re.I),
    # "experience: 3-5 years", "experience of 4+ years"
    re.compile(rf"\bexperience\b[^.\n]{{0,25}}?{_NUM}\s*\+?\s*(?:-|–|to)?\s*(?:\d{{1,2}}\s*)?(?:years?|yrs?)\b", re.I),
    # "minimum 5 years", "at least 2 years"
    re.compile(rf"\b(?:minimum|min\.?|at least|atleast)\s*(?:of\s*)?{_NUM}\s*(?:years?|yrs?)\b", re.I),
]
_ENTRY = re.compile(
    r"\b(fresher|freshers|new grad\w*|recent grad\w*|graduate (?:engineer|trainee|program)|entry[- ]level|"
    r"early[- ]career|campus|intern(?:ship)?|trainee|0\s*(?:-|–|to)\s*[12]\s*(?:years?|yrs?)|no (?:prior )?experience required)\b",
    re.I,
)
_TITLE_ENTRY = re.compile(r"\b(intern(?:ship)?|graduate|grad|fresher|junior|jr\.?|trainee|apprentice|associate|campus|entry)\b", re.I)
_TITLE_SENIOR = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|manager|director|head|vp|vice president|architect|distinguished)\b"
    r"|\b(engineer|developer|sde|swe|analyst|scientist)\s*(ii|iii|iv|[2-9])\b",
    re.I,
)
_BATCH = re.compile(r"\b(20[2-3]\d)\s*(?:/|,|&|and|or|-)?\s*(20[2-3]\d)?\s*(?:batch|pass[- ]?outs?|graduat\w*|grads)\b", re.I)


def min_experience(text: str) -> float | None:
    """Smallest 'minimum years' stated near the word 'experience' (the headline
    requirement; a JD asking "5+ years, of which 2 in Kafka" needs 5... but also says 5
    first, and headline requirements come first). Ignores implausible numbers."""
    found: list[float] = []
    for pattern in _EXP_PATTERNS:
        for m in pattern.finditer(text or ""):
            value = float(m.group(1))
            if 0 <= value <= 20:
                found.append((m.start(), value))
    if not found:
        return None
    found.sort()
    return found[0][1]


def is_entry_level(title: str, description: str) -> bool:
    return bool(_TITLE_ENTRY.search(title or "")) or bool(_ENTRY.search((description or "")[:4000]))


def is_senior_title(title: str) -> bool:
    return bool(_TITLE_SENIOR.search(title or ""))


def batch_years(text: str) -> list[int]:
    years: set[int] = set()
    for m in _BATCH.finditer(text or ""):
        for g in m.groups():
            if g:
                years.add(int(g))
    return sorted(years)


def signals(title: str, description: str) -> dict:
    text = f"{title}\n{description or ''}"
    exp = min_experience(text)
    if exp is None:
        # Titles sometimes carry it: "Product Manager | Experience : 5-8 yrs".
        m = re.search(rf"{_NUM}\s*(?:\+|[-–to ]+\s*\d{{1,2}})?\s*(?:yrs|years|yr)\b", title or "", re.I)
        exp = float(m.group(1)) if m else None
    return {
        "family": classify_title(title),
        "min_experience": exp,
        "entry_level": is_entry_level(title, description),
        "senior": is_senior_title(title),
        "batch_years": batch_years(text),
    }
