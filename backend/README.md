# Pathlight Backend (FastAPI + LangGraph + MCP)

**Status:** Gate 6 done — Discovery, Eligibility, Skill Gap, and Planner agents are all
implemented and tested, wired into a complete 4-node LangGraph pipeline, backed by a
Chroma vector store for semantic skill matching and GitHub/Calendar MCP tools. LLM +
embedding provider: Gemini — and, new at Gate 6, actually verified against the real
Gemini API (see the section below; this used to be an open limitation).

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
- **Skill Gap Agent** (Chroma + Gemini embeddings, distance-threshold classification + a
  deterministic negation guard, Gate 6) — ✅ implemented
- **Preparation Planner Agent** (deterministic skill-prerequisite ordering, no LLM call — Gate 6) — ✅ implemented
- **GitHub MCP** (read-only, public repos, supplementary Skill Gap evidence — Gate 6) — ✅ implemented
- **Calendar MCP** (writes to an internal CalendarEvent collection standing in for a real
  external calendar until OAuth exists — Gate 6) — ✅ implemented
- **RAG pipeline**: resume chunking → embedding → Chroma storage, at upload time — ✅ implemented
- **LangGraph pipeline** (Discovery → persist → Eligibility → Skill Gap → Planner, retry + needs_human_review fallback) — ✅ implemented
- Gmail MCP, private-repo GitHub access, real external Calendar — still planned, see `docs/ARCHITECTURE.md` §15

## ✅ Gemini calls verified against the real API (Gate 6)

Earlier gates (4/5) could only test against fakes — the original dev sandbox couldn't
reach Google's API. Gate 6 finally ran the real manual smoke test this section used to
ask for, and found (and fixed) three real bugs in the process — full writeup in
`docs/ARCHITECTURE.md` §15:
1. `LLM_MODEL_STRONG` was pointed at a model that doesn't exist; its real replacement
   needs a billing-enabled account this project doesn't have — moved to
   `gemini-3.6-flash`, confirmed working (including the ambiguous-eligibility path).
2. Skill Gap's `MATCH_THRESHOLD`/`WEAK_THRESHOLD` were recalibrated against real
   observed distances (still only a directional fix, not a full calibration — that's
   Gate 9's labeled benchmark set).
3. A structural negation-blindness bug (real embeddings can't tell "no experience with
   X" apart from "experienced with X") was fixed with a deterministic guard, not a
   threshold change.

To re-run this smoke test yourself (e.g. after changing a threshold or model name):

1. Set a real `GOOGLE_API_KEY` in `.env` (repo root, gitignored).
2. Upload a real resume: `POST /api/documents/upload` (doc_type=resume) or `/paste`.
3. Ingest a real opportunity mentioning skills from that resume:
```bash
curl -X POST http://localhost:8000/api/opportunities/ingest \
  -H "Authorization: Bearer <your-token>" -H "Content-Type: application/json" \
  -d '{"raw_text": "Acme Corp is hiring a Backend Intern. Required: Python, AWS. Minimum CGPA 7.0.", "source": "manual"}'
```
4. Check the `skill_gap` field in the response, and then
   `GET /api/applications/{id}/preparation-plan` for the auto-generated plan. If skills
   you know are on the resume show up as `missing`/`weak` when they shouldn't (or vice
   versa), the real embedding distances don't match `MATCH_THRESHOLD`/`WEAK_THRESHOLD`
   in `app/agents/skill_gap.py` — adjust based on what you observe, the same way Gate 6
   did.

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

All 80 tests should pass, with **no MongoDB, no Gemini API key, no embedding API, and no
network access required** — the DB is mocked, the LLM/embedder/GitHub HTTP calls are all
faked or monkeypatched. (A real Gemini API key + MongoDB + network access is only needed
for the manual smoke test above, not for `pytest`.)

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `password cannot be longer than 72 bytes` on any password | `bcrypt>=4.1` breaks passlib's version detection | Pinned (`bcrypt==4.0.1`) — if this recurs after installing something new (e.g. chromadb), see the note in `requirements.txt` about forcing a clean bcrypt reinstall |
| `TypeError: ...list_collection_names() got an unexpected keyword argument 'authorizedCollections'` in tests | `beanie>=2.0` incompatible with `mongomock` | Pinned (`beanie==1.29.0`) |
| `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` | `mcp>=2.0` renamed the FastMCP API | Pinned (`mcp==1.29.1`) |
| `ResolutionImpossible` installing requirements.txt | `mcp`'s own PyPI pins (pydantic/uvicorn) or google-genai's (httpx) moved past this project's pins | Already fixed as of Gate 6 (pydantic==2.11.5, uvicorn==0.31.1, httpx==0.28.1) — if it recurs, check what `mcp`/`google-genai` now require and bump to match, same pattern |
| Installing `mcp`/`langgraph`/`chromadb` silently upgrades `starlette` or `bcrypt` | Transitive dependency resolution | Always `pip install -r requirements.txt` as a whole — key packages are explicitly pinned with comments explaining why |
| `502 Bad Gateway` from `/api/opportunities/ingest` | Discovery or Eligibility failed twice against the real Gemini API | Check `GOOGLE_API_KEY`/model names, check `AgentExecution` records in MongoDB for the actual error |
| `google.api_core.exceptions.NotFound: model not found` | Gemini model name in `.env` is stale/retired | Check https://ai.google.dev/gemini-api/docs/models — and see `docs/ARCHITECTURE.md` §15: `gemini-3.1-pro` specifically doesn't exist and its preview replacement needs a billing-enabled account |
| Skill Gap results look wrong (obvious matches showing as missing) | `MATCH_THRESHOLD`/`WEAK_THRESHOLD` in `app/agents/skill_gap.py` are only a directional recalibration (Gate 6), not a full benchmark-validated fit | Run the manual smoke test above and adjust the thresholds based on real observed distances |
| `OperationFailure: db already exists with different case` | MongoDB db names collide case-insensitively even though stored case-sensitively — you likely have an existing db with different casing on the same `mongod` | Point `MONGO_DB_NAME` at a distinctly-named database, or drop the conflicting one if it's not needed |
| `pymongo.errors.ServerSelectionTimeoutError` when running the app | MongoDB isn't running / wrong `MONGO_URI` | Start MongoDB or check `.env` |

## Structure
```
app/api/routes/    # auth.py, opportunities.py, documents.py, profile.py, ingest.py, preparation.py
app/core/           # config.py, db.py, security.py, dedupe.py
app/models/          # user.py, opportunity.py, document.py, application.py, agent_execution.py,
                       # preparation.py, calendar_event.py
app/schemas/          # pydantic I/O schemas (per-route)
app/agents/            # schemas.py, llm_client.py, discovery.py, eligibility.py, skill_gap.py, planner.py
app/graphs/               # opportunity_pipeline.py — the 4-node LangGraph workflow
app/mcp/                    # sandbox.py, filesystem_server.py, filesystem_client.py,
                              # github_server.py, github_client.py, calendar_server.py, calendar_client.py
                              # Gmail MCP and private-repo/real-calendar access still land here later
app/retrieval/                 # chunking.py, embeddings.py, vector_store.py (Chroma)
tests/                           # conftest.py, fakes.py (FakeLLM + FakeEmbedder),
                                   # + one file per feature area
```
