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
    GOOGLE_API_KEY: str = ""
    LLM_MODEL_SMALL: str = "gemini-3.1-flash-lite"  # cheap/fast — Discovery Agent extraction
    LLM_MODEL_STRONG: str = "gemini-3.1-pro"  # stronger reasoning — ambiguous Eligibility cases
    EMBEDDING_MODEL: str = "gemini-embedding-001"  # GA text embedding model, verified current Sep 2026

    # Vector store (Chroma) — used by the Skill Gap Agent (Gate 5)
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
