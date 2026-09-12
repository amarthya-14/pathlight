# Pathlight Backend (FastAPI + LangGraph + MCP)

**Status:** Gate 5 done — Discovery, Eligibility, and Skill Gap agents are all
implemented and tested, wired into a complete 3-node LangGraph pipeline, backed by a
Chroma vector store for semantic skill matching. LLM + embedding provider: Gemini.

**Architecture notes:**
- Solo project with MCP as a central pillar — Spring Boot/GraphQL were dropped, single
  Python backend (`docs/ARCHITECTURE.md` §1).
- Database is MongoDB via Beanie, not the originally planned PostgreSQL (§11).
- LLM/embeddings are Gemini, isolated to `app/agents/llm_client.py` and
  `app/retrieval/embeddings.py` so the provider can be swapped without touching agent logic.

## Responsibilities
- Authentication (JWT) and authorization — ✅ implemented
- Domain CRUD via Beanie/MongoDB — ✅ implemented
- Document ingestion (upload + text-paste, PDF text extraction) — ✅ implemented
- **Filesystem MCP** (server + client, sandboxed per-user document access) — ✅ implemented
- **Discovery Agent** (Gemini, structured extraction from raw text) — ✅ implemented
- **Eligibility Agent** (deterministic rules first, LLM only when genuinely ambiguous) — ✅ implemented
- **Skill Gap Agent** (Chroma + Gemini embeddings, distance-threshold classification) — ✅ implemented
- **RAG pipeline**: resume chunking → embedding → Chroma storage, at upload time — ✅ implemented
- **LangGraph pipeline** (Discovery → persist → Eligibility → Skill Gap, retry + needs_human_review fallback) — ✅ implemented
- Gmail/GitHub/Calendar MCP — planned, Gate 6+

## ⚠️ Known limitation: Gemini calls are unverified in this build

The environment this backend was built in cannot reach Google's Gemini API — neither the
chat endpoint nor the embedding endpoint (network egress limited to package registries).
Every agent test uses fakes (`tests/fakes.py::FakeLLM`, `FakeEmbedder`) that mimic
Gemini's interfaces exactly — this proves agent *logic* (deterministic-first ordering,
retries, schema validation, distance-threshold classification, logging), not that the
real API integration works, and not that `gemini-embedding-001` produces good real-world
skill-matching embeddings. **Before treating this as demo-ready:**

1. Set a real `GOOGLE_API_KEY` in `.env`.
2. Upload a real resume: `POST /api/documents/upload` (doc_type=resume) or `/paste`.
3. Ingest a real opportunity mentioning skills from that resume:
```bash
curl -X POST http://localhost:8000/api/opportunities/ingest \
  -H "Authorization: Bearer <your-token>" -H "Content-Type: application/json" \
  -d '{"raw_text": "Acme Corp is hiring a Backend Intern. Required: Python, AWS. Minimum CGPA 7.0.", "source": "manual"}'
```
4. Check the `skill_gap` field in the response. If skills you know are on the resume show
   up as `missing` or `weak` when they should be `matched` (or vice versa), the real
   embedding distances don't match the assumptions `MATCH_THRESHOLD`/`WEAK_THRESHOLD` in
   `app/agents/skill_gap.py` were set with — adjust them based on what you observe.

## Local run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Requires MongoDB running — either:
#   docker compose -f ../infra/docker/docker-compose.yml up mongo
# or a local `mongod`, or point MONGO_URI at MongoDB Atlas in .env

# Set GOOGLE_API_KEY in .env for ingestion and skill matching to actually work.

uvicorn app.main:app --reload --port 8000
```

Then visit `http://localhost:8000/docs` for interactive API docs. Chroma data persists
under `CHROMA_PERSIST_DIR` (default `./chroma_data`, gitignored).

## Testing

```bash
cd backend
python -m pytest -v
```

All 54 tests should pass, with **no MongoDB, no Gemini API key, no embedding API, and no
network access required** — the DB is mocked, the LLM and embedder are both faked.

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `password cannot be longer than 72 bytes` on any password | `bcrypt>=4.1` breaks passlib's version detection | Pinned (`bcrypt==4.0.1`) — if this recurs after installing something new (e.g. chromadb), see the note in `requirements.txt` about forcing a clean bcrypt reinstall |
| `TypeError: ...list_collection_names() got an unexpected keyword argument 'authorizedCollections'` in tests | `beanie>=2.0` incompatible with `mongomock` | Pinned (`beanie==1.29.0`) |
| `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` | `mcp>=2.0` renamed the FastMCP API | Pinned (`mcp==1.29.1`) |
| Installing `mcp`/`langgraph`/`chromadb` silently upgrades `starlette` or `bcrypt` | Transitive dependency resolution | Always `pip install -r requirements.txt` as a whole — key packages are explicitly pinned with comments explaining why |
| `502 Bad Gateway` from `/api/opportunities/ingest` | Discovery or Eligibility failed twice against the real Gemini API | Check `GOOGLE_API_KEY`/model names, check `AgentExecution` records in MongoDB for the actual error |
| `google.api_core.exceptions.NotFound: model not found` | Gemini model name in `.env` is stale/retired | Check https://ai.google.dev/gemini-api/docs/models |
| Skill Gap results look wrong (obvious matches showing as missing) | `MATCH_THRESHOLD`/`WEAK_THRESHOLD` in `app/agents/skill_gap.py` are unvalidated against real embeddings — see the limitation note above | Run the manual smoke test above and adjust the thresholds based on real observed distances |
| `pymongo.errors.ServerSelectionTimeoutError` when running the app | MongoDB isn't running / wrong `MONGO_URI` | Start MongoDB or check `.env` |

## Structure
```
app/api/routes/    # auth.py, opportunities.py, documents.py, profile.py, ingest.py
app/core/           # config.py, db.py, security.py, dedupe.py
app/models/          # user.py, opportunity.py, document.py, application.py, agent_execution.py
app/schemas/          # pydantic I/O schemas (per-route)
app/agents/            # schemas.py, llm_client.py, discovery.py, eligibility.py, skill_gap.py
app/graphs/               # opportunity_pipeline.py — the 3-node LangGraph workflow
app/mcp/                    # sandbox.py, filesystem_server.py, filesystem_client.py
                              # Gmail/GitHub/Calendar MCP land here, Gate 6+
app/retrieval/                 # chunking.py, embeddings.py, vector_store.py (Chroma)
tests/                           # conftest.py, fakes.py (FakeLLM + FakeEmbedder),
                                   # + one file per feature area
```
