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
import re
import time

from beanie import PydanticObjectId

from app.agents.schemas import SkillGapResult
from app.mcp.github_client import mcp_search_github_evidence
from app.models.agent_execution import AgentExecution
from app.retrieval.vector_store import query_resume_chunks, user_has_indexed_resume

# Chroma is configured for cosine distance (0 = identical, 2 = opposite direction).
#
# Gate 6 real-API smoke test (docs/ARCHITECTURE.md §15 has the full writeup): the
# original 0.25/0.45 thresholds were chosen by inspection against a fake embedder and
# turned out to be badly wrong against real gemini-embedding-001 output. A real resume
# with clear, explicit skills (Python/FastAPI/PostgreSQL/AWS present; Kubernetes/Rust/
# Swift explicitly disclaimed: "No experience with Kubernetes, Rust, or ... Swift")
# produced these single-skill-vs-resume-chunk cosine distances:
#   FastAPI 0.319, AWS 0.341, Python 0.363, Django 0.358, PostgreSQL 0.375,
#   Machine Learning 0.376, Swift 0.375, Kubernetes 0.352, Rust 0.390,
#   Photography (unrelated control) 0.442
# Two real findings, not one:
#   1. Genuine matches and genuine non-matches for a topically-similar (backend
#      engineering) resume overlap almost completely in the 0.32-0.39 band — a single
#      global threshold cannot cleanly separate them. Thresholds below were a rough
#      recalibration using that one real example as a directional signal, NOT a
#      validated fit — explicitly flagged as needing the labeled benchmark set
#      docs/EVALUATION.md called for (Gate 9), not more manual tweaking against one resume.
#   2. Embedding distance alone can't tell "no experience with Kubernetes" apart from
#      "experienced with Kubernetes" — both chunks contain the word "Kubernetes" and
#      score similarly close. This is a structural gap, not a threshold problem, so it's
#      fixed separately below with a deterministic negation check on the actual matched
#      chunk text (see _skill_explicitly_negated), not by moving the numbers around.
#
# Gate 9 evaluation harness (backend/eval/, see docs/EVALUATION.md): ran the above
# real-API smoke test's directional signal through an actual hand-labeled benchmark for
# the first time — 2 resumes (backend-focused and frontend-focused domains), 18 labeled
# skills. Result confirmed finding #1 above is real, not a one-resume fluke: 7 of 8
# genuinely-matched skills fell below the old MATCH_THRESHOLD=0.34 into "weak"
# (distances 0.325-0.368), while two genuinely "weak" skills (GraphQL 0.334, Next.js
# 0.333) scored BELOW several genuine matches — matched/weak distance ranges truly
# interleave across resume domains, so no single threshold can perfectly separate them.
# The matched-vs-not-matched split is much cleaner: a sweep over the same 18 labeled
# skills found MATCH_THRESHOLD=0.38 as the single best split (raises 3-way classification
# accuracy on this benchmark from 7/18 to 12/18 — see eval/report.md). Moved
# MATCH_THRESHOLD to 0.38 on that evidence. WEAK_THRESHOLD is left at 0.42: nothing in
# this run's sweep contradicts it, and n=2 resumes is still too small to recalibrate it
# with any confidence — grow the benchmark before touching it again.
MATCH_THRESHOLD = 0.38
WEAK_THRESHOLD = 0.42

_NEGATION_CUES = r"(?:no|not|without|never|none|lacks?|lacking)"


def _skill_explicitly_negated(chunk_text: str, skill: str) -> bool:
    """
    Deterministic guard on top of the embedding distance, not a replacement for it:
    catches the specific failure the Gate 6 smoke test found (see the threshold comment
    above) where a resume line disclaiming a skill ("no experience with Kubernetes")
    embeds just as close to the skill name as a line claiming it. Only overrides a
    matched/weak classification to `missing` when the actual chunk text that produced
    that distance contains an explicit negation cue within a few words of the skill name
    — this is not general semantic negation detection, just a targeted fix for the
    concrete pattern observed.
    """
    skill = skill.strip()
    if not skill:
        return False
    pattern = re.compile(
        rf"\b{_NEGATION_CUES}\b(?:\W+\w+){{0,6}}?\W+{re.escape(skill)}\b",
        re.IGNORECASE,
    )
    return bool(pattern.search(chunk_text))


async def run_skill_gap(
    user_id: str,
    opportunity_id: str,
    required_skills: list[str],
    preferred_skills: list[str],
    github_username: str | None = None,
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
            chunk_text, distance = hits[0]
            if _skill_explicitly_negated(chunk_text, skill):
                # Overrides distance entirely — see _skill_explicitly_negated's docstring.
                missing.append(skill)
            elif distance <= MATCH_THRESHOLD:
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

    github_evidence: dict[str, list[str]] = {}
    github_unavailable = False

    # GitHub evidence only looked up for weak/missing skills (see SkillGapResult's
    # docstring: matched skills already have strong resume evidence and don't need
    # corroboration, and this bounds how many external calls one Skill Gap run makes).
    # A single failure short-circuits the rest of this run's lookups — if GitHub is
    # down/rate-limited once it will very likely fail again immediately after, so this
    # avoids N slow, doomed retries per pipeline run (see docs/ARCHITECTURE.md §5's
    # failure principle: degrade the evidence, don't stall the pipeline).
    if github_username:
        for skill in weak + missing:
            if github_unavailable:
                break
            try:
                matches = await mcp_search_github_evidence(github_username, skill)
            except Exception:
                github_unavailable = True
                continue
            if matches:
                github_evidence[skill] = [f"{m['name']} ({m['language'] or 'unknown language'})" for m in matches]

    result = SkillGapResult(
        matched=matched,
        weak=weak,
        missing=missing,
        github_evidence=github_evidence,
        github_unavailable=github_unavailable,
    )

    latency_ms = (time.monotonic() - start) * 1000
    execution = AgentExecution(
        user_id=PydanticObjectId(user_id),
        agent_name="skill_gap",
        method="embeddings",
        input_summary=(
            f"required={required_skills}, preferred={preferred_skills}, has_resume={has_resume}, "
            f"github_username={github_username}"
        ),
        output=result.model_dump(mode="json"),
        status="success",
        latency_ms=latency_ms,
        opportunity_id=PydanticObjectId(opportunity_id),
    )
    await execution.insert()

    return result, execution
