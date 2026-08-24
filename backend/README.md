# Pathlight Backend (FastAPI + LangGraph + MCP)

**Status:** Scaffolded, no code yet — starts at Gate 2.

**Architecture note:** this project was originally scoped with a split Java (Spring Boot)
+ Python (FastAPI) backend for a 4-person team. It is now a **solo project with MCP as a
central architectural pillar**, so the two stacks were collapsed into one — see
`docs/ARCHITECTURE.md` for the full reasoning. Spring Boot/GraphQL remain documented as
the team-scale alternative, not something built here.

## Responsibilities (everything lives in one service now)
- Authentication (JWT) and authorization
- Domain CRUD (User, Profile, Opportunity, Application, etc.) via SQLAlchemy/SQLModel
- Deterministic rules: CGPA/branch eligibility cutoffs, deadline math, dedupe key,
  ranking formula
- LangGraph agent workflows (Discovery → Eligibility → Skill Gap for MVP)
- **MCP client integration** — agents reach external tools (Gmail, GitHub, Calendar,
  filesystem/document storage) through MCP servers via a standard tool-calling interface,
  not bespoke API clients per integration
- Embeddings + Chroma retrieval (RAG)
- Structured, schema-validated output for every agent decision:
  `{decision, reason, evidence[], confidence, source, timestamp}`

## Why one service instead of two
- MCP tool-calling and LangGraph both live naturally in the Python ecosystem — splitting
  agent orchestration from a Java API layer would mean the Java side becomes a thin,
  pointless proxy.
- Solo dev: one dependency system, one auth boundary, one deploy target, one language
  context-switch instead of two.
- The MVP has one client (the dashboard) hitting one backend — GraphQL's aggregation
  benefit only matters when there are multiple backend domains/services to combine.

## Local run (once implemented)
```bash
uvicorn app.main:app --reload --port 8000
```

## Structure
```
app/api/         # REST routers (auth, opportunities, applications, uploads)
app/agents/       # one module per agent (discovery.py, eligibility.py, skill_gap.py, ...)
app/graphs/        # LangGraph graph definitions
app/mcp/            # MCP client setup, tool registration, per-tool permission config
app/retrieval/      # chunking, embedding, Chroma access
app/schemas/         # pydantic models for API I/O, agent I/O, event payloads
app/models/           # SQLAlchemy/SQLModel ORM models
app/core/              # config, security (JWT), db session, outbox helper
tests/
```
