# API Design

**Status:** Through Gate 6 implemented. REST only — GraphQL was dropped when the backend
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
PUT    /api/profile                          200 -> ProfileOut (auth required, accepts optional github_username since Gate 6)
GET    /api/profile                           200 -> ProfileOut (id=null if not created yet, auth required)
POST   /api/opportunities/ingest               200 -> IngestResponse | 400 bad request | 404 document not found/owned | 502 needs_human_review (auth required)
POST   /api/applications/{id}/preparation-plan  200 -> PreparationPlanOut | 400 no skill_gap yet / nothing to plan | 404 not found/owned (auth required) — Gate 6
GET    /api/applications/{id}/preparation-plan   200 -> PreparationPlanOut | 404 no plan generated yet (auth required) — Gate 6
GET    /health                                  200 -> {"status": "ok"}
```
Interactive docs available at `/docs` (Swagger UI) once the server is running.

`POST /api/opportunities/ingest` runs the Discovery → Eligibility → Skill Gap → Planner
LangGraph pipeline (`app/graphs/opportunity_pipeline.py`). Body is either
`{"raw_text": "...", "source": "manual"}` or `{"document_id": "..."}` (reads the
document's content via the Filesystem MCP tool) — exactly one of the two, not both.
`IngestResponse.skill_gap` is null if the opportunity had no extracted skills to check;
`skill_gap_note` explains when a skill gap result exists but is based on "no resume on
file" rather than real evidence. `SkillGapResult` also carries `github_evidence` (skill →
matching public repo names, Gate 6, only populated if the caller's Profile has a
`github_username` set) and `github_unavailable` (the GitHub lookup couldn't be
completed — distinct from "checked, found nothing").

If the pipeline found missing/weak skills, it auto-generates a first-pass
`PreparationPlan` (a default hours/day assumption — see `app/agents/planner.py`) —
fetch it via `GET /api/applications/{id}/preparation-plan`, or replace it with a plan
based on your real available time via `POST` with `{"hours_per_day": <float>}`.
`PreparationPlanOut.feasible` is `null`, not `false`, when there isn't enough
information (no deadline) to judge feasibility — don't render that as "not feasible."

Note: all IDs in responses are MongoDB ObjectId strings (24 hex characters), not UUIDs —
this changed when the database switched from PostgreSQL to MongoDB (`ARCHITECTURE.md` §11).

## Planned (later gates)
```
GET    /api/opportunities/{id}          # Gate 5+
PATCH  /api/applications/{id}/status    # Gate 5+ (manual stage updates beyond DISCOVERED/ELIGIBILITY_CHECKED)
GET    /api/dashboard/home              # Gate 8, server-composed aggregation
POST   /api/mcp/gmail/connect           # Gate 6+, OAuth handoff for Gmail MCP
```
