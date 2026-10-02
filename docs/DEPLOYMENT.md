# Deployment

**Status:** Gate 11 — deployment-ready (verified locally in the production Docker image;
first live deploy pending). Target: free tier end to end, public URL, friends-then-campus.

| Piece | Host (free tier) | Why |
|---|---|---|
| Frontend (Next.js) | **Vercel** | Built for Next.js; every pushed branch gets its own preview URL — redesign the UI on a branch, share the preview with friends, merge when it's good. |
| Backend (FastAPI) | **Render** web service (Docker) | Free, deploys from `render.yaml`, Singapore region. |
| Database | **MongoDB Atlas M0** | Free 512MB cluster with auth built in (closes `SECURITY.md`'s "local Mongo has no auth" item). |
| Gmail polling | **GitHub Actions cron** | Free; wakes the sleeping backend every 30 min and triggers the poll. |

Local/demo fallback remains Docker Compose (`infra/docker/docker-compose.yml`).
Kubernetes stays out of scope (the "how this scales" viva answer).

## Free-tier realities (designed around, stated plainly)

- **Render free sleeps after 15 min idle** → first request after a nap takes ~30–60s.
  The in-process Gmail poller can't run while asleep, so `.github/workflows/gmail-poll.yml`
  calls `POST /api/internal/gmail/poll` (guarded by `CRON_SECRET`) every 30 min.
- **Render free has an ephemeral disk** — wiped on every restart/redeploy. MongoDB is the
  source of truth; nothing depends on disk surviving:
  - Chroma (resume vectors) is rebuilt lazily per user from the resume text stored in
    MongoDB (`vector_store.user_has_indexed_resume`).
  - Ingesting an uploaded document falls back to its MongoDB-stored text if the file is gone.
  - Tailored-resume PDFs are rendered on demand from MongoDB, never stored.
- **Gmail is capped at 100 users.** Gmail read/send are Google "restricted" scopes: while
  the OAuth app is in *Testing* mode, only manually-added test users (max 100) can connect,
  and their connection expires every 7 days (they click Reconnect). Publishing beyond that
  requires Google verification plus a paid third-party security assessment — not free.
  Everything except Gmail sourcing/sending works for anyone.
- **One shared Gemini key.** Free-tier rate limits are shared by all users; Google may use
  free-tier API data to improve its products — tell users before they upload resumes, or
  move to a paid key before a wider launch.

## Production safety (enforced in code)

With `ENVIRONMENT=production` the backend **refuses to start** if `JWT_SECRET` is
weak/default, `MONGO_URI` is localhost, `GOOGLE_API_KEY` is missing, Gmail is configured
without `TOKEN_ENCRYPTION_KEY`, or `FRONTEND_URL`/`GMAIL_OAUTH_REDIRECT_URI` still point at
localhost (`app/core/config.py::check_production_settings`). The container runs as a
non-root user; CORS allows only `CORS_ORIGINS` plus the optional `CORS_ORIGIN_REGEX`
(for Vercel previews).

## Step-by-step: first deploy

### 1. MongoDB Atlas
1. cloud.mongodb.com → create a free **M0** cluster (region: Mumbai/Singapore).
2. **Database Access** → add a user with a strong generated password.
3. **Network Access** → add `0.0.0.0/0` (Render's free tier has no fixed outbound IP).
4. **Connect → Drivers** → copy the `mongodb+srv://…` string, put the password in.

### 2. Backend on Render
1. Push this repo to GitHub.
2. render.com → **New → Blueprint** → select the repo. It reads `render.yaml`.
3. Fill the prompted secrets: `MONGO_URI` (Atlas), `GOOGLE_API_KEY`,
   `GMAIL_MCP_CLIENT_ID`/`SECRET`, `TOKEN_ENCRYPTION_KEY` (generate a new one), and leave
   `FRONTEND_URL`/`CORS_ORIGINS`/`GMAIL_OAUTH_REDIRECT_URI` for after step 3 — but the
   service will refuse to start until they're set (by design), so set placeholders:
   `FRONTEND_URL=https://pathlight.vercel.app`, `CORS_ORIGINS` the same.
4. Once live, note the URL, e.g. `https://pathlight-api.onrender.com`; check `/health`.

### 3. Frontend on Vercel
1. vercel.com → **Add New → Project** → import the repo.
2. **Root Directory:** `frontend`. Framework: Next.js (auto-detected).
3. Env var: `NEXT_PUBLIC_API_URL=https://pathlight-api.onrender.com` → **Deploy**.
4. Note the production URL, e.g. `https://pathlight-xyz.vercel.app`.

### 4. Wire them together (Render → Environment)
- `FRONTEND_URL` and `CORS_ORIGINS` = the Vercel production URL.
- `CORS_ORIGIN_REGEX` = `^https://pathlight-[a-z0-9-]+\.vercel\.app$` (adjust to your
  Vercel project name) so preview deployments can call the API.
- `GMAIL_OAUTH_REDIRECT_URI` = `https://<render-url>/api/integrations/gmail/callback`.

### 5. Google OAuth client
Google Cloud Console → your OAuth client → **Authorized redirect URIs** → add the
production callback above (keep the localhost one for local dev). Add each friend's Gmail
under **Audience → Test users**.

### 6. Gmail poll cron (GitHub → Settings → Secrets and variables → Actions)
- Secrets: `BACKEND_URL` = Render URL, `CRON_SECRET` = the value Render generated.
- Variables: `ENABLE_GMAIL_POLL` = `true`. Run it once via **Actions → Gmail poll → Run workflow**.

### 7. CI
`.github/workflows/ci.yml` runs backend tests and frontend typecheck/tests/build on every
push and PR to `main`. Render and Vercel auto-deploy `main` once it's pushed.
