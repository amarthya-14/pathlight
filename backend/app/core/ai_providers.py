"""
AI providers a student can bring their own key for.

Pathlight runs on a shared Gemini key out of the box. A student can add keys for any of
these; every AI call then tries their keys first (in the order they added them), then the
shared keys (app/agents/llm_client.py).

When a key is added it is checked with the provider (listing models costs nothing), and
the best available strong and fast models are picked from what that key can actually
use — providers rename models often, so nothing here hard-depends on one model id.
Keys are stored only as Fernet ciphertext (app/core/crypto.py) and never returned.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from beanie import PydanticObjectId

from app.core.config import settings
from app.core.crypto import decrypt_token, encryption_available, encrypt_token
from app.models.user import AiKey, User


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    key_prefixes: tuple[str, ...]  # what valid keys start with (empty = no check)
    base_url: str | None  # OpenAI-compatible endpoint, or None for native clients
    strong_prefs: tuple[str, ...]  # preferred model ids / substrings, best first
    small_prefs: tuple[str, ...]


PROVIDERS: dict[str, Provider] = {
    # AI Studio issues both the classic "AIza…" keys and newer "AQ.…" keys.
    "gemini": Provider("gemini", "Google Gemini", ("AIza", "AQ."), None, (), ()),
    "groq": Provider(
        "groq", "Groq", ("gsk_",), "https://api.groq.com/openai/v1",
        ("llama-3.3-70b-versatile", "openai/gpt-oss-120b", "70b"), ("llama-3.1-8b-instant", "8b", "gpt-oss-20b"),
    ),
    "openai": Provider(
        "openai", "OpenAI", ("sk-",), "https://api.openai.com/v1",
        ("gpt-5-mini", "gpt-4.1-mini", "gpt-4o-mini", "gpt-5", "gpt-4.1"), ("gpt-5-nano", "gpt-4.1-nano", "gpt-4o-mini"),
    ),
    "anthropic": Provider("anthropic", "Anthropic Claude", ("sk-ant-",), None, ("sonnet",), ("haiku",)),
    "custom": Provider("custom", "OpenAI-compatible", (), None, (), ()),
}


class KeyProblem(Exception):
    """A key that can't be used, with a message the student can act on."""


def _pick(ids: list[str], prefs: tuple[str, ...]) -> str | None:
    for pref in prefs:
        for model_id in ids:  # providers list newest first
            if model_id == pref or pref in model_id:
                return model_id
    return None


async def _list_models(provider: Provider, key: str, base_url: str | None) -> list[str]:
    async with httpx.AsyncClient(timeout=12.0) as http:
        if provider.id == "gemini":
            r = await http.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 1})
        elif provider.id == "anthropic":
            r = await http.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                params={"limit": 100},
            )
        else:
            r = await http.get(f"{(base_url or provider.base_url).rstrip('/')}/models", headers={"Authorization": f"Bearer {key}"})
    if r.status_code == 429:
        return []  # valid, just out of quota right now
    if r.status_code in (401, 403):
        raise KeyProblem(f"{provider.label} rejected this key. Copy it again — and check the account has API access.")
    if r.status_code == 404 and provider.id == "custom":
        return []  # some compatible servers don't list models; the model name is given
    if r.status_code != 200:
        raise KeyProblem(f"{provider.label} says this key isn't valid ({r.status_code}).")
    data = r.json()
    return [m.get("id") or m.get("name", "").removeprefix("models/") for m in data.get("data") or data.get("models") or []]


async def verify_key(provider_id: str, key: str, base_url: str | None = None, model: str | None = None) -> AiKey:
    """Checks the key with the provider and returns a ready-to-store record (with the key
    encrypted and the models picked). Raises KeyProblem with a student-facing message."""
    provider = PROVIDERS.get(provider_id)
    if provider is None:
        raise KeyProblem("Unknown provider.")
    key = key.strip()
    if provider.key_prefixes and not key.startswith(provider.key_prefixes):
        starts = " or ".join(f"“{p}”" for p in provider.key_prefixes)
        raise KeyProblem(f"That doesn't look like a {provider.label} key — those start with {starts}.")
    if provider.id == "custom" and not (base_url and model):
        raise KeyProblem("For an OpenAI-compatible provider, add its base URL and the model to use.")
    try:
        ids = await _list_models(provider, key, base_url)
    except httpx.HTTPError:
        raise KeyProblem(f"Couldn't reach {provider.label} to check the key. Try again in a minute.")

    if provider.id == "gemini":
        strong, small = settings.LLM_MODEL_STRONG, settings.LLM_MODEL_SMALL
    elif provider.id == "custom":
        strong = small = model.strip()
    else:
        strong = (model.strip() if model else None) or _pick(ids, provider.strong_prefs) or (ids[0] if ids else None)
        small = _pick(ids, provider.small_prefs) or strong
        if not strong:
            raise KeyProblem(f"This {provider.label} key works but can't use any chat model Pathlight knows. Add a model name.")
    return AiKey(
        provider=provider.id,
        encrypted_key=encrypt_token(key),
        last4=key[-4:],
        strong_model=strong,
        small_model=small,
        base_url=(base_url.strip().rstrip("/") if base_url else None),
        added_at=datetime.now(timezone.utc),
    )


def decrypt_keys(user: User | None) -> list[dict]:
    """The student's usable keys, decrypted, in their order. Keys that can't be decrypted
    (e.g. after TOKEN_ENCRYPTION_KEY rotation) are skipped — the shared keys still work."""
    if user is None or not user.ai_keys or not encryption_available():
        return []
    out = []
    for k in user.ai_keys:
        try:
            out.append({
                "provider": k.provider, "key": decrypt_token(k.encrypted_key), "strong": k.strong_model,
                "small": k.small_model, "base_url": k.base_url,
            })
        except Exception:
            continue
    return out


async def load_user_keys(user_id) -> list[dict]:
    if not user_id:
        return []
    try:
        user = await User.get(PydanticObjectId(str(user_id)))
    except Exception:
        return []
    return decrypt_keys(user)
