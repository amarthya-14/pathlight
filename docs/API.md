# API Design

**Status:** Gate 2 subset implemented. REST only — GraphQL was dropped when the backend
collapsed to a single service (see `ARCHITECTURE.md` §1).

## Implemented
```
POST   /api/auth/register          201 -> UserOut | 409 if email exists
POST   /api/auth/login              200 -> {access_token, token_type} | 401 if bad creds
GET    /api/auth/me                  200 -> UserOut (auth required)
POST   /api/opportunities             201 -> OpportunityOut | 409 if duplicate (auth required)
GET    /api/opportunities              200 -> [OpportunityOut] (auth required)
POST   /api/documents/upload            201 -> DocumentDetailOut | 415 unsupported type | 413 too large (auth required)
POST   /api/documents/paste              201 -> DocumentDetailOut (auth required)
GET    /api/documents                     200 -> [DocumentOut] (auth required)
GET    /api/documents/{id}                 200 -> DocumentDetailOut | 404 if not found/not owned (auth required)
PUT    /api/profile                          200 -> ProfileOut (auth required)
GET    /api/profile                           200 -> ProfileOut (id=null if not created yet, auth required)
POST   /api/opportunities/ingest               200 -> IngestResponse | 400 bad request | 404 document not found/owned | 502 needs_human_review (auth required)
GET    /health                                  200 -> {"status": "ok"}
```
Interactive docs available at `/docs` (Swagger UI) once the server is running.

`POST /api/opportunities/ingest` runs the Discovery → Eligibility → Skill Gap LangGraph
pipeline (`app/graphs/opportunity_pipeline.py`). Body is either
`{"raw_text": "...", "source": "manual"}` or `{"document_id": "..."}` (reads the
document's content via the Filesystem MCP tool) — exactly one of the two, not both.
`IngestResponse.skill_gap` is null if the opportunity had no extracted skills to check;
`skill_gap_note` explains when a skill gap result exists but is based on "no resume on
file" rather than real evidence.

Note: all IDs in responses are MongoDB ObjectId strings (24 hex characters), not UUIDs —
this changed when the database switched from PostgreSQL to MongoDB (`ARCHITECTURE.md` §11).

## Planned (later gates)
```
GET    /api/opportunities/{id}          # Gate 5+
PATCH  /api/applications/{id}/status    # Gate 5+ (manual stage updates beyond DISCOVERED/ELIGIBILITY_CHECKED)
GET    /api/dashboard/home              # Gate 8, server-composed aggregation
POST   /api/mcp/gmail/connect           # Gate 6+, OAuth handoff for Gmail MCP
```
