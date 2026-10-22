"""
College offer rules (app/core/placement.py): once a student holds an offer, many Indian
colleges only allow higher-tier on-campus drives, or none at all. Checked deterministically,
never by the LLM, and only for postings that read like a placement-cell notice.
"""
from beanie import PydanticObjectId

from app.agents.eligibility import run_eligibility
from app.agents.schemas import EligibilityDecision
from app.core.placement import HeldOffer, PlacementPolicy, looks_on_campus, parse_ctc_lpa, tier_of
from app.models.opportunity import OpportunityRequirements
from app.models.user import Profile

VIT_LIKE = PlacementPolicy(dream_min_lpa=5.5, super_dream_min_lpa=10, after_offer="higher_tier")
CAMPUS_NOTICE = "Dear students, the Placement Cell is happy to announce a campus drive by {company}. CTC: {ctc}."


def _fail_if_llm_called(*args, **kwargs):
    raise AssertionError("offer rules must never need the LLM")


def test_parse_ctc():
    assert parse_ctc_lpa("CTC: 12 LPA") == 12
    assert parse_ctc_lpa("Package 8-10 LPA") == 10
    assert parse_ctc_lpa("₹6,50,000 per annum") == 6.5
    assert parse_ctc_lpa("Rs. 4.5 lakhs p.a.") == 4.5
    assert parse_ctc_lpa("Stipend Rs 40,000 per month") is None
    assert parse_ctc_lpa(None) is None


def test_tiers_and_campus_detection():
    assert [tier_of(x, VIT_LIKE) for x in (4, 5.5, 9.9, 10, 25)] == ["regular", "dream", "dream", "super_dream", "super_dream"]
    assert looks_on_campus("Training & Placement Cell: pool campus drive for 2027 batch")
    assert looks_on_campus("Register on the placement portal before Friday")
    assert not looks_on_campus("LinkedIn job alert: Software Engineer at Acme, Bengaluru")


async def _check(profile, ctc="12 LPA", text=None, company="Zeta"):
    requirements = OpportunityRequirements(min_cgpa=7.0, compensation=ctc)
    description = text if text is not None else CAMPUS_NOTICE.format(company=company, ctc=ctc)
    result, execution = await run_eligibility(
        requirements, profile, str(PydanticObjectId()), str(PydanticObjectId()), role="SDE", description=description
    )
    assert execution.method == "deterministic"
    return result


def _profile(**kw):
    return Profile(user_id=PydanticObjectId(), cgpa=8.5, branch="CSE", **kw)


async def test_dream_offer_holder_can_sit_super_dream_but_not_dream(client, monkeypatch):
    monkeypatch.setattr("app.agents.eligibility.get_strong_llm", _fail_if_llm_called)
    holder = _profile(placement_policy=VIT_LIKE, current_offer=HeldOffer(company="Infy", ctc_lpa=7))

    allowed = await _check(holder, ctc="12 LPA")
    assert allowed.decision == EligibilityDecision.ELIGIBLE
    assert any("Higher tier" in e for e in allowed.evidence)

    blocked = await _check(holder, ctc="8 LPA")
    assert blocked.decision == EligibilityDecision.NOT_ELIGIBLE
    assert "only lets you sit for higher-tier drives" in blocked.reason and "Infy" in blocked.reason


async def test_one_offer_rule_and_unknown_ctc(client, monkeypatch):
    monkeypatch.setattr("app.agents.eligibility.get_strong_llm", _fail_if_llm_called)
    stop = _profile(placement_policy=PlacementPolicy(after_offer="stop"), current_offer=HeldOffer(company="TCS", ctc_lpa=3.6))
    assert (await _check(stop)).decision == EligibilityDecision.NOT_ELIGIBLE

    holder = _profile(placement_policy=VIT_LIKE, current_offer=HeldOffer(company="Infy", ctc_lpa=7))
    unknown = await _check(holder, ctc=None, text="Placement cell: campus drive by Zeta, details at the venue.")
    assert unknown.decision == EligibilityDecision.UNCERTAIN
    assert any("CTC isn't stated" in m for m in unknown.missing_information)


async def test_rules_never_apply_off_campus_or_without_an_offer(client, monkeypatch):
    monkeypatch.setattr("app.agents.eligibility.get_strong_llm", _fail_if_llm_called)
    holder = _profile(placement_policy=VIT_LIKE, current_offer=HeldOffer(company="Infy", ctc_lpa=7))
    off_campus = await _check(holder, ctc="6 LPA", text="Acme is hiring an SDE. CTC 6 LPA. Apply on our careers page.")
    assert off_campus.decision == EligibilityDecision.ELIGIBLE

    no_offer = await _check(_profile(placement_policy=VIT_LIKE), ctc="6 LPA")
    assert no_offer.decision == EligibilityDecision.ELIGIBLE
    assert any("registering is binding" in e for e in no_offer.evidence)


def test_profile_saves_policy_and_offer(client):
    client.post("/api/auth/register", json={"email": "policy@example.com", "password": "testpass123"})
    token = client.post("/api/auth/login", data={"username": "policy@example.com", "password": "testpass123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    body = {"cgpa": 8.5, "branch": "CSE", "placement_policy": {"dream_min_lpa": 5.5, "super_dream_min_lpa": 10, "after_offer": "higher_tier"},
            "current_offer": {"company": "Infy", "ctc_lpa": 7}}
    assert client.put("/api/profile", json=body, headers=headers).status_code == 200
    got = client.get("/api/profile", headers=headers).json()
    assert got["placement_policy"]["dream_min_lpa"] == 5.5 and got["current_offer"]["company"] == "Infy"
    # Clearing the offer (e.g. after reneging is resolved) works too
    client.put("/api/profile", json={**body, "current_offer": None}, headers=headers)
    assert client.get("/api/profile", headers=headers).json()["current_offer"] is None
