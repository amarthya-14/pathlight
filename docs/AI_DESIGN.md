# AI Design

**Status:** Discovery + Eligibility + Skill Gap all implemented and tested (Gate 4 + 5).
LLM provider: Gemini. Embedding provider: Gemini (`gemini-embedding-001`).

## Model routing (confirmed principle; all five rows now implemented)
| Task | Method | Status |
|---|---|---|
| Deadline math, CGPA cutoffs | Deterministic code — no LLM | ✅ Implemented (`app/agents/eligibility.py::_deterministic_check`) |
| Opportunity field extraction | Small/cheap LLM (`gemini-3.1-flash-lite`), structured-output | ✅ Implemented (`app/agents/discovery.py`) |
| Ambiguous eligibility interpretation | Stronger LLM (`gemini-3.1-pro`), only when deterministic rules can't decide | ✅ Implemented (`app/agents/eligibility.py`) |
| Resume↔JD similarity / skill matching | Embeddings + cosine distance (Chroma) | ✅ Implemented (`app/agents/skill_gap.py`) |

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
- distance ≤ 0.25 → **matched**
- 0.25 < distance ≤ 0.45 → **weak**
- distance > 0.45, or no resume indexed at all → **missing**

**These thresholds are unvalidated against real embeddings** — see the limitation note
below. They're internally consistent (verified against Chroma's actual cosine distance
output using a fake embedder — see `tests/test_vector_store.py`), not empirically tuned.

Only `resume_chunks` exists. `job_description_chunks`, `interview_experiences`,
`study_resources` from the original blueprint are not built — nothing retrieves from
them yet (see `ARCHITECTURE.md` §14's "don't build vector search nothing needs" note).

## MCP tool access
Agents don't call Gmail/GitHub/Calendar APIs directly. They call MCP tools through
`app/mcp/`, which handles auth, permission scoping, retries, and timeouts uniformly.

**Filesystem MCP (built, Gate 3; first real caller added Gate 4):** `app/mcp/filesystem_server.py`
exposes `list_documents` and `read_document`, scoped per-user (`app/mcp/sandbox.py` is the
single shared path-safety implementation).

**Gmail/GitHub/Calendar MCP:** still planned Gate 6+ — see `ARCHITECTURE.md` §5.

## Non-negotiable rule
Every agent decision returns a structured, schema-validated result — never a bare
verdict (`EligibilityResult`) or an unstructured guess (`SkillGapResult`). See
`app/agents/schemas.py`.

## Observability
Every agent call — Discovery, Eligibility, Skill Gap, success or failure — is logged via
`AgentExecution` (`app/models/agent_execution.py`): input summary, output, method
(`deterministic` / `llm` / `embeddings`), latency, and error message if any.

## Known, stated limitation (Gate 4 and Gate 5 both)
This project's sandbox environment during development could not reach Google's Gemini
API — neither the chat endpoint nor the embedding endpoint (network egress limited to
package registries). All agent tests use fakes (`tests/fakes.py::FakeLLM`,
`FakeEmbedder`) that mimic the real interfaces exactly — this proves agent *logic*
(ordering, retries, validation, logging, threshold classification) but not the real API
integration, and not that `gemini-embedding-001` actually produces good real-world skill
embeddings. **Run a manual smoke test with a real `GOOGLE_API_KEY`** — ingest a real
opportunity and check a real resume's Skill Gap results — **before treating this as
demo-ready**, and be prepared to adjust `MATCH_THRESHOLD`/`WEAK_THRESHOLD` in
`app/agents/skill_gap.py` if real distances don't land where expected.
