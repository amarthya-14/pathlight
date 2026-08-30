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
GET    /health                              200 -> {"status": "ok"}
```
Interactive docs available at `/docs` (Swagger UI) once the server is running.

Note: all IDs in responses are MongoDB ObjectId strings (24 hex characters), not UUIDs —
this changed when the database switched from PostgreSQL to MongoDB (`ARCHITECTURE.md` §11).

## Planned (later gates)
```
GET    /api/opportunities/{id}          # Gate 4
PATCH  /api/applications/{id}/status    # Gate 4+
GET    /api/dashboard/home              # Gate 8, server-composed aggregation
POST   /api/mcp/gmail/connect           # Gate 4, OAuth handoff for Gmail MCP
```
