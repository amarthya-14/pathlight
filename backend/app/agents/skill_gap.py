"""
Skill Gap Agent — compares an opportunity's required/preferred skills against the user's
resume content using semantic similarity (Chroma + Gemini embeddings), not exact keyword
matching. This is the one agent in this project that genuinely needs embeddings, per
docs/AI_DESIGN.md's model routing table — moved here to Gate 5 specifically because it
depends on the Chroma infrastructure built alongside it (see docs/ARCHITECTURE.md's Gate
4 scope-correction note).

Classification is a plain distance threshold on embeddings — deliberately NOT an LLM
call per skill, which would be slower, costlier, and less consistent than a threshold
for what is fundamentally a similarity-ranking task, not a reasoning task.
"""
import time

from beanie import PydanticObjectId

from app.agents.schemas import SkillGapResult
from app.models.agent_execution import AgentExecution
from app.retrieval.vector_store import query_resume_chunks, user_has_indexed_resume

# Chroma is configured for cosine distance (0 = identical, 2 = opposite direction).
# These thresholds are a reasonable starting point for gemini-embedding-001, chosen by
# inspection rather than calibrated against a labeled benchmark — this sandbox cannot
# reach the real embedding API to generate one. Building the skill-matching benchmark
# set called for in docs/EVALUATION.md and tuning these against it is real follow-up
# work, not a formality — don't treat these numbers as validated.
MATCH_THRESHOLD = 0.25
WEAK_THRESHOLD = 0.45


async def run_skill_gap(
    user_id: str,
    opportunity_id: str,
    required_skills: list[str],
    preferred_skills: list[str],
) -> tuple[SkillGapResult, AgentExecution]:
    start = time.monotonic()

    all_skills = list(required_skills) + list(preferred_skills)
    has_resume = await user_has_indexed_resume(user_id)

    matched: list[str] = []
    weak: list[str] = []
    missing: list[str] = []

    if all_skills and has_resume:
        for skill in all_skills:
            hits = await query_resume_chunks(user_id, skill, n_results=1)
            if not hits:
                missing.append(skill)
                continue
            _chunk_text, distance = hits[0]
            if distance <= MATCH_THRESHOLD:
                matched.append(skill)
            elif distance <= WEAK_THRESHOLD:
                weak.append(skill)
            else:
                missing.append(skill)
    elif all_skills and not has_resume:
        # No resume indexed at all — every skill is "missing" for a different reason
        # than "we checked and found no evidence." Still returned as `missing` (the
        # schema has no separate state for this), but AgentExecution's input_summary
        # records has_resume=False so this is distinguishable in the audit log, and the
        # pipeline layer (app/graphs/opportunity_pipeline.py) surfaces it to the caller
        # via a separate note rather than silently presenting it as a real skill gap.
        missing = list(all_skills)

    result = SkillGapResult(matched=matched, weak=weak, missing=missing)

    latency_ms = (time.monotonic() - start) * 1000
    execution = AgentExecution(
        user_id=PydanticObjectId(user_id),
        agent_name="skill_gap",
        method="embeddings",
        input_summary=(
            f"required={required_skills}, preferred={preferred_skills}, has_resume={has_resume}"
        ),
        output=result.model_dump(mode="json"),
        status="success",
        latency_ms=latency_ms,
        opportunity_id=PydanticObjectId(opportunity_id),
    )
    await execution.insert()

    return result, execution
