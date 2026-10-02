# Security Model

**Status:** Core auth implemented at Gate 2; MCP/OAuth and rate limiting are still
planned. GitHub and Calendar MCP were added at Gate 6, but both deliberately **without**
real OAuth — see the note below.

## Implemented
- AuthN: JWT bearer tokens (access token only, 24h expiry), FastAPI OAuth2 password flow.
- CORS (Gate 8): `CORSMiddleware` restricts browser-originated requests to the explicit
  origins in `CORS_ORIGINS` (`.env`, default `http://localhost:3000`) — found missing via
  real browser testing of the new frontend, not assumed; every request failed at the
  preflight step until this was added (see `docs/ARCHITECTURE.md` §16).
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
  managed MongoDB Atlas free tier with auth built in) before any cloud deployment (Gate 11).
- Refresh tokens (currently access-token-only, which is fine for a semester demo but
  should be revisited if session length becomes an issue).
- AuthZ: role-based (STUDENT now; no other roles needed for solo MVP).
- MCP/OAuth tokens (Gmail, GitHub, Calendar): encrypted at rest, never logged, scoped to
  least-privilege access — implemented alongside each MCP tool starting Gate 4.
  **Scope decision at Gate 6, stated plainly**: GitHub MCP and Calendar MCP were built
  this gate, but *without* real per-user OAuth — GitHub is read-only public-repo access
  via an optional shared app-level PAT (not a per-user token), and Calendar MCP writes
  to an internal `CalendarEvent` collection rather than calling a real external calendar
  API. Building real OAuth for either now, ahead of this section's own token-encryption
  work, would mean shipping plaintext per-user tokens — worse than deferring both
  cleanly. See `docs/ARCHITECTURE.md` §15 for the full reasoning. Encrypting real OAuth
  tokens is brought forward to Gate 10 (`docs/AUTONOMOUS_APPLICATIONS.md` §2/§5) — Gmail
  MCP is the first tool in this project that needs a real per-user OAuth token, so the
  encryption work can no longer be deferred to Gate 12. **Implemented:** Fernet
  (`app/core/crypto.py`) with `TOKEN_ENCRYPTION_KEY`; with no key configured the Gmail
  connect route returns 503 rather than ever storing plaintext. A test asserts no
  plaintext token substring reaches the stored `Integration` document or any API response.
  Key rotation (MultiFernet) is still deferred.
- Gmail OAuth (Gate 10): least-privilege scopes only (`gmail.readonly` + `gmail.send`);
  the OAuth `state` is a 10-minute signed JWT with a `purpose` claim, so a forged state —
  or a normal login token replayed as one — can't complete a flow into someone else's
  account. Disconnect revokes the token with Google and deletes the row.
- Irreversible actions (Gate 10): sending an application email is reachable only from
  `POST /api/applications/{id}/review` — enforced by an AST-scanning test
  (`tests/test_gmail_mcp.py::test_send_is_only_reachable_from_review_route`), not by
  convention. Sends are never auto-retried (a timed-out send may have gone through).
- Rate limiting: Redis-backed token bucket on public/auth endpoints.
- All LLM-produced structured output schema-validated before being trusted (principle
  locked in `AI_DESIGN.md`; enforced once agents exist at Gate 4).
- Audit: `AgentExecution` collection (Gate 4) + lightweight `AuditLog` for auth/
  data-deletion/MCP connect-disconnect events.
