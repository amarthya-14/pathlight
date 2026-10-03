"""
AI clients for every agent: the student's own provider keys first, then shared fallbacks.

Chain for every call (each link is tried only if the previous one fails — quota, overload,
invalid key, a model that can't produce the structured output):
1. The student's own keys (app/core/ai_providers.py: Gemini, Groq, OpenAI, Anthropic or
   any OpenAI-compatible API), in the order they added them — their quota, so the shared
   free quota isn't their bottleneck. Set per request by app/api/deps.py, and per student
   by background workers via `llm_for_user`.
2. The server's Gemini keys: GOOGLE_API_KEY, then GOOGLE_API_KEYS (comma-separated).
Strong-model links come first; small/fast-model links follow; then LLM_EXTRA_FALLBACK_MODELS.

Tests monkeypatch get_small_llm()/get_strong_llm() with fakes (tests/fakes.py); both keep
their no-argument signature and expose the one method agents use:
with_structured_output(schema).
"""
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings

# The current student's keys, decrypted: [{provider, key, strong, small, base_url}, ...].
# A ContextVar so concurrent requests and background tasks never see each other's keys.
_user_keys: ContextVar[tuple[dict, ...]] = ContextVar("pathlight_user_ai_keys", default=())


def set_user_keys(keys: list[dict]) -> None:
    _user_keys.set(tuple(keys))


def using_own_key() -> bool:
    return bool(_user_keys.get())


def server_keys() -> list[str]:
    keys = [settings.GOOGLE_API_KEY] + [k.strip() for k in settings.GOOGLE_API_KEYS.split(",")]
    return list(dict.fromkeys(k for k in keys if k)) or [""]


def gemini_keys() -> list[str]:
    """Gemini keys only — the student's, then the server's (used for embeddings, whose
    vectors must all come from the same model)."""
    own = [k["key"] for k in _user_keys.get() if k["provider"] == "gemini"]
    return list(dict.fromkeys(own + server_keys()))


class _Link:
    """One (provider, model, key) in the chain."""

    def __init__(self, label: str, chat, method: str | None = None):
        self.label = label
        self.chat = chat
        self.method = method

    def with_structured_output(self, schema):
        if self.method:
            return self.chat.with_structured_output(schema, method=self.method)
        return self.chat.with_structured_output(schema)


@lru_cache(maxsize=128)
def _gemini(model: str, key: str) -> ChatGoogleGenerativeAI:
    # Few retries per link: a failing link should hand over to the next quickly instead of
    # backing off for a minute against an exhausted quota.
    return ChatGoogleGenerativeAI(model=model, google_api_key=key, temperature=0, max_retries=1)


@lru_cache(maxsize=128)
def _openai_compatible(model: str, key: str, base_url: str):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, api_key=key, base_url=base_url, temperature=0, max_retries=1, timeout=90)


@lru_cache(maxsize=64)
def _anthropic(model: str, key: str):
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, api_key=key, temperature=0, max_retries=1, max_tokens=8192, timeout=90)


def _own_link(k: dict, model: str) -> _Link:
    from app.core.ai_providers import PROVIDERS

    provider = k["provider"]
    label = f"{provider}:{model}"
    if provider == "gemini":
        return _Link(label, _gemini(model, k["key"]))
    if provider == "anthropic":
        return _Link(label, _anthropic(model, k["key"]))
    base_url = k.get("base_url") or PROVIDERS[provider].base_url
    # OpenAI supports strict JSON-schema output; other compatible APIs reliably support
    # tool calling, which LangChain uses to get the same structured result.
    method = None if provider == "openai" else "function_calling"
    return _Link(label, _openai_compatible(model, k["key"], base_url), method)


class FallbackLLM:
    """An ordered chain of links behind the one method agents call."""

    def __init__(self, links: list[_Link]):
        self.links = links

    def with_structured_output(self, schema):
        runnables = [link.with_structured_output(schema) for link in self.links]
        return runnables[0].with_fallbacks(runnables[1:]) if len(runnables) > 1 else runnables[0]


def _chain(tiers: list[str]) -> FallbackLLM:
    """tiers: which model of each key, in order — e.g. ["strong", "small"]."""
    own = _user_keys.get()
    extra = [m.strip() for m in settings.LLM_EXTRA_FALLBACK_MODELS.split(",") if m.strip()]
    server_model = {"strong": settings.LLM_MODEL_STRONG, "small": settings.LLM_MODEL_SMALL}
    links: list[_Link] = []
    seen: set[str] = set()

    def add(link_key: str, make):
        if link_key not in seen:
            seen.add(link_key)
            links.append(make())

    for tier in tiers:
        for k in own:
            model = k[tier]
            # Same identity as a server Gemini link, so a student key equal to a server key
            # isn't tried twice.
            add(f"{k['provider']}:{model}:{k['key']}", lambda k=k, model=model: _own_link(k, model))
        for key in server_keys():
            model = server_model[tier]
            add(f"gemini:{model}:{key}", lambda model=model, key=key: _Link(f"gemini:{model}", _gemini(model, key)))
    for model in extra:
        for key in server_keys():
            add(f"gemini:{model}:{key}", lambda model=model, key=key: _Link(f"gemini:{model}", _gemini(model, key)))
    return FallbackLLM(links)


def get_small_llm() -> FallbackLLM:
    """Cheap/fast model for structured extraction (Discovery Agent)."""
    return _chain(["small"])


def get_strong_llm() -> FallbackLLM:
    """Stronger model for generation and ambiguous reasoning (Resume Tailor, Eligibility),
    falling back to fast models — Gemini's free strong tier allows only ~20 requests a day
    per project (measured, see docs/DEPLOYMENT.md)."""
    return _chain(["strong", "small"])


@asynccontextmanager
async def llm_for_user(user_id):
    """Background work (Gmail alerts, autopilot) runs outside any request: this makes the
    student's own keys apply to everything inside the block."""
    from app.core.ai_providers import load_user_keys  # local: avoids a models import cycle

    token = _user_keys.set(tuple(await load_user_keys(user_id)))
    try:
        yield
    finally:
        _user_keys.reset(token)
