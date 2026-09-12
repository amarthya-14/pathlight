"""
Vector store tests, using the default FakeEmbedder (see tests/fakes.py, applied globally
by the `client` fixture) since this sandbox cannot reach Google's embedding API.

Distance values are asserted directly here (not just trusted from FakeEmbedder's
docstring math) — this is what actually proves Chroma's cosine distance behaves the way
app/agents/skill_gap.py's thresholds assume.
"""
import pytest

from app.retrieval.vector_store import (
    index_resume_chunks,
    query_resume_chunks,
    user_has_indexed_resume,
)


async def test_user_has_no_resume_before_indexing(client):
    assert await user_has_indexed_resume("user-1") is False


async def test_index_and_query_returns_matching_chunk(client):
    count = await index_resume_chunks("user-1", "doc-1", "Skilled in Python and backend development.")
    assert count == 1
    assert await user_has_indexed_resume("user-1") is True

    hits = await query_resume_chunks("user-1", "Python", n_results=1)
    assert len(hits) == 1
    chunk_text, distance = hits[0]
    assert "Python" in chunk_text
    assert distance == pytest.approx(0.0, abs=1e-6)


async def test_distance_thresholds_match_skill_gap_agent_assumptions(client):
    """Empirically verifies the exact distance values app/agents/skill_gap.py's
    MATCH_THRESHOLD/WEAK_THRESHOLD were chosen against — not just trusted by hand-math."""
    await index_resume_chunks("user-2", "doc-2", "Experienced with Python.")

    matched_hits = await query_resume_chunks("user-2", "Python", n_results=1)
    _, matched_distance = matched_hits[0]
    assert matched_distance == pytest.approx(0.0, abs=1e-6)

    weak_hits = await query_resume_chunks("user-2", "Django", n_results=1)
    _, weak_distance = weak_hits[0]
    assert 0.25 < weak_distance <= 0.45

    missing_hits = await query_resume_chunks("user-2", "AWS", n_results=1)
    _, missing_distance = missing_hits[0]
    assert missing_distance > 0.45


async def test_reindexing_same_document_replaces_not_accumulates(client):
    await index_resume_chunks("user-3", "doc-3", "Skilled in Python.")
    count_first = (await query_resume_chunks("user-3", "Python", n_results=10))
    assert len(count_first) == 1

    # Re-index the same document_id with different content
    await index_resume_chunks("user-3", "doc-3", "Skilled in AWS and Python.")
    all_chunks = await query_resume_chunks("user-3", "Python", n_results=10)
    # Still just the chunks from the latest index call, not old + new combined
    assert len(all_chunks) == 1


async def test_query_scoped_to_user_does_not_leak_across_users(client):
    await index_resume_chunks("user-a", "doc-a", "Skilled in Python.")
    hits_for_other_user = await query_resume_chunks("user-b", "Python", n_results=5)
    assert hits_for_other_user == []


async def test_empty_text_indexes_nothing(client):
    count = await index_resume_chunks("user-4", "doc-4", "")
    assert count == 0
    assert await user_has_indexed_resume("user-4") is False
