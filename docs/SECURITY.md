# Security Model

**Status:** Core auth implemented at Gate 2; MCP/OAuth and rate limiting are still planned.

## Implemented
- AuthN: JWT bearer tokens (access token only, 24h expiry), FastAPI OAuth2 password flow.
- Passwords: bcrypt via passlib (pinned to `bcrypt==4.0.1` — see `ARCHITECTURE.md` §10 for
  why the pin is required).
- Secrets: env vars only (`.env`, gitignored); `.env.example` documents required keys,
  including `MONGO_URI` (no credentials in it for local dev — add auth before any real
  deployment, since the default Docker Compose Mongo has no auth configured).
- Dedupe/uniqueness enforced at the database level via MongoDB unique indexes, not just
  application code (verified directly, see `ARCHITECTURE.md` §11).

## Planned
- **MongoDB auth**: the local dev `mongo:7` container currently has no authentication
  enabled — fine for local Docker Compose, but must be enabled (username/password, or a
  managed MongoDB Atlas free tier with auth built in) before any cloud deployment (Gate 10).
- Refresh tokens (currently access-token-only, which is fine for a semester demo but
  should be revisited if session length becomes an issue).
- AuthZ: role-based (STUDENT now; no other roles needed for solo MVP).
- MCP/OAuth tokens (Gmail, GitHub, Calendar): encrypted at rest, never logged, scoped to
  least-privilege access — implemented alongside each MCP tool starting Gate 4.
- Rate limiting: Redis-backed token bucket on public/auth endpoints.
- All LLM-produced structured output schema-validated before being trusted (principle
  locked in `AI_DESIGN.md`; enforced once agents exist at Gate 4).
- Audit: `AgentExecution` collection (Gate 4) + lightweight `AuditLog` for auth/
  data-deletion/MCP connect-disconnect events.
