# Deployment

**Status:** Gate 11 — deployment-ready (verified locally in the production Docker image;
first live deploy pending). Target: free tier end to end, public URL, friends-then-campus.

| Piece | Host (free tier) | Why |
|---|---|---|
| Frontend (Next.js) | **Vercel** | Built for Next.js; every pushed branch gets its own preview URL — redesign the UI on a branch, share the preview with friends, merge when it's good. |
| Backend (FastAPI) | **Render** web service (Docker) | Free, deploys from `render.yaml`, Singapore region. |
| Database | **MongoDB Atlas M0** | Free 512MB cluster with auth built in (closes `SECURITY.md`'s "local Mongo has no auth" item). |
| Gmail polling | **GitHub Actions cron** | Free; wakes the sleeping backend once a day (09:00 IST) and triggers the poll. |

Local/demo fallback remains Docker Compose (`infra/docker/docker-compose.yml`).
Kubernetes stays out of scope (the "how this scales" viva answer).

## Free-tier realities (designed around, stated plainly)

- **Render free sleeps after 15 min idle** → first request after a nap takes ~30–60s.
  The in-process Gmail poller can't run while asleep, so `.github/workflows/gmail-poll.yml`
  calls `POST /api/internal/gmail/poll` (guarded by `CRON_SECRET`) once a day. Users
  are only polled when their last check is ~a day old, so server wake-ups don't re-poll.
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
- **Gemini free tier is tiny for the strong model — measured, not assumed.** On
  2026-10-03 `gemini-3.6-flash` returned `429 RESOURCE_EXHAUSTED` with
  `GenerateRequestsPerDayPerProjectPerModel-FreeTier, limit: 20` — i.e. **20 strong-model
  requests per day for the whole deployment**. Resume tailoring and LLM-path eligibility
  use the strong model. Mitigation in code: `get_strong_llm()` falls back to the small
  model (separate quota) on any failure, verified live against that real 429. For a
  campus launch, a billing-enabled key (pay-as-you-go flash pricing is cents per day at
  this scale) is the real fix.
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

## Launch checklist (startup-ready off-campus)

Required:
1. Render env: `ADMIN_EMAILS` = your email (unlocks `/admin`: users, funnel, AI errors, job sources).
2. Vercel env: `NEXT_PUBLIC_CONTACT_EMAIL` (shown on /privacy and /terms).
3. GitHub repo variable `ENABLE_GMAIL_POLL=true` — the daily cron also runs **Autopilot**.

Strongly recommended:
4. **Fresher jobs:** free keys from Adzuna (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`) and Jooble
   (`JOOBLE_API_KEY`). Company career pages are mostly experienced hiring; aggregators are
   where entry-level roles in India are. Check `/admin` → Job sources after the next refresh.
5. **Google sign-in for everyone:** create a second OAuth client in a separate Google Cloud
   project, scopes `openid email profile` only, publish it (no verification needed for these
   scopes), add `https://<render-url>/api/auth/google/callback` as a redirect URI, and set
   `GOOGLE_LOGIN_CLIENT_ID/SECRET/REDIRECT_URI`. Without this, sign-in falls back to the Gmail
   client, which is limited to its 100 test users.
6. **Password reset:** `SMTP_HOST=smtp.gmail.com`, `SMTP_USER`/`SMTP_PASSWORD` (a Gmail App
   Password on a dedicated account), `SMTP_FROM`. Without it, "Forgot password" points users
   to Google sign-in.

Before Gmail can leave testing (more than 100 users): Google's restricted-scope verification
for `gmail.readonly`/`gmail.send` needs the published privacy policy (`/privacy` — it includes
the Limited Use statement) and a security assessment. Plan for weeks, not days.

Limits built in: per-user daily AI budgets (`app/core/usage.py`: 25 analyses, 12 tailored
resumes, 3 autopilot jobs) so one user can't exhaust the shared Gemini quota. If the strong
model's free quota (~20/day/project) becomes the bottleneck, a billing-enabled key is the fix.

### AI keys and fallbacks
- Students can add their own key for Google Gemini (free, via Google AI Studio), Groq (free),
  OpenAI, Anthropic Claude, or any OpenAI-compatible API in **Profile → Your AI keys**.
  Keys are verified with the provider, stored encrypted (needs `TOKEN_ENCRYPTION_KEY`), and
  tried first for that student's requests; they also get 4x the daily limits.
- Every AI call falls back in order: the student's keys → `GOOGLE_API_KEY` →
  `GOOGLE_API_KEYS` (extra shared keys) → the small model on each → `LLM_EXTRA_FALLBACK_MODELS`.
- Resume embeddings always use Gemini (the stored vectors must come from one model): the
  student's Gemini key if they added one, else the shared keys.

### Forwarded job alerts (LinkedIn/Naukri alerts for every student, no Google review)

Students forward their alert emails to a private address (`<token>@<your domain>`); a free
Cloudflare Email Worker hands each message to Pathlight. No inbox access is requested, so
this has no 100-user limit. Until it's set up, the Job alerts page shows it as "Coming soon".

1. **Get a domain** (any registrar, a few hundred rupees a year) — ideally one used only for
   this, e.g. `pathlightmail.in`.
2. **Add it to Cloudflare** (free plan): Cloudflare dashboard → **Add a domain** → follow the
   steps → at your registrar, change the nameservers to the two Cloudflare shows. Wait until
   Cloudflare says the domain is **Active**.
3. **Create the worker:** **Workers & Pages → Create → Create Worker** → name it
   `pathlight-inbound` → **Deploy** → **Edit code** → replace everything with
   `infra/email-worker/worker.js` → **Deploy**.
4. **Worker settings → Variables and Secrets:**
   - `PATHLIGHT_INBOUND_URL` (Text) = `https://<render-host>/api/inbound/email`
   - `INBOUND_SECRET` (Secret) = a long random string. Generate one with
     `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
5. **Route mail to it:** your domain → **Email → Email Routing → Enable** (Cloudflare adds the
   MX records) → **Routing rules → Catch-all address → Edit** → Action **Send to a Worker** →
   `pathlight-inbound` → **Save** → make sure the catch-all is **enabled**.
6. **Render env:** `INBOUND_EMAIL_DOMAIN` = your domain (e.g. `pathlightmail.in`) and
   `INBOUND_WEBHOOK_SECRET` = the same random string as step 4 → **Save, rebuild, and deploy**.
7. **Keep the backend awake (recommended):** Render's free server sleeps after 15 minutes and
   takes up to a minute to wake; the worker retries for ~50s, but staying awake is safer. At
   https://cron-job.org create a free job that opens `https://<render-host>/health` every
   10 minutes. (Render's free plan includes 750 hours a month — enough for one service
   running all month.)
8. **Test:** in Pathlight → **Job alerts**, copy your address and send it any email from your
   phone. Within a minute **Recent** shows "Ignored — not a job alert": delivery works. Then
   follow the three steps on that page to set up Gmail forwarding.

