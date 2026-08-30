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

    # LLM (used from Gate 4 onward)
    LLM_API_KEY: str = ""
    LLM_MODEL_SMALL: str = ""
    LLM_MODEL_STRONG: str = ""

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
