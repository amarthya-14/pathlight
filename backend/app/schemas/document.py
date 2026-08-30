from datetime import datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentType


class DocumentPasteCreate(BaseModel):
    doc_type: DocumentType
    title: str
    text: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: PydanticObjectId
    doc_type: DocumentType
    original_filename: str
    content_type: str
    created_at: datetime


class DocumentDetailOut(DocumentOut):
    storage_filename: str  # what agents pass to the Filesystem MCP tool to read this doc
    extracted_text: str | None = None
