"""Document service for file handling and database operations."""

import os
import uuid
from pathlib import Path

import structlog
from fastapi import UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client as TemporalClient

from backend.config import get_settings
from backend.models.document import Document, DocumentStatus, DocumentType

settings = get_settings()
logger = structlog.get_logger(__name__)

_temporal_client = None

async def get_temporal_client() -> TemporalClient:
    """Get or create Temporal client."""
    global _temporal_client
    if _temporal_client is None:
        _temporal_client = await TemporalClient.connect(settings.temporal_host)
    return _temporal_client


class DocumentService:
    """Service for document management operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _get_document_type(self, filename: str) -> DocumentType:
        """Determine document type from filename extension."""
        ext = Path(filename).suffix.lower()
        type_mapping = {
            ".pdf": DocumentType.PDF,
            ".md": DocumentType.MARKDOWN,
            ".txt": DocumentType.TEXT,
        }
        return type_mapping.get(ext, DocumentType.TEXT)

    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type from filename extension."""
        ext = Path(filename).suffix.lower()
        mime_mapping = {
            ".pdf": "application/pdf",
            ".md": "text/markdown",
            ".txt": "text/plain",
        }
        return mime_mapping.get(ext, "application/octet-stream")

    async def upload_document(self, file: UploadFile) -> Document:
        """
        Upload and store a document.

        Args:
            file: Uploaded file from FastAPI

        Returns:
            Created Document instance
        """
        if not file.filename:
            raise ValueError("Filename is required")

        ext = Path(file.filename).suffix.lower()
        if ext not in settings.allowed_extensions:
            raise ValueError(f"File type {ext} not allowed. Allowed: {settings.allowed_extensions}")

        content = await file.read()
        file_size = len(content)

        if file_size > settings.max_file_size_mb * 1024 * 1024:
            raise ValueError(f"File size exceeds {settings.max_file_size_mb}MB limit")

        file_id = uuid.uuid4()
        stored_filename = f"{file_id}{ext}"
        file_path = self.upload_dir / stored_filename

        with open(file_path, "wb") as f:
            f.write(content)

        document = Document(
            id=file_id,
            filename=stored_filename,
            original_filename=file.filename,
            file_path=str(file_path),
            file_size=file_size,
            file_type=self._get_document_type(file.filename),
            mime_type=self._get_mime_type(file.filename),
            status=DocumentStatus.PENDING,
        )

        self.session.add(document)
        await self.session.commit()

        # Start Temporal workflow for document processing
        try:
            client = await get_temporal_client()
            from backend.temporal.workflows import DocumentProcessingWorkflow
            
            await client.start_workflow(
                DocumentProcessingWorkflow.run,
                str(file_id),
                id=f"doc-processing-{file_id}",
                task_queue="document-processing",
            )
            logger.info(
                "document_workflow_started",
                document_id=str(file_id),
            )
        except Exception as e:
            logger.error(
                "document_workflow_start_failed",
                document_id=str(file_id),
                error=str(e),
            )

        logger.info(
            "document_uploaded",
            document_id=str(file_id),
            filename=file.filename,
            size=file_size,
        )

        return document

    async def get_document(self, document_id: uuid.UUID) -> Document | None:
        """Get a document by ID."""
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self, skip: int = 0, limit: int = 100
    ) -> tuple[list[Document], int]:
        """List all documents with pagination."""
        count_result = await self.session.execute(select(func.count(Document.id)))
        total = count_result.scalar() or 0

        result = await self.session.execute(
            select(Document)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        documents = list(result.scalars().all())

        return documents, total

    async def delete_document(self, document_id: uuid.UUID) -> bool:
        """Delete a document and its file."""
        document = await self.get_document(document_id)
        if not document:
            return False

        if os.path.exists(document.file_path):
            os.remove(document.file_path)

        await self.session.delete(document)

        logger.info("document_deleted", document_id=str(document_id))
        return True

    async def update_status(
        self,
        document_id: uuid.UUID,
        status: DocumentStatus,
        error_message: str | None = None,
        chunk_count: int | None = None,
    ) -> Document | None:
        """Update document processing status."""
        document = await self.get_document(document_id)
        if not document:
            return None

        document.status = status
        if error_message:
            document.error_message = error_message
        if chunk_count is not None:
            document.chunk_count = chunk_count

        await self.session.flush()
        return document
