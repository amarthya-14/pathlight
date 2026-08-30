"""
Document model — represents an uploaded or pasted piece of source material (resume, job
description, or forwarded/pasted email). Agents (Gate 4+) read document content via the
Filesystem MCP tool (app/mcp/filesystem_server.py) using `storage_filename`, rather than
the API layer handing them raw file paths directly.
"""
from datetime import datetime, timezone
from enum import Enum

from beanie import Document as BeanieDocument
from beanie import Indexed, PydanticObjectId
from pydantic import Field


class DocumentType(str, Enum):
    RESUME = "resume"
    JOB_DESCRIPTION = "job_description"
    EMAIL_PASTE = "email_paste"
    OTHER = "other"


class Document(BeanieDocument):
    owner_id: Indexed(PydanticObjectId)
    doc_type: DocumentType
    original_filename: str
    storage_filename: str  # sanitized, unique name actually used on disk (see app/mcp/sandbox.py)
    content_type: str
    extracted_text: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "documents"
