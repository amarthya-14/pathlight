"""Bring-your-own AI keys (any provider): verification, storage, ordering, fallbacks, limits."""
import httpx
from cryptography.fernet import Fernet
from langchain_core.runnables import RunnableLambda

from app.agents import llm_client
from app.agents.llm_client import FallbackLLM, gemini_keys, set_user_keys
from app.agents.schemas import ExtractedOpportunity
from app.core import ai_providers
from app.core.usage import DAILY_LIMITS, OWN_KEY_MULTIPLIER, try_consume
from app.models.user import User

GEMINI_KEY = "AIza" + "x" * 35
GROQ_KEY = "gsk_" + "y" * 40


def _login(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "testpass123", "full_name": "Key User"})
    token = client.post("/api/auth/login", data={"username": email, "password": "testpass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _provider_api(monkeypatch, status=200, models=None):
    """Fakes every provider's 'list models' endpoint."""
    seen = []

    async def fake_get(self, url, **kwargs):
        seen.append(url)
        data = {"data": [{"id": m} for m in (models or [])]}
        return httpx.Response(status, json=data, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr("app.core.config.settings.TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    return seen


async def test_adding_keys_checks_the_provider_and_stores_only_ciphertext(client, monkeypatch):
    _provider_api(monkeypatch, models=["llama-3.1-8b-instant", "llama-3.3-70b-versatile"])
    headers = _login(client, "byok@example.com")

    resp = client.post("/api/account/ai-keys", json={"provider": "groq", "api_key": GROQ_KEY}, headers=headers)
    assert resp.status_code == 200, resp.text
    key = resp.json()["ai_keys"][0]
    assert key == {**key, "provider": "groq", "last4": "yyyy", "strong_model": "llama-3.3-70b-versatile", "small_model": "llama-3.1-8b-instant"}

    client.post("/api/account/ai-keys", json={"provider": "gemini", "api_key": GEMINI_KEY}, headers=headers)
    user = await User.find_one(User.email == "byok@example.com")
    assert [k.provider for k in user.ai_keys] == ["groq", "gemini"]
    assert all(GROQ_KEY not in k.encrypted_key and GEMINI_KEY not in k.encrypted_key for k in user.ai_keys)

    me = client.get("/api/auth/me", headers=headers).json()
    assert [k["provider"] for k in me["ai_keys"]] == ["groq", "gemini"] and "encrypted_key" not in me["ai_keys"][0]
    exported = client.get("/api/account/export", headers=headers).text
    assert GROQ_KEY not in exported and "encrypted_key" not in exported

    order = client.put("/api/account/ai-keys/order", json=["gemini", "groq"], headers=headers).json()
    assert [k["provider"] for k in order["ai_keys"]] == ["gemini", "groq"]
    left = client.delete("/api/account/ai-keys/groq", headers=headers).json()
    assert [k["provider"] for k in left["ai_keys"]] == ["gemini"]


def test_wrong_looking_or_rejected_keys_get_a_clear_reason(client, monkeypatch):
    _provider_api(monkeypatch, status=401)
    headers = _login(client, "badkey@example.com")
    shape = client.post("/api/account/ai-keys", json={"provider": "openai", "api_key": "not-a-key-123"}, headers=headers)
    assert shape.status_code == 400 and "start with “sk-”" in shape.json()["detail"]
    rejected = client.post("/api/account/ai-keys", json={"provider": "openai", "api_key": "sk-" + "z" * 40}, headers=headers)
    assert rejected.status_code == 400 and "rejected this key" in rejected.json()["detail"]
    custom = client.post("/api/account/ai-keys", json={"provider": "custom", "api_key": "abc12345678"}, headers=headers)
    assert "base URL" in custom.json()["detail"]


def test_model_picking_prefers_named_models_then_substrings():
    assert ai_providers._pick(["claude-haiku-4-5", "claude-sonnet-5-5"], ("sonnet",)) == "claude-sonnet-5-5"
    assert ai_providers._pick(["gpt-4o-mini", "gpt-4.1-mini"], ("gpt-5-mini", "gpt-4.1-mini")) == "gpt-4.1-mini"
    assert ai_providers._pick(["x"], ("sonnet",)) is None


def test_every_ai_call_in_a_request_uses_the_students_keys(client, monkeypatch):
    _provider_api(monkeypatch, models=["llama-3.3-70b-versatile"])
    headers = _login(client, "inrequest@example.com")
    client.post("/api/account/ai-keys", json={"provider": "groq", "api_key": GROQ_KEY}, headers=headers)
    seen = []

    def recording_llm():
        seen.append([link.label for link in llm_client.get_small_llm().links])

        class Fake:
            def with_structured_output(self, schema):
                return RunnableLambda(lambda _: ExtractedOpportunity(company_name="Acme", role="SDE Intern"))

        return Fake()

    monkeypatch.setattr("app.agents.discovery.get_small_llm", recording_llm)
    client.post("/api/opportunities/ingest", json={"raw_text": "SDE Intern at Acme"}, headers=headers)
    assert seen and seen[0][0].startswith("groq:")
    assert any(label.startswith("gemini:") for label in seen[0])  # shared key still behind it


class _Step:
    def __init__(self, label, fail, calls):
        self.label, self.fail, self.calls = label, fail, calls

    def with_structured_output(self, schema):
        def run(_):
            self.calls.append(self.label)
            if self.fail:
                raise RuntimeError("429 RESOURCE_EXHAUSTED")
            return self.label

        return RunnableLambda(run)


async def test_a_failing_provider_falls_through_to_the_next():
    calls = []
    chain = FallbackLLM([_Step("own-groq", True, calls), _Step("shared-gemini", True, calls), _Step("own-groq-small", False, calls)])
    assert await chain.with_structured_output(ExtractedOpportunity).ainvoke("x") == "own-groq-small"
    assert calls == ["own-groq", "shared-gemini", "own-groq-small"]


def test_strong_chain_is_own_keys_then_shared_then_fast_models(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr("app.core.config.settings.GOOGLE_API_KEY", "server")
    monkeypatch.setattr("app.core.config.settings.GOOGLE_API_KEYS", "")
    monkeypatch.setattr("app.core.config.settings.LLM_EXTRA_FALLBACK_MODELS", "")
    set_user_keys([
        {"provider": "anthropic", "key": "sk-ant-1", "strong": "claude-sonnet", "small": "claude-haiku", "base_url": None},
        {"provider": "gemini", "key": "AIza-mine", "strong": settings.LLM_MODEL_STRONG, "small": settings.LLM_MODEL_SMALL, "base_url": None},
    ])
    labels = [link.label for link in llm_client.get_strong_llm().links]
    embed_keys = gemini_keys()
    set_user_keys([])
    assert labels == [
        "anthropic:claude-sonnet", f"gemini:{settings.LLM_MODEL_STRONG}", f"gemini:{settings.LLM_MODEL_STRONG}",
        "anthropic:claude-haiku", f"gemini:{settings.LLM_MODEL_SMALL}", f"gemini:{settings.LLM_MODEL_SMALL}",
    ]
    assert embed_keys == ["AIza-mine", "server"]


async def test_own_key_raises_the_daily_limit(client):
    set_user_keys([{"provider": "groq", "key": "k", "strong": "m", "small": "m", "base_url": None}])
    results = [await try_consume("64b7f00000000000000000aa", "tailor") for _ in range(DAILY_LIMITS["tailor"] * OWN_KEY_MULTIPLIER + 1)]
    set_user_keys([])
    assert results.count(True) == DAILY_LIMITS["tailor"] * OWN_KEY_MULTIPLIER
