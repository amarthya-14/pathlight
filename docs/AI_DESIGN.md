# AI Design

**Status:** Discovery + Eligibility + Skill Gap + Planner all implemented and tested
(Gate 4/5/6), and — new at Gate 6 — actually verified against the real Gemini API, not
just fakes (see `docs/ARCHITECTURE.md` §15). LLM provider: Gemini. Embedding provider:
Gemini (`gemini-embedding-001`).

## Model routing (confirmed principle; all six rows now implemented)
| Task | Method | Status |
|---|---|---|
| Deadline math, CGPA cutoffs | Deterministic code — no LLM | ✅ Implemented (`app/agents/eligibility.py::_deterministic_check`) |
| Opportunity field extraction | Small/cheap LLM (`gemini-3.1-flash-lite`), structured-output | ✅ Implemented (`app/agents/discovery.py`) — confirmed against the real API, Gate 6 |
| Ambiguous eligibility interpretation | Stronger LLM (`gemini-3.6-flash` — see note below), only when deterministic rules can't decide | ✅ Implemented (`app/agents/eligibility.py`) — confirmed against the real API, Gate 6 |
| Resume↔JD similarity / skill matching | Embeddings + cosine distance (Chroma) | ✅ Implemented (`app/agents/skill_gap.py`) — thresholds recalibrated against real embeddings, Gate 6 |
| Skill prerequisite ordering / prep planning | Deterministic code — no LLM | ✅ Implemented (`app/agents/planner.py`) |

**Why `LLM_MODEL_STRONG` is a flash model, not a pro model:** the original choice
(`gemini-3.1-pro`) doesn't exist on the real API at all, and its real replacement
(`gemini-3.1-pro-preview`) has zero free-tier quota for this project's API key — this is
a billing-tier limitation, not a code choice. `gemini-3.6-flash` was confirmed working
end-to-end on the free tier, including for the ambiguous-eligibility reasoning task.
Full story in `docs/ARCHITECTURE.md` §15 and the comment in `app/core/config.py`.

**LLM provider (Gemini) is isolated to two files:** `app/agents/llm_client.py` (chat
models) and `app/retrieval/embeddings.py` (embedding model). Swapping providers later
means changing two files, not every agent.

**Deterministic-first is enforced structurally, not just by convention.** The Eligibility
Agent's `_deterministic_check` function returns a definitive result and simply never
calls `get_strong_llm()` for hard CGPA/branch cutoffs or missing-data cases. The Skill
Gap Agent similarly never calls an LLM at all — skill matching is a plain distance
threshold over embeddings, not a per-skill LLM judgment, because it's a similarity-
ranking task, not a reasoning task. Both are verified directly in tests, not just by
checking the output looks right.

## RAG / Embeddings pipeline (Gate 5)
```
Resume uploaded/pasted (app/api/routes/documents.py)
   ↓ (if doc_type == resume and text extracted)
Chunked (app/retrieval/chunking.py — paragraph-aware, ~500 chars/chunk)
   ↓
Embedded (app/retrieval/embeddings.py — gemini-embedding-001, task_type=RETRIEVAL_DOCUMENT)
   ↓
Stored in Chroma (app/retrieval/vector_store.py — resume_chunks collection,
                   cosine distance, scoped per-user via metadata)
```
At query time (Skill Gap Agent), each required/preferred skill string is embedded with
`task_type=RETRIEVAL_QUERY` and matched against the user's resume chunks:
- distance ≤ 0.34 → **matched**
- 0.34 < distance ≤ 0.42 → **weak**
- distance > 0.42, or no resume indexed at all, or the matched chunk explicitly
  disclaims the skill (`_skill_explicitly_negated` — see below) → **missing**

**These thresholds were recalibrated against real `gemini-embedding-001` output at
Gate 6** (`docs/ARCHITECTURE.md` §15 has the exact real distances observed) — a real
improvement over Gate 5's fake-only 0.25/0.45, but still just a directional fix from one
real resume, not a validated calibration. That requires the labeled benchmark set
`docs/EVALUATION.md` calls for (Gate 9). Separately, embedding distance alone cannot
tell "no experience with X" apart from "experienced with X" (both chunks contain the
word) — this structural gap is fixed with a deterministic negation-cue check on the
actual matched chunk text, not by moving thresholds around.

Only `resume_chunks` exists. `job_description_chunks`, `interview_experiences`,
`study_resources` from the original blueprint are not built — nothing retrieves from
them yet (see `ARCHITECTURE.md` §14's "don't build vector search nothing needs" note).

## MCP tool access
Agents don't call Gmail/GitHub/Calendar APIs directly. They call MCP tools through
`app/mcp/`, which handles auth, permission scoping, retries, and timeouts uniformly.

**Filesystem MCP (built, Gate 3; first real caller added Gate 4):** `app/mcp/filesystem_server.py`
exposes `list_documents` and `read_document`, scoped per-user (`app/mcp/sandbox.py` is the
single shared path-safety implementation).

**GitHub MCP (built, Gate 6):** `app/mcp/github_server.py` exposes
`search_repos_for_skill`, read-only, public repos only for now (private-repo OAuth
deferred — see `docs/ARCHITECTURE.md` §15). Used by the Skill Gap Agent as supplementary
evidence for weak/missing skills only — it never changes the matched/weak/missing
classification itself. On failure, proceeds without GitHub evidence rather than
blocking, per the MCP failure principle in `ARCHITECTURE.md` §5.

**Calendar MCP (built, Gate 6):** `app/mcp/calendar_server.py` exposes `create_reminder`,
writing to an internal `CalendarEvent` collection that stands in for "the dedicated
Pathlight calendar" until real Calendar OAuth exists (same deferral reasoning as GitHub
MCP). Called from the LangGraph pipeline's Planner node once a plan exists with a
deadline; a failure here is caught but never blocks the pipeline — not yet logged
anywhere, since there's no `Notification` model to log it to (still "Planned" in
`docs/DATABASE.md`); flagged as a real gap in `docs/ARCHITECTURE.md` §15, not silently
accepted.

**Gmail MCP:** still planned — the Discovery Agent currently takes text directly or via
an uploaded Document, not a live inbox poll.

## Non-negotiable rule
Every agent decision returns a structured, schema-validated result — never a bare
verdict (`EligibilityResult`) or an unstructured guess (`SkillGapResult`). See
`app/agents/schemas.py`.

## Observability
Every agent call — Discovery, Eligibility, Skill Gap, Planner — success or failure, is
logged via `AgentExecution` (`app/models/agent_execution.py`): input summary, output,
method (`deterministic` / `llm` / `embeddings`), latency, and error message if any.
Planner is always `method="deterministic"` — it never calls an LLM, verified directly by
a test that runs it with no `FakeLLM` monkeypatched anywhere (same verification style as
Eligibility's never-calls-the-LLM tests).

## Real-API verification status (updated Gate 6 — supersedes the Gate 4/5 fakes-only note)
Gates 4 and 5 were built and tested entirely against fakes (`tests/fakes.py::FakeLLM`,
`FakeEmbedder`) — the original development sandbox couldn't reach Google's API at all.
**Gate 6 finally ran the real manual smoke test this note used to call for**, with a real
`GOOGLE_API_KEY`: real Discovery extraction, both Eligibility paths (deterministic and
the LLM-based ambiguous-reasoning path), and Skill Gap (embeddings + the negation guard)
were all confirmed working end-to-end against the live API — not just unit-tested
against fakes. Three real bugs were found and fixed in the process (stale/unavailable
model name, miscalibrated thresholds, negation blindness) — full details in
`docs/ARCHITECTURE.md` §15. What's still true and still worth stating plainly: the
fakes-based test suite (now 80 tests) still proves agent *logic* (ordering, retries,
validation, logging, threshold classification) independent of any real API call, which
is what keeps CI hermetic and fast — the real-API run was a one-time manual verification
pass, not something CI does on every push, and Skill Gap's thresholds are still only a
*directional* recalibration from one real resume, not a validated benchmark (Gate 9).
