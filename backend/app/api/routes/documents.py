"""
Document ingestion — file upload (PDF or plain text) and text-paste (for forwarded
emails / pasted job descriptions), both landing in the same sandboxed uploads directory
that the Filesystem MCP server reads from (app/mcp/filesystem_server.py), so agents
access documents the same way regardless of how they arrived.

Resumes are additionally indexed into Chroma (app/retrieval/vector_store.py) at
upload/paste time, so the Skill Gap Agent (Gate 5) has something to search against as
soon as a resume exists — not indexed lazily on first Skill Gap run, which would make
the first ingestion after a resume upload silently slower and harder to reason about.
"""
import io

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pypdf import PdfReader

from app.api.deps import get_current_user
from app.mcp.sandbox import sanitize_filename, user_dir
from app.models.document import Document, DocumentType
from app.models.user import User
from app.retrieval.vector_store import index_resume_chunks
from app.schemas.document import DocumentDetailOut, DocumentOut, DocumentPasteCreate

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB — generous for a resume/JD PDF, cheap abuse guard
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}


def _extract_text(content_type: str, raw: bytes) -> str | None:
    """Best-effort text extraction. Returning None on failure (rather than raising) means
    a corrupt/scanned-image PDF doesn't block the upload — it just has no extracted_text,
    which downstream agents (Gate 4+) should treat as 'nothing to work with yet' rather
    than crashing the pipeline."""
    if content_type == "text/plain":
        return raw.decode("utf-8", errors="replace")
    if content_type == "application/pdf":
        try:
            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text.strip() or None
        except Exception:
            return None
    return None


async def _index_if_resume(document: Document) -> None:
    """Indexes a resume's extracted text into Chroma. Silently does nothing for
    non-resume documents or resumes with no extractable text (e.g. a scanned-image PDF
    that produced no text) — there's nothing to index, which the Skill Gap Agent already
    treats as 'no resume evidence' rather than an error (see app/agents/skill_gap.py)."""
    if document.doc_type != DocumentType.RESUME or not document.extracted_text:
        return
    await index_resume_chunks(str(document.owner_id), str(document.id), document.extracted_text)


@router.post("/upload", response_model=DocumentDetailOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    doc_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {file.content_type}. Allowed: {sorted(ALLOWED_CONTENT_TYPES)}",
        )

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large (max 10MB)",
        )

    # sanitize_filename strips directory components and adds a UUID prefix — see
    # app/mcp/sandbox.py. This is the ONE place a path is derived from user-controlled
    # input on the write side; the Filesystem MCP server independently re-validates on
    # every read (see resolve_safe_path), so a bug here wouldn't be a single point of failure.
    storage_filename = sanitize_filename(file.filename or "upload")
    dest = user_dir(str(current_user.id)) / storage_filename
    dest.write_bytes(raw)

    document = Document(
        owner_id=current_user.id,
        doc_type=doc_type,
        original_filename=file.filename or storage_filename,
        storage_filename=storage_filename,
        content_type=file.content_type,
        extracted_text=_extract_text(file.content_type, raw),
    )
    await document.insert()
    await _index_if_resume(document)
    return document


@router.post("/paste", response_model=DocumentDetailOut, status_code=status.HTTP_201_CREATED)
async def paste_document(
    payload: DocumentPasteCreate,
    current_user: User = Depends(get_current_user),
):
    storage_filename = sanitize_filename(f"{payload.title}.txt")
    dest = user_dir(str(current_user.id)) / storage_filename
    dest.write_text(payload.text, encoding="utf-8")

    document = Document(
        owner_id=current_user.id,
        doc_type=payload.doc_type,
        original_filename=f"{payload.title}.txt",
        storage_filename=storage_filename,
        content_type="text/plain",
        extracted_text=payload.text,
    )
    await document.insert()
    await _index_if_resume(document)
    return document


@router.get("", response_model=list[DocumentOut])
async def list_documents(current_user: User = Depends(get_current_user)):
    return await Document.find(Document.owner_id == current_user.id).sort(-Document.created_at).to_list()


@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(document_id: str, current_user: User = Depends(get_current_user)):
    try:
        oid = PydanticObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    document = await Document.get(oid)
    # Ownership check: a document existing isn't enough — it must belong to the
    # requesting user, or this leaks other users' resumes/JDs by guessing IDs.
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document
