# Pathlight Backend (FastAPI + LangGraph + MCP)

**Status:** Gate 3 done — auth, Opportunity CRUD, document ingestion, and a working
Filesystem MCP server/client are implemented and tested. Agents land at Gate 4.

**Architecture notes:**
- Originally scoped as a split Java (Spring Boot) + Python (FastAPI) backend for a
  4-person team. Now a solo project with MCP as a central pillar, so the two stacks were
  collapsed into one — see `docs/ARCHITECTURE.md` §1.
- Originally scoped on PostgreSQL. Switched to **MongoDB (via Beanie)** post-Gate-2 for
  developer familiarity/velocity — see `docs/ARCHITECTURE.md` §11.

## Responsibilities
- Authentication (JWT) and authorization — ✅ implemented
- Domain CRUD via Beanie/MongoDB — ✅ implemented (User, Profile, Company, Opportunity, Document)
- Deterministic rules: dedupe key (`company_id` + `role_hash`) — ✅ implemented as a
  MongoDB compound unique index
- Document ingestion (upload + text-paste, PDF text extraction) — ✅ implemented
- **Filesystem MCP** (server + client, sandboxed per-user document access) — ✅ implemented
- LangGraph agent workflows — planned, Gate 4
- Gmail/GitHub/Calendar MCP — planned, Gate 4/6+
- Embeddings + Chroma retrieval (RAG) — planned, Gate 5

## Local run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Requires MongoDB running — either:
#   docker compose -f ../infra/docker/docker-compose.yml up mongo
# or a local `mongod` on the default port, or point MONGO_URI at MongoDB Atlas in .env

uvicorn app.main:app --reload --port 8000
```

Then visit `http://localhost:8000/docs` for interactive API docs, or `http://localhost:8000/health`.

Uploaded documents are stored under `UPLOADS_ROOT` (default `./data/uploads`, gitignored)
in a per-user sandboxed subdirectory — see `app/mcp/sandbox.py`.

## Testing

```bash
cd backend
python -m pytest -v
```

Tests run against an isolated in-memory MongoDB mock (`mongomock-motor`) **and** an
isolated temp directory for document uploads (see `tests/conftest.py`) — no real MongoDB
or persistent disk state required to run the suite. All 17 tests should pass.

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `password cannot be longer than 72 bytes` on any password | `bcrypt>=4.1` breaks passlib's version detection | Already pinned in `requirements.txt` (`bcrypt==4.0.1`) |
| `TypeError: Database.list_collection_names() got an unexpected keyword argument 'authorizedCollections'` in tests | `beanie>=2.0` calls a MongoDB 5.0+ auth-aware method `mongomock` doesn't support | Already fixed by pinning `beanie==1.29.0` |
| `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` | `mcp>=2.0` renamed/restructured the FastMCP API | Already fixed by pinning `mcp==1.29.1` — don't upgrade without checking the migration guide |
| Installing `mcp` silently upgrades `starlette` and breaks FastAPI | `mcp`'s dependency resolution can pull a newer starlette than `fastapi==0.115.0` allows | Always `pip install -r requirements.txt` as a whole (starlette is explicitly pinned there), never `pip install mcp` standalone |
| `RuntimeError`/exceptions from `mcp_read_document`/`mcp_list_documents` come wrapped oddly if you bypass `filesystem_client.py` | `anyio.TaskGroup` wraps exceptions in a `BaseExceptionGroup` | Use the functions in `filesystem_client.py`, which already unwrap this — don't call `session.call_tool` directly elsewhere without the same handling |
| `pymongo.errors.ServerSelectionTimeoutError` when running the app (not tests) | MongoDB isn't running / wrong `MONGO_URI` | Start MongoDB (`docker compose up mongo`) or check `.env` |

## Structure
```
app/api/routes/    # auth.py, opportunities.py, documents.py
app/core/           # config.py, db.py (Beanie/Motor init), security.py
app/models/          # user.py, opportunity.py, document.py (Beanie Documents)
app/schemas/          # user.py, opportunity.py, document.py (pydantic I/O)
app/mcp/               # sandbox.py (shared path-safety logic), filesystem_server.py,
                         # filesystem_client.py — Gmail/GitHub/Calendar MCP land here, Gate 4/6+
app/agents/              # empty — Gate 4
app/graphs/                # empty — Gate 4
app/retrieval/               # empty — Gate 5
tests/                         # conftest.py + test_auth.py, test_health.py,
                                 # test_opportunities.py, test_documents.py, test_mcp_filesystem.py
```
