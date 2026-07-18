"""Document management endpoints."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.document import DocumentResponse, DocumentListResponse
from backend.database import get_async_session
from backend.services.document_service import DocumentService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
) -> DocumentResponse:
    """
    Upload a document for processing.

    Supported formats: PDF, Markdown, TXT

    The document will be queued for processing via Temporal workflow.
    """
    service = DocumentService(session)

    try:
        document = await service.upload_document(file)

        logger.info(
            "document_upload_endpoint",
            document_id=str(document.id),
            filename=document.original_filename,
        )

        return DocumentResponse.model_validate(document)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("document_upload_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List all documents",
)
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
) -> DocumentListResponse:
    """
    List all uploaded documents with pagination.
    """
    service = DocumentService(session)
    documents, total = await service.list_documents(skip=skip, limit=limit)

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> DocumentResponse:
    """
    Get details of a specific document.
    """
    service = DocumentService(session)
    document = await service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    return DocumentResponse.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """
    Delete a document and its associated chunks and embeddings.
    """
    service = DocumentService(session)
    deleted = await service.delete_document(document_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    logger.info("document_deleted_endpoint", document_id=str(document_id))
