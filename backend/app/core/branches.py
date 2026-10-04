"""
Branch names — one student's "CSE" is a posting's "B.Tech CSE", "Computer Science &
Engineering", "CS/IT" or "Circuit branches". Eligibility compares canonical codes, never
raw strings.

branch_codes() reads any spelling into a set of codes. A specialisation counts as its
parent too ("CSE (AI & ML)" -> {"aiml", "cse"}), so a CSE-AIML student meets a "CSE"
requirement, but a plain CSE student doesn't meet an "AI & ML only" one.
"""
import re

# (code, pattern) — checked against a lowercased, punctuation-normalised string.
_BRANCHES: list[tuple[str, str]] = [
    ("aiml", r"\bai\s*(?:&|and|/)?\s*ml\b|artificial intelligence (?:and|&) machine learning|\baiml\b|\bcsm\b"),
    ("aids", r"\bai\s*(?:&|and|/)?\s*ds\b|artificial intelligence (?:and|&) data science|\baids\b"),
    ("ds", r"\bdata science\b|\bcsd\b"),
    ("cyber", r"\bcyber ?security\b|\bcsc\b|\bcys\b"),
    ("iot", r"\biot\b|internet of things"),
    ("cse", r"\bcse\b|\bcs\b|\bcomputer (?:science|engineering)\b|\bcomputer sc\b|\bcomp(?:uter)? sci\b|\bcomps?\b|\bcoe\b|\bcsit\b"),
    ("it", r"\bit\b|\binformation technology\b|\bise\b|\binformation science\b|\bcsit\b"),
    ("mca", r"\bmca\b|master of computer applications?"),
    ("bca", r"\bbca\b|bachelor of computer applications?"),
    ("ece", r"\bece\b|\bec\b|\belectronics (?:and|&)? ?communications?\b|\betc\b|\bentc\b|\bextc\b|(?<!electrical and )(?<!electrical & )\belectronics\b(?! (?:and|&) instrumentation)"),
    ("eee", r"\beee\b|\bee\b|\belectrical (?:and|&)? ?electronics?\b|\belectrical\b"),
    ("eie", r"\beie\b|\bei\b|\bice\b|\binstrumentation\b"),
    ("me", r"\bme\b|\bmech\w*\b"),
    ("ce", r"\bce\b|\bcivil\b"),
    ("chem", r"\bche?\b|\bchemical\b"),
    ("bio", r"\bbiotech\w*\b|\bbt\b|\bbio ?technology\b"),
    ("aero", r"\baero\w*\b"),
]
_PARENT = {"aiml": {"cse"}, "aids": {"cse"}, "ds": {"cse"}, "cyber": {"cse"}, "iot": {"cse"}}
# Postings that name a group rather than branches.
_GROUPS: list[tuple[str, set[str]]] = [
    (r"\bcircuit\b", {"cse", "it", "ece", "eee", "eie", "aiml", "aids", "ds", "cyber", "iot"}),
    (r"\bcs ?(?:and|&|/) ?allied\b|\ballied (?:cs|cse|branches)\b|\bcomputer related\b|\bcs related\b", {"cse", "it", "aiml", "aids", "ds", "cyber", "iot", "mca"}),
]
_ANY = re.compile(r"\b(all|any)\b.*\b(branch|branches|stream|streams|discipline|disciplines|engineering)\b|\ball streams\b|\bno branch\b")
# Degrees alone ("B.Tech", "BE") don't say which branch.
_DEGREE = re.compile(r"\b(b ?tech|b ?e|m ?tech|m ?e|b ?sc|m ?sc|bachelor\w*|master\w*|degree|engineering|graduates?|in|of|and|or|with|&|hons?)\b")


def _clean(text: str) -> str:
    t = text.lower().replace("&", " & ")
    t = re.sub(r"[.()\[\],;:_\-]+", " ", t)
    t = t.replace("/", " / ")
    return re.sub(r"\s+", " ", t).strip()


def branch_codes(text: str, student: bool = False) -> set[str] | None:
    """Canonical codes for one branch string; None = any branch / degree-only (no branch
    restriction stated); empty set = couldn't read it.

    student=True adds parents (a CSE-AIML student is also CSE). On a posting's side a
    specialisation is just that: "CSE (AI & ML)" means the AIML branch, not all of CSE —
    unless the entry is itself a list ("CSE, AI & ML")."""
    t = _clean(text or "")
    if not t or _ANY.search(t):
        return None
    codes: set[str] = set()
    for pattern, group in _GROUPS:
        if re.search(pattern, t):
            codes |= group
    for code, pattern in _BRANCHES:
        if re.search(pattern, t):
            codes.add(code)
    specialisations = {c for c in codes if c in _PARENT}
    if student:
        for code in specialisations:
            codes |= _PARENT[code]
    elif specialisations and not re.search(r",|/|\bor\b", t):
        codes -= {"cse"}
    if not codes and not _DEGREE.sub(" ", t).strip(" /&"):
        return None  # just "B.Tech" / "BE graduates"
    return codes


def branch_allowed(student_branch: str, allowed: list[str]) -> bool | None:
    """True/False when it's clear, None when a listed branch or the student's own entry
    can't be read (eligibility then says "uncertain" instead of a wrong hard fail)."""
    student = branch_codes(student_branch, student=True)
    if not student:
        return None
    unreadable = False
    for entry in allowed:
        wanted = branch_codes(entry)
        if wanted is None:
            return True
        if not wanted:
            unreadable = True
            continue
        if student & wanted:
            return True
    return None if unreadable else False
