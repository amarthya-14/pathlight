"""
Application configuration, loaded from environment variables (.env at repo root).
See ../../.env.example for the full list of expected variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database (MongoDB)
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "pathlight"

    # Auth
    JWT_SECRET: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h — fine for dev/demo, revisit for prod

    # File storage (sandboxed document uploads — see app/mcp/sandbox.py)
    UPLOADS_ROOT: str = "./data/uploads"

    # LLM — Gemini (Google), used from Gate 4 onward.
    # Model defaults verified current as of Aug 2026: gemini-2.0-flash and gemini-2.5-pro
    # are being retired by Google (2.0-flash already shut down; 2.5-pro shuts down
    # Oct 2026), so this project intentionally does NOT default to either. Check
    # https://ai.google.dev/gemini-api/docs/models before changing these — model names
    # and availability change frequently.
    #
    # Gate 6 real-API smoke test (2026-09-12, see docs/ARCHITECTURE.md §15): the
    # previous LLM_MODEL_STRONG default, "gemini-3.1-pro", does not exist — the real
    # API's ListModels response has no such model, and calling it 404s
    # (models/gemini-3.1-pro is not found for API version v1beta). This had never been
    # caught because every prior gate's tests use FakeLLM, which doesn't validate model
    # names at all. Its real replacement, "gemini-3.1-pro-preview", DOES exist (confirmed
    # via ListModels and by triggering a real 429 against it, not a 404) but returned
    # "limit: 0" on every pro-tier quota metric for this project's free-tier API key —
    # i.e. the entire gemini-3.1-pro family requires a billing-enabled account, which
    # this project doesn't have. Rather than ship a "strong" model this key can never
    # actually call, LLM_MODEL_STRONG was moved to "gemini-3.6-flash" — confirmed
    # working end-to-end (HTTP 200, extended-thinking tokens present in the response) on
    # the free tier, and a genuinely stronger/newer model than LLM_MODEL_SMALL despite
    # being in the flash family. If this project ever moves to a billing-enabled key,
    # reverting to a real pro-tier model for ambiguous-eligibility reasoning is a
    # one-line config change, not a code change.
    GOOGLE_API_KEY: str = ""
    LLM_MODEL_SMALL: str = "gemini-3.1-flash-lite"  # cheap/fast — Discovery Agent extraction
    LLM_MODEL_STRONG: str = "gemini-3.6-flash"  # stronger reasoning — ambiguous Eligibility cases
    EMBEDDING_MODEL: str = "gemini-embedding-001"  # GA text embedding model, verified current Sep 2026

    # Vector store (Chroma) — used by the Skill Gap Agent (Gate 5)
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # GitHub MCP (Gate 6) — read-only, public repos only for now (see
    # app/mcp/github_server.py's scope-decision docstring). This is an app-level PAT
    # purely for higher unauthenticated rate limits, NOT per-user OAuth.
    GITHUB_MCP_TOKEN: str = ""

    # CORS (Gate 8) — the browser blocks cross-origin requests (frontend on :3000,
    # backend on :8000) without this: a real bug caught by actually driving the new
    # frontend in a browser, not by pytest (TestClient bypasses CORS entirely — no
    # existing test could have caught this). Comma-separated origins, matching
    # NEXT_PUBLIC_API_URL's counterpart on the frontend side (.env.example).
    CORS_ORIGINS: str = "http://localhost:3000"
    # Gate 11: optional regex for extra allowed origins — Vercel gives every preview
    # deployment its own URL (pathlight-git-<branch>-<user>.vercel.app), which a fixed
    # list can't cover. e.g. ^https://pathlight-[a-z0-9-]+\.vercel\.app$
    CORS_ORIGIN_REGEX: str = ""

    # Gate 11 — deployment. "production" turns on fail-fast checks for insecure defaults.
    ENVIRONMENT: str = "development"
    # Shared secret for POST /api/internal/gmail/poll, called by a GitHub Actions cron.
    # Free hosts (Render) sleep when idle, and a sleeping server's in-process poller
    # doesn't run — the cron both wakes it and triggers the poll. Empty = route disabled.
    CRON_SECRET: str = ""

    # Gate 10 — Gmail MCP (real per-user Google OAuth2) + autonomous applications. See
    # docs/AUTONOMOUS_APPLICATIONS.md. GMAIL_MCP_CLIENT_ID/SECRET have been stubbed in
    # .env.example since Gate 0; this is the first gate that actually reads them.
    GMAIL_MCP_CLIENT_ID: str = ""
    GMAIL_MCP_CLIENT_SECRET: str = ""
    # Must exactly match an "Authorized redirect URI" on the Google Cloud OAuth client.
    GMAIL_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/integrations/gmail/callback"
    # Where the OAuth callback sends the browser back to once it's done.
    FRONTEND_URL: str = "http://localhost:3000"
    # Fernet key for OAuth tokens at rest (app/core/crypto.py). Generate once with
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # and never commit it. Empty = Gmail integration disabled (connect returns 503), never
    # a silent fallback to plaintext storage.
    TOKEN_ENCRYPTION_KEY: str = ""
    GMAIL_POLL_ENABLED: bool = True
    GMAIL_POLL_INTERVAL_SECONDS: int = 900
    # Inspection-based starting allowlist, NOT a validated list (see
    # docs/AUTONOMOUS_APPLICATIONS.md §10) — comma-separated sender addresses whose mail
    # is treated as a job alert. Anything else in the inbox is never read by the poller.
    GMAIL_ALERT_SENDERS: str = (
        "jobalerts-noreply@linkedin.com,jobs-noreply@linkedin.com,"
        "noreply@naukri.com,info@naukri.com,naukrialerts@naukri.com"
    )

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()


def check_production_settings(s: Settings) -> list[str]:
    """Insecure defaults that are fine locally but must never reach a public deployment.
    Returns the problems found; app startup refuses to run in production if any exist."""
    problems = []
    if s.JWT_SECRET in ("", "changeme") or len(s.JWT_SECRET) < 32:
        problems.append("JWT_SECRET must be a random string of at least 32 characters")
    if "localhost" in s.MONGO_URI or "127.0.0.1" in s.MONGO_URI:
        problems.append("MONGO_URI points at localhost — use your MongoDB Atlas connection string")
    if not s.GOOGLE_API_KEY or s.GOOGLE_API_KEY == "changeme":
        problems.append("GOOGLE_API_KEY is not set")
    if s.GMAIL_MCP_CLIENT_ID and not s.TOKEN_ENCRYPTION_KEY:
        problems.append("TOKEN_ENCRYPTION_KEY is required when Gmail is configured")
    if s.GMAIL_MCP_CLIENT_ID and "localhost" in s.GMAIL_OAUTH_REDIRECT_URI:
        problems.append("GMAIL_OAUTH_REDIRECT_URI still points at localhost")
    if "localhost" in s.FRONTEND_URL:
        problems.append("FRONTEND_URL still points at localhost")
    return problems
