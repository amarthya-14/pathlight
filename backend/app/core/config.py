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

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
