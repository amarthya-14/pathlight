"""
Scam check for openings — deterministic red-flag rules, no LLM.

Fake internships and jobs aimed at Indian students follow a recognisable pattern, which
AICTE's internship-portal rules (updated 15 Sep 2026) list as red flags: any fee to apply or
train, payment by UPI/QR, applications through Google Forms or WhatsApp, lookalike or free
email domains, and requests for Aadhaar or bank details. Each flag carries the exact text it
matched, so the student sees why — a warning without evidence is just noise.

Never blocks anything on its own: high risk only adds an explicit acknowledgement step before
the student approves sending an application (see routes/applications.py::review_application).
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

Risk = Literal["none", "medium", "high"]


class ScamFlag(BaseModel):
    code: str
    label: str
    severity: Literal["medium", "high"]
    evidence: str  # the matched text, with a little context


class ScamCheck(BaseModel):
    risk: Risk
    flags: list[ScamFlag] = Field(default_factory=list)
    advice: str = ""


# (code, label, severity, pattern). Patterns are case-insensitive.
_RULES: list[tuple[str, str, str, str]] = [
    (
        "fee",
        "Asks for a fee or deposit",
        "high",
        r"\b(registration|training|security|processing|enrol+ment|certificate|certification|kit|onboarding|application|"
        r"joining|refundable|interview|verification)\s+(fee|fees|charges?|deposit|amount)\b"
        r"|\b(fee|fees|deposit)\s+of\s+(rs\.?|inr|₹)"
        r"|\bpay\s+(rs\.?|inr|₹)\s*\d[\d,]*\s*(/-)?\s*(to|for|as|towards)\b",
    ),
    ("upi", "Payment by UPI, QR code or wallet", "high", r"\bupi\b|\bqr\s*code\b|\b(paytm|gpay|google\s*pay|phone\s*pe)\b"),
    (
        "otp_bank",
        "Asks for an OTP or bank/card details",
        "high",
        r"\botp\b|\bbank\s+(account|details|passbook|statement)\b|\b(debit|credit|atm)\s+card\b|\bcvv\b",
    ),
    ("id_upfront", "Asks for Aadhaar or PAN before any interview", "medium", r"\baadha+r\b|\bpan\s+(card|number)\b"),
    (
        "channel",
        "Applications through Google Forms, WhatsApp or Telegram",
        "medium",
        r"forms\.gle|docs\.google\.com/forms|\bwa\.me\b|chat\.whatsapp\.com|api\.whatsapp\.com|\bt\.me/|\btelegram\b",
    ),
    (
        "too_good",
        "Promises that real employers don't make",
        "medium",
        r"guaranteed\s+(job|placement|offer|selection|internship)|100\s*%\s+(job|placement)(\s+guarantee)?"
        r"|\bno\s+interview\b|\bearn\s+(up\s+to\s+)?(rs\.?|inr|₹)\s*\d[\d,]*\s*(per|/|a|every)\s*(day|week|hour)\b",
    ),
]
_COMPILED = [(code, label, sev, re.compile(p, re.I)) for code, label, sev, p in _RULES]

# "There is no registration fee", "free of cost", "we never ask for OTP" — reassurance, not a request.
_NEGATION = re.compile(r"\b(no|not|never|without|zero|free\s+of|won'?t|will\s+not|do\s+not|don'?t|doesn'?t)\b[^.]{0,30}$", re.I)

FREE_EMAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "ymail.com", "outlook.com", "hotmail.com",
    "live.com", "rediffmail.com", "proton.me", "protonmail.com", "icloud.com", "aol.com",
}

ADVICE = {
    "high": (
        "Genuine employers and colleges never charge students to apply, train or get an offer letter, and never ask "
        "for an OTP or bank details. Don't pay or share these. If you've already paid, report it at "
        "cybercrime.gov.in or call 1930."
    ),
    "medium": (
        "Not proof of a scam, but worth checking: find the opening on the company's own careers page or confirm it "
        "with your placement cell before sharing documents."
    ),
}


def _snippet(text: str, start: int, end: int) -> str:
    a, b = max(0, start - 40), min(len(text), end + 40)
    return ("…" if a else "") + " ".join(text[a:b].split()) + ("…" if b < len(text) else "")


def check_opening(text: str | None, apply_email: str | None = None) -> ScamCheck:
    """Red flags in a posting's text and contact details. Each rule reports at most once."""
    text = text or ""
    flags: list[ScamFlag] = []
    for code, label, severity, pattern in _COMPILED:
        for m in pattern.finditer(text):
            if _NEGATION.search(text[max(0, m.start() - 40) : m.start()]):
                continue
            flags.append(ScamFlag(code=code, label=label, severity=severity, evidence=_snippet(text, m.start(), m.end())))
            break
    domain = apply_email.rsplit("@", 1)[-1].lower().strip() if apply_email and "@" in apply_email else None
    if domain in FREE_EMAIL:
        flags.append(
            ScamFlag(
                code="free_email",
                label="Applications go to a personal email address, not a company domain",
                severity="medium",
                evidence=apply_email,
            )
        )
    risk: Risk = "high" if any(f.severity == "high" for f in flags) else "medium" if flags else "none"
    return ScamCheck(risk=risk, flags=flags, advice=ADVICE.get(risk, ""))
