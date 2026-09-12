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
from app.agents.schemas import ExtractedOpportunity
from app.models.agent_execution import AgentExecution

DISCOVERY_SYSTEM_PROMPT = """You are an information-extraction system for a career \
intelligence platform. Extract ONLY information explicitly present in the text you are \
given. Do NOT invent, infer, guess, or fill in values that are not stated in the text — \
leave a field null or empty if it is not mentioned. In particular:
- Do not assume a CGPA or branch requirement exists unless the text states one.
- Do not invent compensation figures.
- If eligibility is described in qualitative, non-numeric terms (e.g. "strong problem \
solving skills preferred"), put that text verbatim in raw_eligibility_text rather than \
trying to force it into a structured field it doesn't fit."""


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
