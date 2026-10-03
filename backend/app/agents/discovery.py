"""
Discovery Agent — extracts structured opportunity data from raw source text (a pasted
job description, a forwarded placement email, or text read from a Document via the
Filesystem MCP tool).

Extraction only — this agent does not decide eligibility (app/agents/eligibility.py) or
touch the database directly; the LangGraph pipeline (app/graphs/opportunity_pipeline.py)
that calls this is responsible for turning the result into Company/Opportunity records.
"""
import time

from beanie import PydanticObjectId
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm_client import get_small_llm
from app.agents.schemas import ExtractedOpportunities, ExtractedOpportunity
from app.models.agent_execution import AgentExecution

DISCOVERY_SYSTEM_PROMPT = """You are an information-extraction system for a career \
intelligence platform. Extract ONLY information explicitly present in the text you are \
given. Do NOT invent, infer, guess, or fill in values that are not stated in the text — \
leave a field null or empty if it is not mentioned. In particular:
- Do not assume a CGPA or branch requirement exists unless the text states one.
- Do not invent compensation figures.
- If eligibility is described in qualitative, non-numeric terms (e.g. "strong problem \
solving skills preferred"), put that text verbatim in raw_eligibility_text rather than \
trying to force it into a structured field it doesn't fit.
- min_experience_years: the minimum years of work experience required, as a number \
("7+ years" -> 7, "3-5 years" -> 3, "0-2 years", "freshers" or "2025 graduates" -> 0). \
Leave it null if experience isn't mentioned — a job-alert digest that only lists title, \
company and location does NOT state an experience requirement.
- apply_email / application_url: set ONLY if the text literally contains an email \
address or URL for submitting applications. Never construct one from the company name \
(e.g. do not invent careers@company.com). Job-alert digests usually contain a link to the \
posting — that goes in application_url, not apply_email."""


async def run_discovery(raw_text: str, source: str, user_id: str) -> tuple[ExtractedOpportunity, AgentExecution]:
    """
    Runs the Discovery Agent once (no internal retry loop here — the pipeline layer
    decides retry policy, see app/graphs/opportunity_pipeline.py). Always logs an
    AgentExecution, including on failure, so a failed run is inspectable rather than
    silently lost.
    """
    start = time.monotonic()
    llm = get_small_llm()
    structured_llm = llm.with_structured_output(ExtractedOpportunity)

    result: ExtractedOpportunity | None = None
    status = "success"
    error_message: str | None = None

    try:
        result = await structured_llm.ainvoke(
            [
                SystemMessage(content=DISCOVERY_SYSTEM_PROMPT),
                HumanMessage(content=raw_text),
            ]
        )
    except Exception as e:
        status = "error"
        error_message = str(e)

    latency_ms = (time.monotonic() - start) * 1000

    execution = AgentExecution(
        user_id=PydanticObjectId(user_id),
        agent_name="discovery",
        method="llm",
        input_summary=raw_text[:500],
        output=result.model_dump(mode="json") if result else None,
        status=status,
        error_message=error_message,
        latency_ms=latency_ms,
    )
    await execution.insert()

    if status == "error" or result is None:
        raise RuntimeError(f"Discovery agent failed: {error_message}")

    return result, execution


MAX_JOBS_PER_EMAIL = 6

DIGEST_ADDENDUM = """

This text is a job-alert EMAIL. It may list SEVERAL different jobs (a LinkedIn or \
Naukri digest). Return every distinct job posting it lists as its own entry in \
`opportunities` (at most {max_jobs}, in the order they appear), each with its own company, \
role and posting link (application_url). Skip ads, "people also viewed", course \
promotions and anything that isn't a specific job opening. If it lists no job at all, \
return an empty list."""


async def run_digest_discovery(raw_text: str, source: str, user_id: str) -> list[ExtractedOpportunity]:
    """Discovery for alert emails: one email -> every job it lists. Logs one
    AgentExecution, raises RuntimeError on LLM failure (the caller decides retries)."""
    start = time.monotonic()
    structured_llm = get_small_llm().with_structured_output(ExtractedOpportunities)
    result = None
    error_message = None
    try:
        result = await structured_llm.ainvoke(
            [
                SystemMessage(content=DISCOVERY_SYSTEM_PROMPT + DIGEST_ADDENDUM.format(max_jobs=MAX_JOBS_PER_EMAIL)),
                HumanMessage(content=raw_text),
            ]
        )
    except Exception as e:
        error_message = str(e)

    # Tolerate a model (or test double) that answers with a single posting.
    if isinstance(result, ExtractedOpportunity):
        jobs = [result]
    elif isinstance(result, ExtractedOpportunities):
        jobs = [j for j in result.opportunities if j.company_name.strip() and j.role.strip()]
    else:
        jobs = []

    await AgentExecution(
        user_id=PydanticObjectId(user_id),
        agent_name="discovery",
        method="llm",
        input_summary=raw_text[:500],
        output={"opportunities": [j.model_dump(mode="json") for j in jobs]} if result is not None else None,
        status="error" if result is None else "success",
        error_message=error_message,
        latency_ms=(time.monotonic() - start) * 1000,
    ).insert()

    if result is None:
        raise RuntimeError(f"Discovery agent failed: {error_message}")
    # Same posting twice in one digest ("Top pick" + list) — keep the first.
    seen, unique = set(), []
    for job in jobs:
        key = (job.company_name.strip().lower(), job.role.strip().lower())
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique[:MAX_JOBS_PER_EMAIL]
