# Pathlight — Architecture (Gate 1, Finalized — Revision 2)

**Status:** Locked for Gate 2. This revision supersedes the original team-scale
architecture after two confirmed changes: (1) this is a **solo** project, not a 4-person
team, and (2) **MCP is now a central architectural pillar**, not a Phase 6 add-on.

## Revision log

| Rev | Change | Why |
|---|---|---|
| 1 (Gate 1 initial) | Renamed OIE → Pathlight; locked Kafka/K8s/Weaviate/agent-count/single-integration simplifications | See decision table below |
| 2 (this revision) | Collapsed Spring Boot + FastAPI into a single Python backend; team sections removed; MCP moved to Gate 4 as a core pillar; roadmap resequenced for solo work | Solo execution + MCP-centric goal — see §1 |

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
| 1 | Kafka event queue | **Postgres outbox table → Redis Streams if needed** | Solo, low event volume doesn't justify a cluster |
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
                              PostgreSQL                  Redis
                          (system of record,          (cache, rate
                           outbox table)                limit, state)
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
| 2 | Database + backend foundation (single FastAPI service, auth, models) | Next |
| 3 | Document/opportunity ingestion + Filesystem MCP | Pending |
| 4 | First AI pipeline (Discovery via Gmail MCP → Eligibility → Skill Gap) | Pending |
| 5 | RAG + semantic matching (Chroma) | Pending |
| 6 | LangGraph full workflow (+ Planner), GitHub/Calendar MCP | Pending |
| 7 | *(merged into Gate 4/6 — MCP integrations are no longer a separate late gate)* | N/A |
| 8 | Frontend dashboard | Pending |
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
