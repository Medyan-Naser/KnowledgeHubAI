"""Chat API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Schema for chat request."""

    query: str = Field(..., min_length=1, max_length=4096, description="User question")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")
    debug: bool = Field(default=False, description="Include debug information in response")


class SourceChunk(BaseModel):
    """Schema for source chunk in response."""

    document_id: uuid.UUID
    document_name: str
    chunk_index: int
    content: str
    similarity_score: float


class DebugInfo(BaseModel):
    """Debug information for the chat response."""
    
    system_prompt: str = Field(..., description="System prompt sent to LLM")
    user_prompt: str = Field(..., description="User prompt sent to LLM")
    context_chunks: list[str] = Field(..., description="Retrieved context chunks")
    full_prompt: str = Field(..., description="Complete prompt sent to LLM")


class ChatResponse(BaseModel):
    """Schema for chat response."""

    id: uuid.UUID
    query: str
    response: str
    sources: list[SourceChunk]
    llm_model: str
    embedding_model: str
    latency_ms: float
    retrieved_count: int
    created_at: datetime
    debug: DebugInfo | None = Field(default=None, description="Debug information (only if requested)")
