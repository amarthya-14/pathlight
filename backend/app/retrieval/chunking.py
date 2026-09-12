"""
Simple text chunking for RAG. Deliberately basic (paragraph-aware, fixed target size) —
adequate for resume/JD-length documents (a few hundred to a few thousand words), not
designed for large document corpora. Revisit if longer documents are added later.
"""


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """
    Splits text into chunks of roughly chunk_size characters, breaking on paragraph
    (newline) boundaries where possible so a chunk doesn't cut a sentence in half more
    than necessary. A paragraph longer than chunk_size on its own is kept whole rather
    than force-split mid-sentence — simplicity over precision for this MVP.
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n{para}".strip() if current else para
        if len(candidate) <= chunk_size or not current:
            current = candidate
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)

    return chunks
