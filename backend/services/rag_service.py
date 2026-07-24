"""RAG service for retrieval-augmented generation."""

import time
import uuid
from datetime import datetime, timezone

import structlog
import mlflow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.document import Chunk, Document, Embedding
from backend.models.chat import ChatHistory
from backend.services.embedding_service import EmbeddingService
from backend.services.llm_service import LLMService
from backend.api.schemas.chat import ChatResponse, SourceChunk

settings = get_settings()
logger = structlog.get_logger(__name__)


class RAGService:
    """Service for RAG-based question answering."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()

    async def search_similar_chunks(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[tuple[Chunk, Document, float]]:
        """
        Search for similar chunks using vector similarity.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return

        Returns:
            List of tuples (chunk, document, similarity_score)
        """
        from sqlalchemy import func, text
        
        # Calculate cosine distance in the query
        distance = Embedding.vector.cosine_distance(query_embedding)
        
        # Use ORDER BY and LIMIT in SQL for efficiency
        query = (
            select(Embedding, Chunk, Document, distance.label('distance'))
            .join(Chunk, Embedding.chunk_id == Chunk.id)
            .join(Document, Chunk.document_id == Document.id)
            .order_by(text('distance'))  # Order by distance (ascending = most similar first)
            .limit(top_k * 2)  # Fetch a bit more for safety
        )
        
        logger.info("vector_search_executing", top_k=top_k)
        
        # Force sequential scan: IVFFlat index built on empty table returns 0 rows.
        # SET LOCAL reverts automatically at transaction end.
        await self.session.execute(text("SET LOCAL enable_indexscan = off"))
        result = await self.session.execute(query)
        await self.session.execute(text("SET LOCAL enable_indexscan = on"))
        rows = result.all()
        
        logger.info("vector_search_raw_results", num_rows=len(rows))

        results = []
        for row in rows:
            try:
                embedding, chunk, document, dist = row
                # Convert distance to similarity (1 - distance for cosine)
                similarity = max(0.0, 1.0 - float(dist)) if dist is not None else 0.0
                results.append((chunk, document, similarity))
                logger.debug(
                    "vector_search_chunk",
                    chunk_index=chunk.chunk_index,
                    similarity=round(similarity, 4),
                    content_preview=chunk.content[:100]
                )
            except Exception as e:
                logger.error("vector_search_row_error", error=str(e), row=str(row)[:200])
        
        # Sort by similarity (descending) and limit to exact top_k
        results.sort(key=lambda x: x[2], reverse=True)
        results = results[:top_k]
        
        logger.info(
            "vector_search_results",
            num_results=len(results),
            top_k=top_k,
            top_similarity=round(results[0][2], 4) if results else 0.0
        )

        return results

    async def query(self, query: str, top_k: int = 5, debug: bool = False) -> ChatResponse:
        """
        Process a RAG query.

        Args:
            query: User's question
            top_k: Number of chunks to retrieve
            debug: Include debug information in response

        Returns:
            ChatResponse with answer and sources
        """
        start_time = time.time()

        import asyncio
        loop = asyncio.get_event_loop()

        # Run sync Ollama calls in thread pool so event loop stays free for health probes
        query_embedding = await loop.run_in_executor(
            None, self.embedding_service.generate_embedding, query
        )

        similar_chunks = await self.search_similar_chunks(query_embedding, top_k)

        if not similar_chunks:
            response_text = "I couldn't find any relevant information in the knowledge base to answer your question."
            sources = []
            context_chunks = []
            system_prompt = ""
            full_prompt = ""
        else:
            context_chunks = [chunk.content for chunk, _, _ in similar_chunks]
            response_text, token_count, system_prompt, full_prompt = await loop.run_in_executor(
                None, lambda: self.llm_service.generate_response(
                    query, context_chunks, return_prompts=debug
                )
            )

            sources = [
                SourceChunk(
                    document_id=document.id,
                    document_name=document.original_filename,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content[:500],
                    similarity_score=round(score, 4),
                )
                for chunk, document, score in similar_chunks
            ]

        latency_ms = (time.time() - start_time) * 1000

        chat_record = ChatHistory(
            query=query,
            response=response_text,
            context_chunks="\n---\n".join(context_chunks) if context_chunks else None,
            retrieved_document_ids=",".join(
                str(doc.id) for _, doc, _ in similar_chunks
            ) if similar_chunks else None,
            retrieved_count=len(similar_chunks),
            llm_model=settings.llm_model,
            embedding_model=settings.embedding_model,
            latency_ms=latency_ms,
            token_count=token_count if 'token_count' in dir() and token_count else None,
        )
        self.session.add(chat_record)
        await self.session.flush()

        logger.info(
            "rag_query_completed",
            query_length=len(query),
            retrieved_chunks=len(similar_chunks),
            latency_ms=round(latency_ms, 2),
        )

        # Log to MLflow
        try:
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            mlflow.set_experiment("rag-queries")
            
            with mlflow.start_run(run_name=f"query-{str(chat_record.id)[:8]}"):
                mlflow.log_param("query_length", len(query))
                mlflow.log_param("top_k", top_k)
                mlflow.log_param("llm_model", settings.llm_model)
                mlflow.log_param("embedding_model", settings.embedding_model)
                mlflow.log_metric("retrieved_chunks", len(similar_chunks))
                mlflow.log_metric("latency_ms", latency_ms)
                if similar_chunks:
                    mlflow.log_metric("top_similarity", similar_chunks[0][2])
                
                logger.debug("mlflow_rag_logged", chat_id=str(chat_record.id))
        except Exception as e:
            logger.warning("mlflow_rag_failed", error=str(e))

        # Build debug info if requested
        debug_info = None
        if debug:
            from backend.api.schemas.chat import DebugInfo
            debug_info = DebugInfo(
                system_prompt=system_prompt,
                user_prompt=query,
                context_chunks=context_chunks,
                full_prompt=full_prompt
            )

        return ChatResponse(
            id=chat_record.id,
            query=query,
            response=response_text,
            sources=sources,
            llm_model=settings.llm_model,
            embedding_model=settings.embedding_model,
            latency_ms=round(latency_ms, 2),
            retrieved_count=len(similar_chunks),
            created_at=datetime.now(timezone.utc),
            debug=debug_info,
        )
