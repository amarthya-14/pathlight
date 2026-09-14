# Pathlight — Architecture (Gate 1, Finalized — Revision 2)

**Status:** Locked for Gate 2. This revision supersedes the original team-scale
architecture after two confirmed changes: (1) this is a **solo** project, not a 4-person
team, and (2) **MCP is now a central architectural pillar**, not a Phase 6 add-on.

## Revision log

| Rev | Change | Why |
|---|---|---|
| 1 (Gate 1 initial) | Renamed OIE → Pathlight; locked Kafka/K8s/Weaviate/agent-count/single-integration simplifications | See decision table below |
| 2 (this revision) | Collapsed Spring Boot + FastAPI into a single Python backend; team sections removed; MCP moved to Gate 4 as a core pillar; roadmap resequenced for solo work | Solo execution + MCP-centric goal — see §1 |
| 3 (post-Gate-2) | PostgreSQL → MongoDB (Beanie ODM); SQLAlchemy relational models → Beanie Documents | Developer familiarity/velocity — see §11 |

---

## 1. Why the stack changed

**Solo, not a team.** The original split (Spring Boot for one member, FastAPI for
another) existed to give two people independent lanes. Solo, running two backend stacks
is pure overhead: two dependency systems, two auth boundaries, two deploy configs,
constant language context-switching — with no corresponding benefit.

**MCP is now central, not a Gate 7 integration.** MCP tool-calling and LangGraph both live
naturally in the Python ecosystem. If every agent needs tool access (Gmail, GitHub,
Calendar, filesystem), that tool-calling logic belongs in one place. Splitting it behind
a Java orchestrator would make the Java layer a pointless proxy.

**GraphQL's justification disappears with one backend.** GraphQL earned its place
aggregating *multiple backend domains* for the dashboard. With a single FastAPI service,
there's nothing to aggregate across — a typed REST API gives the same dashboard
experience without the extra layer.

**Decision:** single **FastAPI + LangGraph + MCP** backend. Spring Boot and GraphQL are
documented here as the team/production-scale alternative — a legitimate viva answer
("why didn't you use GraphQL/Java" → "single-service MVP had nothing to aggregate across;
documented as the scale-out path") — but are not built.

## 2. Gate 0/1 decisions still in force (unchanged)

| # | Original spec | Finalized decision | Rationale |
|---|---|---|---|
| 1 | Kafka event queue | **Mongo outbox collection → Redis Streams if needed** | Solo, low event volume doesn't justify a cluster |
| 2 | Kubernetes orchestration | **Docker Compose + free-tier PaaS for demo** | No operational benefit at this scale |
| 3 | Weaviate vector DB | **Chroma (embedded)** | Zero infra to run |
| 4 | 7 agents | **3 for MVP: Discovery, Eligibility, Skill Gap** | Reliability over agent count |
| 5 | 4 integrations for MVP | **Gmail first, via MCP from Gate 4 — see §5** | MCP makes adding GitHub/Calendar later cheap, so integration count stays disciplined even as tool access becomes core |

## 3. System Overview

Pathlight is an event-driven, stateful, agentic system. A new email, resume, or skill
certification triggers detection → understanding → reasoning → planning → notification →
tracking, continuously — not a single chatbot turn.

## 4. Component Architecture (Revision 2)

```
                         ┌──────────────────────┐
                         │   Next.js Dashboard   │
                         │  React + TS + Tailwind│
                         └──────────┬────────────┘
                                    │ Typed REST (OpenAPI-generated client)
                                    ▼
                         ┌───────────────────────────────────┐
                         │     Pathlight Backend (FastAPI)     │
                         │  Auth · Domain CRUD · Deterministic  │
                         │  Rules · Ranking · Outbox Producer    │
                         │  ────────────────────────────────    │
                         │     LangGraph Agent Runtime            │
                         │  Discovery · Eligibility · Skill Gap    │
                         │  ────────────────────────────────       │
                         │     MCP Client Layer                     │
                         │  Gmail MCP · GitHub MCP · Calendar MCP    │
                         │  (tool access, permissioned per agent)     │
                         └──────────┬──────────────────────┬──────────┘
                                    ▼                       ▼
                              MongoDB                    Redis
                          (system of record,          (cache, rate
                          outbox collection)             limit, state)
                                    │
                                    ▼
                                 Chroma
                          (resume/JD/interview
                             chunk embeddings)
```

**One process, clearly separated internal layers.** The API layer (`app/api/`), the agent
layer (`app/agents/`, `app/graphs/`), and the MCP layer (`app/mcp/`) are separate Python
modules with clean interfaces between them — this is what keeps "single service" from
becoming "one big tangled file." The outbox pattern is preserved *inside* the same service
(a background worker task, not a separate service) purely to keep the async-decoupling
demonstration intact for the viva, without adding a second deployable.

## 5. MCP Integration Plan (now a core pillar, not Phase 6)

**Why MCP is genuinely justified here (not novelty-chasing):** multiple agents
(Discovery now; Skill Gap and Planner later) need to reach external tools with the *same*
permission/auth/failure-handling pattern. MCP standardizes that interface once instead of
writing a bespoke client per integration (Gmail API client, GitHub API client, Calendar
API client, each with its own auth flow and error handling). That's the actual
architectural advantage — say this exact thing in the viva, not "MCP is popular."

| MCP Tool | Introduced at | Used by | Permissions | On failure |
|---|---|---|---|---|
| **Gmail MCP** | Gate 4 (core, not deferred) | Discovery Agent — read placement/opportunity emails | Read-only, scoped to a labeled folder if the provider supports it | Falls back to manual paste; logged; user notified — never blocks other agents |
| **Filesystem/Document MCP** | Gate 3 | Discovery Agent, Resume ingestion | Read/write to a sandboxed uploads directory only | Falls back to direct file handling in the API layer |
| **GitHub MCP** | Gate 6+ | Skill Gap Agent — evidence for claimed skills | Read-only, public repos + explicitly connected private repos | Skill Gap run proceeds without GitHub evidence; noted in the result's `evidence` field as "unavailable" |
| **Calendar MCP** | Gate 6+ | Deadline/Calendar Agent (if built) | Write access to a dedicated Pathlight calendar only, never the user's whole calendar | Falls back to in-app notification only |

**Failure handling principle (unchanged from Gate 0):** an MCP tool failure degrades that
agent's evidence, it never crashes the pipeline. Every MCP call is wrapped with retry +
timeout + a structured failure result that still flows into the agent's
`{decision, reason, evidence, confidence}` output — `confidence` should visibly drop when
expected evidence sources were unavailable, not silently proceed as if nothing was missing.

**Sequencing change from Rev 1:** Gmail MCP moves from "Gate 7 integration" to
"Gate 4 core dependency" — because the Discovery Agent's primary real-world input *is*
email; building it against a mocked/local text input first and bolting Gmail on later
would mean rebuilding the extraction interface. Build Discovery Agent against the MCP
tool interface from the start, with a local-file/paste fallback path for development and
demo reliability (a live Gmail dependency shouldn't be a single point of failure during
your viva demo).

## 6. Data Flow (canonical path, Rev 2)

```
Email arrives (via Gmail MCP poll) OR user pastes/uploads a JD
        ↓
Backend stores Document, writes outbox row (OPPORTUNITY_INGESTED)
Background worker (in-process) picks up the row
        ↓
Discovery Agent (LangGraph node, may call Gmail/Filesystem MCP for source content)
        → structured Opportunity JSON
        ↓ dedupe check (company + role_hash) → write Opportunity
        ↓ outbox row (ELIGIBILITY_REQUESTED)
Eligibility Agent (deterministic rules → LLM only if ambiguous)
        → EligibilityResult {decision, reason, evidence, confidence}
        ↓ outbox row (SKILL_GAP_REQUESTED)
Skill Gap Agent (embeddings; may call GitHub MCP for evidence, Gate 6+)
        → SkillGapResult {matched, missing, weak}
        ↓
Notification created, Redis cache invalidated
        ↓
Dashboard (REST) shows ranked, explainable result with MCP-sourced evidence flagged
```

## 7. Agent State Graph (LangGraph) — MVP, MCP-aware

```
Discovery (MCP: Gmail/Filesystem)
   → Eligibility (rules first, LLM only if ambiguous)
   → Skill Gap (embeddings; MCP: GitHub optional evidence)
   → END (persist + notify)
```

Each node: max 2 retries with exponential backoff (MCP tool timeouts count as retryable
failures) → falls to `needs_human_review` rather than failing silently. No irreversible
actions in the MVP graph, so no human-approval gate yet — added when a future action
(auto-apply, sending email via MCP) is introduced.

## 8. Development Gate System (resequenced for solo work)

Because this is now solo, gates that were previously "parallelizable across team members"
are explicitly **sequential**. Don't start Gate 4 before Gate 3 is stable — there's no
second person keeping a different gate moving in parallel anymore.

| Gate | Milestone | Status |
|---|---|---|
| 0 | Project Blueprint | Done |
| 1 | Architecture approved, repo scaffolded (Rev 2: solo + MCP-central) | Done (this doc) |
| 2 | Database + backend foundation (single FastAPI service, auth, models) | Done — see §10 |
| 3 | Document/opportunity ingestion + Filesystem MCP | Done — see §12 |
| 4 | First AI pipeline (Discovery → Eligibility; Skill Gap moved to Gate 5) | Done — see §13 |
| 5 | RAG + semantic matching (Chroma) + Skill Gap Agent | Done — see §14 |
| 6 | LangGraph full workflow (+ Planner), GitHub/Calendar MCP | Done — see §15 |
| 7 | *(merged into Gate 4/6 — MCP integrations are no longer a separate late gate)* | N/A |
| 8 | Frontend dashboard | Next |
| 9 | Testing + evaluation | Pending |
| 10 | Cloud deployment | Pending |
| 11 | Security + observability | Pending |
| 12 | Final demonstration | Pending |

## 9. Full Reference

The Gate 0 blueprint's personas, requirements, database entity model, security model,
evaluation strategy, risk register, and cost estimate remain valid and are not
team-dependent, so they still stand as written. Only the component architecture, stack
choice, MCP timing, and team/roadmap sections are superseded by this revision — see
`docs/DATABASE.md`, `docs/AI_DESIGN.md`, `docs/DEPLOYMENT.md` for the sections updated to
match Rev 2.

## 10. Gate 2 — What Was Actually Built

Scope was deliberately narrower than the full entity list in `DATABASE.md`: **User,
Profile, Company, Opportunity** — enough to prove the full chain (DB → auth → CRUD →
dedupe) end-to-end. Application/ApplicationStatus and the rest land when a feature
actually needs them (Gate 3+), not preemptively.

**Implemented:**
- `app/core/config.py` — pydantic-settings config, reads `.env`
- `app/core/db.py` — SQLAlchemy engine/session, `Base.metadata.create_all()` used instead
  of Alembic while the schema is still moving (documented simplification — switch to
  Alembic before Gate 4, once agent-written data needs a stable schema to land on)
- `app/core/security.py` — bcrypt password hashing, JWT create/decode
- `app/models/user.py` — `User`, `Profile` (UUID PKs, 1:1 relationship)
- `app/models/opportunity.py` — `Company`, `Opportunity`, with a `(company_id, role_hash)`
  unique constraint enforcing the dedupe rule from Gate 0 §26 at the DB level, not just
  in application code
- `app/api/routes/auth.py` — `POST /api/auth/register`, `POST /api/auth/login`
  (OAuth2 password flow, JWT bearer)
- `app/api/routes/opportunities.py` — `POST /api/opportunities` (auth-required, dedupe
  enforced), `GET /api/opportunities` (auth-required, list)
- `tests/` — 6 tests covering register/login/duplicate-email/wrong-password and
  create/list/duplicate-opportunity/auth-required, run against an isolated in-memory
  SQLite DB (no Postgres dependency in CI)
- `.github/workflows/ci.yml` — runs the backend test suite on every push/PR
- `infra/docker/docker-compose.yml` — `backend` service is now real (was a commented-out
  stub)

**Two bugs found and fixed during verification** (both are worth knowing as debugging
patterns, not just fixed-and-forgotten):
1. In-memory SQLite (`sqlite:///:memory:`) without `poolclass=StaticPool` gives each
   connection checkout its own separate database — tables created by `create_all()`
   vanished before tests could query them. Fixed by pinning the test engine to a single
   shared connection via `StaticPool`.
2. `passlib==1.7.4` (unmaintained since 2020) misdetects `bcrypt>=4.1` because bcrypt
   removed an internal attribute passlib's version-sniffing relies on, causing a false
   "password cannot be longer than 72 bytes" error on any password. Fixed by pinning
   `bcrypt==4.0.1` in `requirements.txt`.
3. Also migrated `@app.on_event("startup")` to FastAPI's `lifespan` context manager
   (the old pattern is deprecated), and updated the test fixture accordingly.

**Not yet done / explicitly deferred:**
- Alembic migrations (still using `create_all()`)
- Refresh tokens (access-token-only for now, 24h expiry)
- Docker Compose has not been run end-to-end in this environment (no Docker available in
  the sandbox used to build this) — verified instead via direct app import + full pytest
  suite against SQLite. Run `docker compose up` yourself before relying on it for a demo.

## 11. Post-Gate-2 — PostgreSQL → MongoDB

**Decision:** switched from PostgreSQL/SQLAlchemy to **MongoDB via Beanie** (an async
ODM built on Motor + Pydantic).

**Why, honestly:** developer familiarity, not a technical requirement. This is worth
stating plainly for the viva rather than reverse-engineering a technical justification —
the original spec calls for PostgreSQL specifically because most of this domain
(User↔Profile, Application↔ApplicationStatus history, foreign-key relationships) is
genuinely relational. That reasoning didn't change. What changed is that for a solo
semester project, being fast and confident in the data layer has real value, and losing
some relational guarantees is an acceptable trade for that — as long as the guarantees
that *do* matter (the dedupe constraint) are still enforced at the database level, not
just hoped for in application code.

**What's preserved despite the switch:**
- The `(company_id, role_hash)` dedupe constraint is a genuine compound **unique index**
  in MongoDB, enforced by the database — not just an application-level check. This was
  verified directly (inserting a duplicate document bypassing the API layer correctly
  raises `DuplicateKeyError`), not assumed from documentation.
- The 1:1 `User`↔`Profile` relationship is enforced via a unique index on `Profile.user_id`.

**What's genuinely lost, and the plan for when it matters:**
- No foreign-key integrity — deleting a `Company` won't cascade or block if `Opportunity`
  rows still reference it. Acceptable for MVP single-user scale; **must be handled in
  application code** (check-before-delete or soft-delete) once delete operations exist.
- `Application`↔`ApplicationStatus` (planned Gate 4+) loses the clean "foreign key +
  join" pattern. Plan: model `ApplicationStatus` history as an embedded array within the
  `Application` document (a natural fit for MongoDB's document model, and still
  append-only if we only ever `$push` to it, never mutate existing entries) rather than
  as a separate referenced collection — reconsider this specific decision when Gate 4
  actually builds Application.
- `Numeric`-precision CGPA storage: MongoDB stores floats, not SQL `Numeric` — fine for a
  CGPA (2 decimal places, no financial precision requirement), flagged here so it doesn't
  get silently assumed to have SQL-grade precision if reused elsewhere later.

**A real bug found while switching, worth knowing as a debugging pattern:** Beanie 2.x
calls `list_collection_names(authorizedCollections=True, nameOnly=True)` during
initialization — a MongoDB 5.0+ auth-aware call that `mongomock`'s mocked
`list_collection_names` doesn't support, breaking every test with a `TypeError`. Real
MongoDB (and the Docker Compose `mongo:7` image) handles this fine; only the *test mock*
breaks. Fixed by pinning `beanie==1.29.0`, which predates that call. This is the kind of
version-skew issue that's invisible until you actually run the tests — which is exactly
why it was caught before being called done, not left for you to discover later.

## 12. Gate 3 — What Was Actually Built

Scope: document ingestion (upload + text-paste) and the **first real MCP integration** —
a Filesystem MCP server, built and tested standalone before any agent exists to consume
it (Gate 4).

**Implemented:**
- `app/models/document.py` — `Document` model (resume/JD/email-paste), owned per-user
- `app/api/routes/documents.py` — `POST /api/documents/upload` (PDF or plain text, 10MB
  cap, content-type allowlist), `POST /api/documents/paste` (for forwarded emails/JDs
  without a file), `GET /api/documents` (list), `GET /api/documents/{id}` (ownership-
  checked — returns 404, not 403, if the document exists but belongs to someone else, to
  avoid confirming the ID is valid to an attacker)
- `app/mcp/sandbox.py` — the **single shared implementation** of path-sandboxing logic
  (filename sanitization, path-traversal rejection), used by both the REST upload path
  and the MCP server, so there's exactly one place this security property is enforced
- `app/mcp/filesystem_server.py` — a real MCP server (FastMCP) exposing `list_documents`
  and `read_document` tools, scoped per-user
- `app/mcp/filesystem_client.py` — an in-process MCP client wrapper (`mcp_read_document`,
  `mcp_list_documents`) used to exercise and test the server before Gate 4's Discovery
  Agent exists to call it via LangGraph's own MCP adapter
- `GET /api/auth/me` — added (wasn't in Gate 2 scope) because tests needed a clean way to
  get the current user's ID; also just a normal thing the frontend will need later
- 10 new tests (17 total): document upload/paste/auth/ownership, and MCP
  read/list/path-traversal-rejection/missing-file

**Two things worth knowing, not just fixed silently:**
1. **MCP tool list-return values arrive in `result.structuredContent`, not as parseable
   text.** This was verified empirically (see the manual scratch test in this session)
   before writing `mcp_list_documents` — worth remembering for any future MCP tool that
   returns a list or object rather than a plain string.
2. **`anyio`'s `TaskGroup` (used internally by the MCP SDK's in-process transport) wraps
   exceptions raised inside it in a `BaseExceptionGroup`**, even when there's exactly one
   underlying exception — so a plain `RuntimeError` raised by a tool doesn't propagate as
   a plain `RuntimeError` to the caller by default. `filesystem_client.py` unwraps
   single-exception groups back to the original exception, specifically so future callers
   (Gate 4 agents) can catch ordinary exceptions without needing to know `anyio`
   internals. This is the kind of thing that's easy to leave broken if you only run the
   "happy path" test — the path-traversal-rejection test is exactly what surfaced it.

**Security note carried into Gate 4+:** any future MCP tool that touches the filesystem
or another sensitive resource should reuse `app/mcp/sandbox.py`'s pattern (one shared,
tested sandboxing implementation) rather than each tool inventing its own path-safety
logic — the whole point of standardizing through MCP is undermined if every tool behind
it has bespoke, unverified security logic.

**Not yet done / explicitly deferred:**
- Gmail MCP (Gate 4 — this gate only built the Filesystem MCP pattern)
- The MCP server currently runs in-process via in-memory transport, not as a separate
  subprocess/service — appropriate for a tool this simple and always-local; revisit if a
  future MCP tool needs process isolation for a different reason (e.g. running untrusted
  code).

## 13. Gate 4 — What Was Actually Built

**Scope correction, stated plainly:** the original Gate 4 description ("Discovery →
Eligibility → Skill Gap") was internally inconsistent with the roadmap's own Gate 5
scope ("RAG + semantic matching"). Skill Gap genuinely needs embeddings to do anything
more than crude keyword overlap, and embeddings/Chroma don't exist until Gate 5. Rather
than ship a low-quality placeholder Skill Gap agent just to hit a three-agent count,
**Gate 4 is Discovery + Eligibility only; Skill Gap moves formally to Gate 5**, right next
to the embeddings infrastructure it actually depends on. This is not a scope cut — it's
fixing a sequencing mistake in the plan before building around it.

**LLM provider: Gemini**, chosen for developer preference. `app/agents/llm_client.py` is
the single place the provider is referenced, so swapping later is one file, not a
codebase-wide change.

**Implemented:**
- `app/agents/schemas.py` — `ExtractedOpportunity`, `EligibilityResult` (+`EligibilityDecision`
  enum) — the structured-output contracts every agent decision must satisfy, per
  `AI_DESIGN.md`'s non-negotiable rule (decision, reason, evidence, missing_information,
  confidence — never a bare verdict)
- `app/agents/llm_client.py` — Gemini client factory (`get_small_llm`, `get_strong_llm`),
  deliberately the *only* place agent code touches the LLM provider directly
- `app/agents/discovery.py` — extracts `ExtractedOpportunity` from raw text via the small/
  cheap model; logs an `AgentExecution` on every call, success or failure
- `app/agents/eligibility.py` — **deterministic rules first, always.** `_deterministic_check`
  handles hard CGPA/branch cutoffs and missing-data cases without ever calling the LLM;
  the strong model is only invoked when a qualitative `raw_eligibility_text` still needs
  interpretation after all structured checks pass. This ordering is verified directly in
  tests (`test_eligibility_agent.py`) by monkeypatching `get_strong_llm` to raise
  `AssertionError` if called at all in the deterministic cases — not just checking the
  returned decision looks right.
- `app/graphs/opportunity_pipeline.py` — the first real LangGraph workflow: Discovery →
  persist (Company/Opportunity dedupe, reusing the Gate 2 dedupe logic — see
  `app/core/dedupe.py`) → Eligibility, with a simple retry-then-`needs_human_review`
  fallback (2 attempts per AI-calling step, plain loop rather than LangGraph's own retry
  machinery, to keep a first workflow legible)
- `app/models/opportunity.py` — extended with an **embedded** `OpportunityRequirements`
  sub-document (not a separate collection — matches the Mongo-embedding reasoning in §11)
- `app/models/application.py` — new `Application` model, one per `(user_id, opportunity_id)`
  enforced by a compound unique index; `status_history` is an embedded, append-only array
  (`$push` only, per the plan in §11)
- `app/models/agent_execution.py` — new `AgentExecution` observability log; every agent
  call is logged regardless of outcome
- `app/api/routes/profile.py` — minimal Profile upsert/get, added because the Eligibility
  Agent was otherwise untestable through the API: without it, every user is permanently
  "profile missing," which the pipeline correctly reports as `UNCERTAIN` rather than
  guessing, but that's not a useful demo state
- `app/api/routes/ingest.py` — `POST /api/opportunities/ingest`, the first real caller
  (outside tests) of both the LangGraph pipeline and the Filesystem MCP tool from Gate 3
  — accepts either raw text or a `document_id`, and the document path reads content via
  `mcp_read_document`, not by touching disk directly
- 20 new tests (37 total): Discovery/Eligibility agent logic (including the
  never-calls-the-LLM regression tests), full pipeline dedupe/persistence/failure-routing,
  and API-level ingest tests exercising both the raw-text and document-via-MCP paths

**An honest, unavoidable limitation, stated plainly rather than glossed over:** this
sandbox's network egress cannot reach `generativelanguage.googleapis.com` — only package
registries are reachable. Every agent test in this gate uses a fake LLM
(`tests/fakes.py`) that mimics Gemini's structured-output interface exactly, so all the
*agent logic* (deterministic-first ordering, retries, schema validation, AgentExecution
logging, pipeline wiring) is genuinely tested. **None of these tests prove the real
Gemini API integration works.** Set a real `GOOGLE_API_KEY` and run a manual smoke test
(`POST /api/opportunities/ingest` with real text) before treating Gate 4 as demo-ready.

**Not yet done / explicitly deferred:**
- Skill Gap Agent (moved to Gate 5, with embeddings — see scope correction above)
- Gmail MCP (still Gate 6+ per the original plan — Discovery Agent currently takes text
  directly or via an uploaded Document, not a live inbox)
- Merge strategy for re-ingesting an opportunity from a second, less-complete source
  currently just overwrites `requirements` with the latest extraction — flagged in the
  code as worth revisiting if this causes surprises in practice

## 14. Gate 5 — What Was Actually Built

Scope: the RAG/embeddings infrastructure this project's model-routing table always
called for (`docs/AI_DESIGN.md`), plus the Skill Gap Agent that was deliberately deferred
out of Gate 4 until this existed.

**Implemented:**
- `app/retrieval/chunking.py` — simple paragraph-aware chunking (pure/deterministic, no
  DB or network — fully unit-testable on its own)
- `app/retrieval/embeddings.py` — Gemini embedding client (`gemini-embedding-001`,
  verified as the current GA text-embedding model, not a retired one — see the same
  verification discipline applied to the chat models in §13), isolated to one file for
  the same swap-later reason as `app/agents/llm_client.py`
- `app/retrieval/vector_store.py` — Chroma wrapper (`resume_chunks` collection, cosine
  distance explicitly configured — Chroma's default is squared L2, which the Skill Gap
  Agent's thresholds don't assume), scoped per-user via metadata filtering, with a
  cheap existence check (`user_has_indexed_resume`) that doesn't require an embedding
  call just to know whether a user has any resume on file
- `app/agents/skill_gap.py` — the Skill Gap Agent: a plain distance-threshold
  classification over embeddings (matched / weak / missing), deliberately **not** an LLM
  call per skill — cheaper, faster, and more consistent for what is fundamentally a
  similarity-ranking task, not a reasoning task. This is the one agent in the whole
  project that genuinely needs embeddings rather than deterministic code or LLM
  judgment, per the model-routing table this project committed to from the start.
- Resume indexing wired into the document upload/paste routes (`app/api/routes/documents.py`)
  — a resume is indexed into Chroma at upload time, not lazily on first Skill Gap run,
  so the first opportunity ingestion after uploading a resume isn't silently slower
- `app/graphs/opportunity_pipeline.py` — extended with a third node, Skill Gap, run after
  Eligibility. If an opportunity has no extracted skills there's nothing to compare, so
  the node is a no-op (not an error); if the user has no resume indexed at all, every
  skill is reported `missing` but the pipeline separately surfaces
  `skill_gap_note: "No resume on file..."` so that's distinguishable from "we checked and
  found no evidence" rather than silently conflating the two
- 17 new tests (54 total): chunking (pure logic), vector store (indexing, per-user
  scoping, re-index-replaces-not-accumulates), Skill Gap Agent classification, and
  pipeline-level integration tests for all three skill-gap scenarios (matched resume,
  no resume, no skills to check)

**An empirical verification worth calling out, not just claiming it was done:** the fake
embedder used in tests (`tests/fakes.py::FakeEmbedder`) was designed with vectors chosen
by hand-calculated cosine math to land in specific distance ranges (matched, weak,
missing). Rather than trust that math, `tests/test_vector_store.py` asserts the actual
distances Chroma returns fall in the predicted ranges — this is what caught whether
Chroma's cosine distance formula actually matches the assumption the thresholds in
`app/agents/skill_gap.py` are built on, instead of finding out later.

**The same honest limitation as Gate 4, restated because it applies here too:** this
sandbox cannot reach Google's embedding API. The fake embedder proves the *retrieval and
classification logic* is correct (chunking, indexing, per-user scoping, threshold
classification, pipeline wiring) — it does not prove `gemini-embedding-001` produces
useful real-world embeddings for skill matching, or that the `MATCH_THRESHOLD`/
`WEAK_THRESHOLD` values (0.25 / 0.45) are well-calibrated against real embeddings rather
than just internally consistent with the fake. **Before treating Skill Gap as reliable,**
run it against a real resume and a handful of known matching/non-matching skills with a
real `GOOGLE_API_KEY`, and adjust the thresholds if the real distances don't land where
expected.

**Not yet done / explicitly deferred:**
- The skill-matching benchmark dataset called for in `docs/EVALUATION.md` (Recall@K,
  Precision@K) — needed to actually calibrate the thresholds above against real
  embeddings, not just verify the classification logic works given some distance
- `job_description_chunks`, `interview_experiences`, `study_resources` collections
  from the original blueprint — not built, because nothing yet retrieves from them (the
  Skill Gap Agent only needs `resume_chunks`); adding unused collections would violate
  the "don't use vector search where nothing needs it yet" principle
- A minor inefficiency, not a bug: `app/graphs/opportunity_pipeline.py`'s skill_gap node
  calls `user_has_indexed_resume` once itself (to decide whether to set
  `skill_gap_note`) and `run_skill_gap` calls it again internally — two cheap
  metadata-only Chroma lookups instead of one. Left as-is for clarity; worth collapsing
  if this path gets performance-sensitive later.

## 15. Gate 6 — What Was Actually Built

Scope: complete the LangGraph workflow with a Preparation Planner Agent, add GitHub MCP
(Skill Gap evidence) and Calendar MCP (deadline reminders), per §5/§8. This gate also
did something no prior gate could: it ran against the **real** Gemini API for the first
time (see the smoke-test section below) — every agent test through Gate 5 used fakes
because that development environment couldn't reach Google's API at all.

**Housekeeping before any Gate 6 code:** this repo's git history had stalled at a
`"gate 3"` commit on the `amarthya-14/pathlight` remote while the actual working tree
already had Gate 4 and Gate 5 fully built (54 passing tests, matching §13/§14 above) —
version control had simply fallen behind real progress. Brought back in sync (two
commits: the Gate 4/5 sync itself, and a separate fix for `requirements.txt`, which
failed to install at all — `mcp==1.29.1`'s own PyPI pins had moved past this project's
pins for `pydantic`, `uvicorn`, and `httpx` since they were last set; bumped all three,
each satisfying every other package's constraints too, re-verified with a full clean
install and the full test suite).

### Real Gemini API smoke test (first time ever run against the live API)

With a real `GOOGLE_API_KEY` and real network access finally available, every path
flagged "unverified" in Gates 4 and 5 was actually exercised end-to-end — not just
unit-tested against fakes — and re-verified again after each fix below, not just
patched and assumed correct:

1. **`LLM_MODEL_STRONG = "gemini-3.1-pro"` does not exist.** A real ambiguous-eligibility
   ingest returned a 404 from the real API (`models/gemini-3.1-pro is not found for API
   version v1beta`) — no prior test caught this because `FakeLLM` doesn't validate model
   names. Its real successor, `gemini-3.1-pro-preview`, DOES exist (confirmed via
   `ListModels`), but calling it returned `429 RESOURCE_EXHAUSTED` with `limit: 0` on
   every quota metric for this project's free-tier key — i.e. the entire
   `gemini-3.1-pro` family requires a billing-enabled Google account, which this project
   doesn't have. Moved `LLM_MODEL_STRONG` to `gemini-3.6-flash` (confirmed working,
   including extended-thinking tokens in the response, and confirmed the
   ambiguous-eligibility LLM path now completes end-to-end with a sensible `uncertain`
   decision and 0.85 confidence). `LLM_MODEL_SMALL` (`gemini-3.1-flash-lite`) needed no
   change — independently confirmed working via a real Discovery extraction.
2. **Skill Gap's `MATCH_THRESHOLD`/`WEAK_THRESHOLD` (0.25/0.45, chosen by inspection
   against a fake in Gate 5) were badly wrong against real `gemini-embedding-001`
   output.** A real resume with clear, explicit skills (Python/FastAPI/PostgreSQL/AWS
   present; Kubernetes/Rust/Swift explicitly disclaimed: *"No experience with
   Kubernetes, Rust, or ... Swift"*) produced these real single-skill-vs-resume-chunk
   cosine distances: FastAPI 0.319, AWS 0.341, Python 0.363, Django 0.358,
   PostgreSQL 0.375, Machine Learning 0.376, Swift 0.375, Kubernetes 0.352, Rust 0.390,
   Photography (an unrelated control) 0.442. Two real findings came out of this, not
   one:
   - Genuine matches and genuine non-matches overlap almost completely in the
     0.32–0.39 band for a topically-similar resume — no single global threshold can
     cleanly separate them. Recalibrated to `MATCH_THRESHOLD = 0.34` /
     `WEAK_THRESHOLD = 0.42` using this one real example as a **directional signal
     only** — explicitly not a validated fit. That still requires the labeled
     benchmark set `docs/EVALUATION.md` already calls for (Gate 9), not more manual
     tweaking against a single resume.
   - Embedding distance alone cannot tell *"no experience with Kubernetes"* apart from
     *"experienced with Kubernetes"* — both chunks contain the word and score
     similarly close. This is a structural gap, not a miscalibration, so it's fixed
     separately: `app/agents/skill_gap.py::_skill_explicitly_negated` is a deterministic
     regex guard on the actual matched chunk text (a few common negation cues — "no",
     "not", "without", "never", "lacks" — within ~6 words of the skill name) that
     overrides a matched/weak classification to `missing` regardless of distance. Both
     fixes were re-verified against the live API (a second real ingest, same resume,
     different company/skills): Kubernetes and Rust correctly came back `missing`,
     FastAPI came back `matched`.
3. Also verified for real, working with no changes needed: Discovery extraction
   (company/role/CGPA/branches/skills/deadline all parsed correctly from a real JD),
   Eligibility's deterministic path, the Filesystem MCP-backed document flow, and (new
   this gate) the Planner Agent and Calendar MCP end-to-end through a real ingest →
   auto-generated plan → regenerate-with-real-hours-per-day → persisted `CalendarEvent`
   reminder, all inspected directly in MongoDB, not just trusted from the HTTP response.

### Implemented

- `app/agents/planner.py` — the **Preparation Planner Agent**. Deliberately
  **deterministic, no LLM call at all** — the same "don't use an agent where
  deterministic code suffices" discipline already applied to Eligibility's hard checks
  and Skill Gap's embedding threshold (see `docs/AI_DESIGN.md`). Reasoning, stated
  plainly: skill-prerequisite relationships (Java → Spring Boot → REST APIs) are
  common-knowledge, slow-changing domain facts for the tech skills this project
  realistically deals with — a static lookup table (`SKILL_PREREQUISITES`) plus a
  topological sort (Kahn's algorithm, `_dependency_order`) is a *complete and correct*
  answer for any skill in the table, not an approximation an LLM would improve on, and
  an LLM call here could hallucinate a prerequisite relationship with no way for the
  user to tell it apart from a real one. For a skill not in the table, there's no
  reliable evidence at this gate to infer a prerequisite either way — listed as a
  standalone task rather than guessed, mirroring Eligibility's
  uncertain-rather-than-guess principle. Effort-hours (`SKILL_EFFORT_HOURS`) and the
  weak-skill discount (`WEAK_SKILL_EFFORT_MULTIPLIER = 0.4`) are inspection-based
  heuristics, stated as such, not calibrated data.
- `app/models/preparation.py` — `PreparationPlan` (top-level Document) /
  `PreparationTask` (embedded `BaseModel`, per `docs/DATABASE.md`'s planned entry: a
  **self-referencing ID list** (`depends_on: list[PydanticObjectId]`) for the dependency
  graph, not a separate graph DB. Each task's ID is generated by the Planner Agent
  itself at construction time (`PydanticObjectId()`), since Beanie doesn't auto-assign
  IDs to embedded sub-documents the way it does top-level Documents — needed so
  `depends_on` can reference sibling tasks before anything is ever persisted.
- `app/mcp/github_server.py` / `github_client.py` — **GitHub MCP**, read-only.
  **Scope decision, stated plainly**: §5's table calls for "public repos + explicitly
  connected private repos." Private-repo access needs a real per-user GitHub OAuth
  flow, and per `docs/SECURITY.md` **no** MCP tool in this project has a real OAuth flow
  yet. Building one just for this, without the token-encryption infrastructure Gate 11
  is supposed to add, would mean either shipping plaintext OAuth tokens or half-building
  encryption ad hoc under the wrong gate's scope — neither is better than being honest
  about deferring it. This gate builds public-repo read access only (GitHub's
  unauthenticated REST API, with an optional shared `GITHUB_MCP_TOKEN` app-level PAT
  purely for rate limits, **not** per-user OAuth). On any HTTP/network failure the tool
  raises (one retry with backoff in the client) rather than returning an empty list, so
  Skill Gap can distinguish "checked, found nothing" from "couldn't check" — and
  proceeds without blocking either way, per §5's MCP failure principle.
- `app/agents/skill_gap.py` extended with an optional `github_username` parameter and
  two new `SkillGapResult` fields: `github_evidence` (skill → matching repo names) and
  `github_unavailable` (the lookup couldn't be completed at all). GitHub is
  **supplementary evidence only** — it never moves a skill between matched/weak/missing
  (a repo-name substring match is too crude a signal to safely override the
  embedding-distance classification); it's only looked up for weak/missing skills
  (matched skills already have strong resume evidence), and a single failure
  short-circuits the rest of that run's lookups rather than retrying N more doomed
  calls.
- `app/models/user.py` — `Profile.github_username`, optional, the lookup key for the
  above.
- `app/mcp/calendar_server.py` / `calendar_client.py` / `app/models/calendar_event.py` —
  **Calendar MCP**. **Same scope decision as GitHub MCP, same reasoning**: a real
  external calendar (Google Calendar, etc.) needs real OAuth, which doesn't exist yet
  for any tool in this project. So "the dedicated Pathlight calendar" is, for now, an
  internal `CalendarEvent` collection — real, persisted, queryable, reachable only
  through the Calendar MCP tool interface — not yet a real external calendar. Swapping
  in a real Google Calendar API call later is a provider swap behind the same MCP tool
  interface, the same isolation pattern `app/agents/llm_client.py` and
  `app/retrieval/embeddings.py` already use for Gemini, not a redesign.
- `app/graphs/opportunity_pipeline.py` extended with a fourth node, **Planner**, run
  after Skill Gap: `discovery → persist → eligibility → skill_gap → planner → END`.
  No-ops (same "nothing to do" pattern as the skill_gap node) if there are no
  missing/weak skills. Generates a first-pass plan using a default hours/day assumption
  (`DEFAULT_HOURS_PER_DAY = 2.0`, documented as a placeholder pending a real
  user-supplied value), persists it (upsert-by-`application_id`, same overwrite-on-
  regenerate pattern as Opportunity re-ingestion), appends a `PREPARING`
  `ApplicationStatusEvent`, and — if the opportunity has a deadline — attempts a
  best-effort Calendar MCP reminder. Planner and Skill Gap both skip the
  retry/`needs_human_review` machinery: neither is a structured-output LLM call prone
  to schema-validation failure, so a single attempt is treated as reliable enough for
  this MVP (documented in the module docstring, same reasoning already applied to
  Skill Gap in Gate 5).
- `app/api/routes/preparation.py` — `POST`/`GET /api/applications/{id}/preparation-plan`.
  `POST` takes a real user-supplied `hours_per_day` and regenerates the plan — the real
  value path the pipeline's auto-generated first-pass plan is explicitly meant to be
  replaced by. 400 if the application has no Skill Gap result yet, or nothing
  missing/weak to plan for; 404 (not 403) if the application doesn't exist or isn't
  owned by the caller, same anti-enumeration reasoning as `GET /api/documents/{id}`.
- 26 new tests (80 total): Planner Agent unit tests (prerequisite ordering, unknown-skill
  fallback, weak-effort discount, feasibility flag, `compute_available_hours`
  edge cases, and a never-calls-an-LLM test in the same style as Eligibility's), GitHub
  MCP (mocked HTTP, matched/no-match/failure-propagates), Calendar MCP
  (create/invalid-time-rejected), Skill Gap's negation guard and GitHub-evidence wiring,
  pipeline-level Planner/Calendar-reminder tests, and API-level preparation-plan route
  tests.

### Two things worth knowing as debugging patterns, not just fixed silently

1. **A dict-typed FastMCP tool return does NOT populate `structuredContent`** — unlike a
   list-typed one (`mcp_list_documents`, Gate 3: `structuredContent["result"]`), a
   dict-typed return (`create_reminder`) arrives as a JSON string in
   `result.content[0].text` with `structuredContent` left `None`. Verified empirically
   with a throwaway script before trusting it (same discipline as Gate 3's list-typed
   finding) — `calendar_client.py::mcp_create_reminder` `json.loads`s the text block
   instead. A list-of-dicts return (`search_repos_for_skill`) turned out to match the
   list-typed behavior, also checked directly rather than assumed by extension.
2. **MongoDB's database names are case-insensitive for collision purposes even though
   they're stored case-sensitively.** The local dev `mongod` used for this gate's smoke
   test already had a `PathLight` database from earlier manual testing; pointing
   `MONGO_DB_NAME` at `pathlight` (lowercase) failed at Beanie init with
   `OperationFailure: db already exists with different case`. Not a code bug — worked
   around by using a distinctly-named local database (`pathlight_gate6`) rather than
   touching whatever was already in `PathLight`. Worth knowing if a fresh
   `docker compose` Mongo volume isn't being used for local testing.

### Not yet done / explicitly deferred

- **Private-repo GitHub access and a real external Calendar (Google Calendar API)** —
  both need real per-user OAuth, which no MCP tool in this project has yet. Building
  either now, ahead of Gate 11's token-encryption work, would mean shipping plaintext
  tokens; deferred on purpose, not forgotten. See both modules' scope-decision
  docstrings.
- **Skill Gap's recalibrated thresholds are a directional fix from ONE real resume**,
  not a validated calibration — the real fix is still the labeled benchmark dataset
  `docs/EVALUATION.md` calls for (Gate 9).
- **No per-task due-date scheduling within a plan** — only a plan-level total-hours/
  feasibility check against the deadline. A deliberate MVP scope cut, not an oversight.
- **No in-app notification fallback if the Calendar MCP reminder fails** — `Notification`
  is still listed as "Planned" in `docs/DATABASE.md`; the pipeline just proceeds without
  a reminder on failure right now (still non-blocking, per §5's failure principle, just
  without the fallback notification §5's table originally imagined).
- **No frontend yet** to show any of this — Gate 8.
