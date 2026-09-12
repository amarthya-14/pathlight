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

from app.core.config import settings


@lru_cache
def get_document_embedder() -> GoogleGenerativeAIEmbeddings:
    """task_type=RETRIEVAL_DOCUMENT — used when embedding resume chunks to be stored."""
    return GoogleGenerativeAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        task_type="RETRIEVAL_DOCUMENT",
    )


@lru_cache
def get_query_embedder() -> GoogleGenerativeAIEmbeddings:
    """task_type=RETRIEVAL_QUERY — used when embedding a skill name to search for matches."""
    return GoogleGenerativeAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        task_type="RETRIEVAL_QUERY",
    )
