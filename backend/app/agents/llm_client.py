"""
Thin wrapper around the Gemini chat models, kept in one place so:
- The provider can be swapped later without touching agent logic.
- Tests can monkeypatch get_small_llm()/get_strong_llm() to return a fake model, so
  agent logic (deterministic-rules-first, retries, schema validation, AgentExecution
  logging) is fully testable without a real network call or API key.

IMPORTANT, stated plainly rather than glossed over: this sandbox's network egress is
limited to package registries and cannot reach generativelanguage.googleapis.com, so the
actual live Gemini call is UNVERIFIED here. Every agent test in this codebase uses a fake
LLM (see tests/test_discovery_agent.py, tests/test_eligibility_agent.py) to test pipeline
logic — none of them prove the real API integration works. Set a real GOOGLE_API_KEY and
run a manual smoke test before treating Gate 4 as demo-ready.
"""
from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings


@lru_cache
def get_small_llm() -> ChatGoogleGenerativeAI:
    """Cheap/fast model for structured extraction (Discovery Agent)."""
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL_SMALL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0,
    )


@lru_cache
def get_strong_llm() -> ChatGoogleGenerativeAI:
    """Stronger model for ambiguous reasoning (Eligibility Agent, only when deterministic
    rules alone can't decide — see app/agents/eligibility.py)."""
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL_STRONG,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0,
    )
