"""Chat endpoint for RAG queries."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.chat import ChatRequest, ChatResponse
from backend.database import get_async_session
from backend.services.rag_service import RAGService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask a question",
)
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ChatResponse:
    """
    Ask a question and get an answer based on the knowledge base.

    The system will:
    1. Generate an embedding for your query
    2. Search for similar document chunks using pgvector
    3. Use the retrieved context to generate an answer via Ollama
    """
    try:
        service = RAGService(session)
        response = await service.query(
            query=request.query, 
            top_k=request.top_k,
            debug=request.debug
        )

        logger.info(
            "chat_query_processed",
            query_length=len(request.query),
            sources_count=len(response.sources),
            latency_ms=response.latency_ms,
            debug_requested=request.debug,
        )

        return response

    except Exception as e:
        logger.error("chat_query_failed", error=str(e), query=request.query[:100])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}",
        )
