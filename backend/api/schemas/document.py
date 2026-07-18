"""Document API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.models.document import DocumentStatus, DocumentType


class DocumentCreate(BaseModel):
    """Schema for document creation response after upload."""

    filename: str


class DocumentResponse(BaseModel):
    """Schema for document response."""

    id: uuid.UUID
    filename: str
    original_filename: str
    file_size: int
    file_type: DocumentType
    status: DocumentStatus
    chunk_count: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Schema for list of documents response."""

    documents: list[DocumentResponse]
    total: int = Field(description="Total number of documents")
