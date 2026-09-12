"""
Chroma vector store wrapper — one persistent client, one collection for resume chunks
(`resume_chunks`). Embeddings are computed via app/retrieval/embeddings.py (Gemini), not
Chroma's own default embedding function, so we control exactly which model produces the
vectors stored here.

Collection is configured for cosine distance explicitly (Chroma's default is squared
L2, which isn't what the Skill Gap Agent's thresholds — app/agents/skill_gap.py — assume).

Persisted under settings.CHROMA_PERSIST_DIR. Tests point this at a per-test temp
directory (see tests/conftest.py), the same isolation pattern used for the sandboxed
document uploads directory in app/mcp/sandbox.py.
"""
import chromadb

from app.core.config import settings
from app.retrieval.chunking import chunk_text
from app.retrieval.embeddings import get_document_embedder, get_query_embedder

_client = None


def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _client


def get_resume_chunks_collection():
    return get_chroma_client().get_or_create_collection(
        "resume_chunks", metadata={"hnsw:space": "cosine"}
    )


async def index_resume_chunks(user_id: str, document_id: str, text: str) -> int:
    """
    Chunks a resume's text and stores embeddings in the resume_chunks collection, scoped
    to the owning user via metadata. Returns the number of chunks stored. Deletes any
    existing chunks for this document_id first, so re-uploading/re-indexing the same
    document replaces rather than accumulates duplicate chunks.
    """
    collection = get_resume_chunks_collection()
    collection.delete(where={"document_id": document_id})

    chunks = chunk_text(text)
    if not chunks:
        return 0

    embedder = get_document_embedder()
    vectors = await embedder.aembed_documents(chunks)

    ids = [f"{document_id}:{i}" for i in range(len(chunks))]
    metadatas = [
        {"user_id": user_id, "document_id": document_id, "chunk_index": i} for i in range(len(chunks))
    ]

    collection.add(ids=ids, embeddings=vectors, documents=chunks, metadatas=metadatas)
    return len(chunks)


async def user_has_indexed_resume(user_id: str) -> bool:
    """Cheap existence check (no embedding call needed) — lets the Skill Gap Agent tell
    'no resume on file' apart from 'resume on file but no skill evidence found'."""
    collection = get_resume_chunks_collection()
    existing = collection.get(where={"user_id": user_id}, limit=1)
    return len(existing["ids"]) > 0


async def query_resume_chunks(user_id: str, query_text: str, n_results: int = 1) -> list[tuple[str, float]]:
    """
    Returns the top-N resume chunks (for this user only) most semantically similar to
    query_text, each paired with its cosine distance (0 = identical, 2 = opposite).
    """
    collection = get_resume_chunks_collection()
    embedder = get_query_embedder()
    query_vector = await embedder.aembed_query(query_text)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results,
        where={"user_id": user_id},
    )
    documents = results["documents"][0] if results["documents"] else []
    distances = results["distances"][0] if results["distances"] else []
    return list(zip(documents, distances))
