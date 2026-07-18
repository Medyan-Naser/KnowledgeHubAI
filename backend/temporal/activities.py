"""Temporal activities for document processing."""

import uuid
from dataclasses import dataclass
from functools import lru_cache

import structlog
from temporalio import activity
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = structlog.get_logger(__name__)

# Lazy initialization to avoid issues with Temporal workflow sandbox
_engine = None
_session_local = None


@lru_cache()
def _get_settings():
    """Lazy load settings."""
    from backend.config import get_settings
    return get_settings()


def _get_session_local():
    """Lazy load session factory."""
    global _engine, _session_local
    if _session_local is None:
        settings = _get_settings()
        _engine = create_engine(settings.sync_database_url)
        _session_local = sessionmaker(bind=_engine)
    return _session_local


@dataclass
class DocumentProcessingInput:
    """Input for document processing workflow."""

    document_id: str


@dataclass
class ChunkData:
    """Data for a single chunk."""

    content: str
    chunk_index: int
    start_char: int
    end_char: int


@dataclass
class ProcessingResult:
    """Result of document processing."""

    document_id: str
    chunk_count: int
    status: str
    error_message: str | None = None


class DocumentActivities:
    """Activities for document processing."""

    def __init__(self):
        # Lazy imports to avoid Temporal sandbox restrictions
        from backend.services.text_processor import TextProcessor
        from backend.services.embedding_service import EmbeddingService
        self.text_processor = TextProcessor()
        self.embedding_service = EmbeddingService()

    @activity.defn
    async def extract_text(self, document_id: str) -> str:
        """Extract text from a document."""
        from backend.models.document import Document, DocumentStatus
        SessionLocal = _get_session_local()
        with SessionLocal() as session:
            document = session.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
            if not document:
                raise ValueError(f"Document {document_id} not found")

            document.status = DocumentStatus.PROCESSING
            session.commit()

            text = self.text_processor.extract_text_from_file(document.file_path)

            logger.info(
                "activity_extract_text",
                document_id=document_id,
                text_length=len(text),
            )

            return text

    @activity.defn
    async def chunk_text(self, document_id: str, text: str) -> list[dict]:
        """Chunk extracted text."""
        chunks = self.text_processor.chunk_text(text)

        logger.info(
            "activity_chunk_text",
            document_id=document_id,
            num_chunks=len(chunks),
        )

        return chunks

    @activity.defn
    async def generate_embeddings(
        self, document_id: str, chunks: list[dict]
    ) -> int:
        """Generate embeddings for chunks and store in database.
        
        Uses batch processing with delays to prevent GPU/memory overload.
        """
        import gc
        import time
        from backend.models.document import Chunk, Document, Embedding
        
        settings = _get_settings()
        batch_size = settings.embedding_batch_size
        batch_delay = settings.embedding_batch_delay_seconds
        total_chunks = len(chunks)
        
        logger.info(
            "activity_generate_embeddings_start",
            document_id=document_id,
            total_chunks=total_chunks,
            batch_size=batch_size,
            batch_delay_seconds=batch_delay,
        )
        
        SessionLocal = _get_session_local()
        with SessionLocal() as session:
            document = session.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
            if not document:
                raise ValueError(f"Document {document_id} not found")

            for i, chunk_data in enumerate(chunks):
                content = chunk_data["content"]
                
                # Skip empty chunks
                if not content or not content.strip():
                    logger.warning(
                        "activity_skipping_empty_chunk",
                        document_id=document_id,
                        chunk_index=chunk_data["chunk_index"],
                    )
                    continue
                
                # Clean content of NUL characters
                content = content.replace("\x00", "")
                
                chunk = Chunk(
                    document_id=document.id,
                    content=content,
                    chunk_index=chunk_data["chunk_index"],
                    start_char=chunk_data["start_char"],
                    end_char=chunk_data["end_char"],
                )
                session.add(chunk)
                session.flush()

                embedding_vector = self.embedding_service.generate_embedding(content)
                
                # Skip if embedding generation failed
                if not embedding_vector or len(embedding_vector) == 0:
                    logger.warning(
                        "activity_empty_embedding",
                        document_id=document_id,
                        chunk_index=chunk_data["chunk_index"],
                    )
                    continue

                embedding = Embedding(
                    chunk_id=chunk.id,
                    vector=embedding_vector,
                    model_name=settings.embedding_model,
                )
                session.add(embedding)
                
                # Progress logging
                progress_pct = ((i + 1) / total_chunks) * 100
                if (i + 1) % 10 == 0 or (i + 1) == total_chunks:
                    logger.info(
                        "activity_embedding_progress",
                        document_id=document_id,
                        processed=i + 1,
                        total=total_chunks,
                        progress_percent=round(progress_pct, 1),
                    )
                
                # Resource management: pause after each batch to prevent GPU overload
                if (i + 1) % batch_size == 0 and (i + 1) < total_chunks:
                    logger.debug(
                        "activity_embedding_batch_pause",
                        document_id=document_id,
                        processed=i + 1,
                        remaining=total_chunks - i - 1,
                        delay_seconds=batch_delay,
                    )
                    # Commit current batch to database
                    session.commit()
                    # Force garbage collection
                    gc.collect()
                    # Delay to let GPU/CPU cool down
                    time.sleep(batch_delay)

            session.commit()

            logger.info(
                "activity_generate_embeddings_complete",
                document_id=document_id,
                embeddings_count=total_chunks,
            )

            return total_chunks

    @activity.defn
    async def update_document_status(
        self,
        document_id: str,
        status: str,
        chunk_count: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Update document status after processing."""
        from backend.models.document import Document, DocumentStatus
        SessionLocal = _get_session_local()
        with SessionLocal() as session:
            document = session.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
            if document:
                document.status = DocumentStatus(status)
                document.chunk_count = chunk_count
                if error_message:
                    document.error_message = error_message
                session.commit()

            logger.info(
                "activity_update_status",
                document_id=document_id,
                status=status,
                chunk_count=chunk_count,
            )
