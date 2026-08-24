# API Design

**Status:** Placeholder — finalized at Gate 2/3 alongside the database schema.

## Conventions (locked at Gate 1, Rev 2)
Single FastAPI service. **REST only** — GraphQL was dropped when the backend collapsed
to one service (see `ARCHITECTURE.md` §1); there's no longer a multi-domain aggregation
problem to justify it. The Next.js frontend uses a typed client generated from the FastAPI
OpenAPI schema.

## Planned endpoint groups
```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/documents/upload            # resume, JD, email paste
GET    /api/opportunities               # filter/sort by status, match score, deadline
GET    /api/opportunities/{id}
PATCH  /api/applications/{id}/status
GET    /api/dashboard/home              # aggregated home-screen payload (server-composed)
POST   /api/mcp/gmail/connect           # OAuth handoff for Gmail MCP
```

Exact schemas finalized once the DB models (Gate 2) are locked.
