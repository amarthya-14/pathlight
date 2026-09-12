"""Chunking is pure/deterministic — no DB, no embeddings, no fixtures needed."""
from app.retrieval.chunking import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_is_a_single_chunk():
    chunks = chunk_text("Skilled in Python and Django.", chunk_size=500)
    assert chunks == ["Skilled in Python and Django."]


def test_long_text_splits_on_paragraph_boundaries():
    para_a = "A" * 300
    para_b = "B" * 300
    text = f"{para_a}\n{para_b}"
    chunks = chunk_text(text, chunk_size=400)
    assert len(chunks) == 2
    assert chunks[0] == para_a
    assert chunks[1] == para_b


def test_oversized_single_paragraph_kept_whole_not_force_split():
    huge_para = "X" * 1000
    chunks = chunk_text(huge_para, chunk_size=400)
    assert chunks == [huge_para]
