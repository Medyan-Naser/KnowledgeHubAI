"""Embedding service for generating vector embeddings using Ollama."""

import gc
import time
import structlog
import ollama
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using Ollama.
    
    Includes resource management to prevent GPU/memory overload.
    """

    def __init__(self):
        self.model = settings.embedding_model
        self.client = ollama.Client(host=settings.ollama_host)
        self.batch_size = settings.embedding_batch_size
        self.batch_delay = settings.embedding_batch_delay_seconds
        self._embeddings_count = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        start_time = time.time()
        
        response = self.client.embeddings(model=self.model, prompt=text)
        embedding = response["embedding"]
        
        elapsed_ms = (time.time() - start_time) * 1000

        logger.debug(
            "embedding_generated",
            text_length=len(text),
            embedding_dim=len(embedding),
            elapsed_ms=round(elapsed_ms, 2),
        )

        return embedding

    def generate_embeddings_batch(
        self, 
        texts: list[str],
        progress_callback: callable = None
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts with resource management.

        Uses batch processing with delays to prevent GPU overload.

        Args:
            texts: List of texts to embed
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            List of embedding vectors
        """
        embeddings = []
        total = len(texts)
        
        logger.info(
            "batch_embedding_starting",
            total_texts=total,
            batch_size=self.batch_size,
            batch_delay_seconds=self.batch_delay,
        )
        
        for i, text in enumerate(texts):
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)
            
            # Progress callback
            if progress_callback:
                progress_callback(i + 1, total)
            
            # Resource management: pause after each batch to prevent GPU overload
            if (i + 1) % self.batch_size == 0 and (i + 1) < total:
                logger.debug(
                    "batch_pause",
                    processed=i + 1,
                    remaining=total - i - 1,
                    delay_seconds=self.batch_delay,
                )
                # Force garbage collection to free memory
                gc.collect()
                # Delay to let GPU/CPU cool down
                time.sleep(self.batch_delay)

        logger.info(
            "batch_embeddings_completed",
            batch_size=total,
            embeddings_generated=len(embeddings),
        )

        return embeddings

    def cosine_similarity(
        self, embedding1: list[float], embedding2: list[float]
    ) -> float:
        """Calculate cosine similarity between two embeddings."""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))
