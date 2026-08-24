# Security Model

**Status:** Confirmed at Gate 1 (see blueprint §15). Implementation is Gate 2+ / Gate 11.

- AuthN: JWT (access + refresh), handled in FastAPI (e.g. via `fastapi-users` or a
  hand-rolled dependency — decide at Gate 2).
- AuthZ: role-based (STUDENT now; future roles out of scope for solo MVP).
- Secrets: env vars only, never committed (.gitignore covers .env*).
- MCP/OAuth tokens (Gmail, GitHub, Calendar): encrypted at rest, never logged, scoped to
  least-privilege access (read-only where possible; write access only to a
  Pathlight-owned calendar, never the user's whole calendar).
- Rate limiting: Redis-backed token bucket on public/auth endpoints.
- All LLM-produced structured output is schema-validated before being trusted.
- Audit: `AgentExecution` table + lightweight `AuditLog` for auth/data-deletion/MCP
  connect-disconnect events.
