from app.core.scam_check import check_opening

REAL_INTERNSHIP = """Software Engineering Intern, Bengaluru. Stipend Rs 40,000 per month.
Eligibility: B.Tech CSE/IT, CGPA 7.5 and above, no active backlogs.
Apply on careers.example.com before 30 November. There is no registration fee at any stage."""


def codes(result):
    return {f.code for f in result.flags}


def test_a_normal_posting_has_no_flags():
    result = check_opening(REAL_INTERNSHIP, apply_email="campus@example.com")
    assert result.risk == "none" and result.flags == []


def test_fee_and_upi_make_it_high_risk_with_evidence():
    text = "Selected candidates must pay a refundable security deposit of Rs 2,999 via UPI to confirm the internship."
    result = check_opening(text)
    assert result.risk == "high"
    assert {"fee", "upi"} <= codes(result)
    assert "security deposit" in next(f for f in result.flags if f.code == "fee").evidence
    assert "1930" in result.advice


def test_reassurances_are_not_flagged():
    for text in ["No registration fee is charged.", "We will never ask for your OTP or bank details.",
                 "This internship is free of cost, without any training fee."]:
        assert check_opening(text).risk == "none", text


def test_salary_wording_is_not_mistaken_for_a_fee():
    assert check_opening("Pay: Rs 25,000 per month. CTC 6 LPA. Joining bonus included.").risk == "none"


def test_medium_signals():
    assert codes(check_opening("Fill this Google Form: https://forms.gle/abc123 by tonight")) == {"channel"}
    assert codes(check_opening("Guaranteed job after training! Earn Rs 2000 per day from home")) == {"too_good"}
    assert codes(check_opening("Send your Aadhaar card copy with your resume")) == {"id_upfront"}
    result = check_opening("Send your resume", apply_email="hr.infosys.careers@gmail.com")
    assert result.risk == "medium" and codes(result) == {"free_email"}


def test_otp_request_is_high_risk():
    assert check_opening("Share the OTP you receive to complete verification").risk == "high"
