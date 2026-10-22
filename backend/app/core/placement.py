"""
Campus placement offer rules — deterministic, per the student's own college.

Indian colleges limit who can sit for on-campus drives once a student holds an offer: a
"dream" offer (e.g. above ₹5.5 LPA at VIT) may only allow "super dream" drives after it, and
some colleges stop students after one offer altogether. The thresholds differ by college and
change between years, so they are data the student enters (Profile.placement_policy), never
hard-coded. Off-campus openings aren't governed by these rules, so they only apply to postings
that read like a placement-cell notice.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

AfterOffer = Literal["any", "higher_tier", "stop"]
Tier = Literal["regular", "dream", "super_dream"]
TIER_RANK = {"regular": 0, "dream": 1, "super_dream": 2}
TIER_LABEL = {"regular": "regular", "dream": "dream", "super_dream": "super dream"}


class PlacementPolicy(BaseModel):
    dream_min_lpa: float | None = Field(default=None, ge=0, le=200)
    super_dream_min_lpa: float | None = Field(default=None, ge=0, le=500)
    # After an offer: "any" = no restriction, "higher_tier" = only drives in a higher tier,
    # "stop" = one offer and you're out of placements.
    after_offer: AfterOffer = "higher_tier"


class HeldOffer(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    ctc_lpa: float = Field(ge=0, le=500)


_CAMPUS = re.compile(
    r"placement\s+(cell|office|department|portal)|training\s*(&|and)\s*placement|\bT\s*&\s*P\b|\bTPO\b|"
    r"campus\s+(drive|recruitment|placement|hiring)|on[- ]campus|pool\s+campus|\bCDC\b|career\s+development\s+cent(re|er)",
    re.I,
)


def looks_on_campus(text: str | None) -> bool:
    return bool(text and _CAMPUS.search(text))


_LPA = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(?:\d+(?:\.\d+)?)?\s*(?:lpa\b|l\.p\.a|lakhs?\b|lacs?\b)", re.I)
_ANNUAL_RUPEES = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]{6,})\s*(?:/-)?\s*(?:per\s+annum|p\.?\s?a\.?\b|/\s*(?:annum|year)|per\s+year|annually)", re.I)


def parse_ctc_lpa(text: str | None) -> float | None:
    """Annual CTC in lakhs from text like "CTC 12 LPA", "₹6,00,000 per annum" or "8-10 LPA"
    (the top of a range counts). Monthly stipends aren't annual CTC and return None."""
    if not text:
        return None
    values = [float(m.group(1)) for m in _LPA.finditer(text)]
    ranges = re.findall(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:lpa\b|lakhs?\b)", text, re.I)
    values += [float(hi) for _lo, hi in ranges]
    values += [int(m.group(1).replace(",", "")) / 100000 for m in _ANNUAL_RUPEES.finditer(text)]
    values = [v for v in values if 0 < v < 500]
    return max(values) if values else None


def tier_of(ctc_lpa: float, policy: PlacementPolicy) -> Tier:
    if policy.super_dream_min_lpa is not None and ctc_lpa >= policy.super_dream_min_lpa:
        return "super_dream"
    if policy.dream_min_lpa is not None and ctc_lpa >= policy.dream_min_lpa:
        return "dream"
    return "regular"


def check_offer_rules(
    policy: PlacementPolicy | None, offer: HeldOffer | None, compensation: str | None, text: str | None
) -> tuple[list[str], list[str], str | None]:
    """(evidence, missing information, reason it's not allowed or None) for an on-campus drive."""
    if policy is None or not looks_on_campus(text):
        return [], [], None
    evidence = ["Campus drive: at many colleges registering is binding — if you're selected you must accept, "
                "and rejecting can bar you from later drives. Check before you register."]
    if offer is None or policy.after_offer == "any":
        return evidence, [], None
    held = tier_of(offer.ctc_lpa, policy)
    held_desc = f"your {TIER_LABEL[held]} offer from {offer.company} (₹{offer.ctc_lpa:g} LPA)"
    if policy.after_offer == "stop":
        return evidence, [], f"Your college allows one offer per student, and you hold {held_desc}."
    ctc = parse_ctc_lpa(compensation) or parse_ctc_lpa(text)
    if ctc is None:
        return evidence, [f"This drive's CTC isn't stated — needed to check it against {held_desc}"], None
    drive = tier_of(ctc, policy)
    if TIER_RANK[drive] <= TIER_RANK[held]:
        return evidence, [], (
            f"With {held_desc}, your college only lets you sit for higher-tier drives; "
            f"this one (₹{ctc:g} LPA) is {TIER_LABEL[drive]}."
        )
    return evidence + [f"Higher tier than {held_desc}: this drive is {TIER_LABEL[drive]} (₹{ctc:g} LPA)"], [], None
