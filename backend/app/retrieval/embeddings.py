"""
Embedding client wrapper — Gemini's gemini-embedding-001 model (GA, text-only; verified
current as of Sep 2026 — see docs/AI_DESIGN.md). Kept in one file for the same reason
app/agents/llm_client.py isolates the chat model: swapping providers later is one file,
not a codebase-wide change.

Two separate cached instances, using different task_type values, because Gemini's
embedding API supports asymmetric embeddings: a document being indexed and a query
searching for it are embedded slightly differently for better retrieval quality.

Same network limitation as app/agents/llm_client.py, stated plainly: this sandbox cannot
reach Google's API, so this is UNVERIFIED against the real embedding endpoint. Tests use
a fake embedder (tests/fakes.py) with deterministic vectors instead — see
docs/ARCHITECTURE.md's Gate 5 section for what that does and doesn't prove.
"""
from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.agents.llm_client import gemini_keys
from app.core.config import settings


@lru_cache(maxsize=64)
def _embedder(key: str, task_type: str) -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(model=settings.EMBEDDING_MODEL, google_api_key=key, task_type=task_type)


class FallbackEmbedder:
    """Tries the student's own Gemini key(s), then each server key (app/agents/llm_client.py).
    Same embedding model on every key, so vectors stay comparable whichever key made them."""

    def __init__(self, task_type: str):
        self.task_type = task_type

    async def _run(self, method: str, arg):
        last_error: Exception | None = None
        for key in gemini_keys():
            try:
                return await getattr(_embedder(key, self.task_type), method)(arg)
            except Exception as e:  # quota, overload, invalid key -> next key
                last_error = e
        raise last_error

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._run("aembed_documents", texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await self._run("aembed_query", text)


def get_document_embedder() -> FallbackEmbedder:
    """task_type=RETRIEVAL_DOCUMENT — used when embedding resume chunks to be stored."""
    return FallbackEmbedder("RETRIEVAL_DOCUMENT")


def get_query_embedder() -> FallbackEmbedder:
    """task_type=RETRIEVAL_QUERY — used when embedding a skill name to search for matches."""
    return FallbackEmbedder("RETRIEVAL_QUERY")
