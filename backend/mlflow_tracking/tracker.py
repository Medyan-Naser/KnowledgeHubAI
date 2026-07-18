"""MLflow experiment tracking for RAG operations."""

import time
from datetime import datetime, timezone
from typing import Any

import mlflow
import structlog

from backend.config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)


class MLflowTracker:
    """Tracker for logging RAG experiments to MLflow."""

    def __init__(self):
        self.tracking_uri = settings.mlflow_tracking_uri
        self.experiment_name = settings.mlflow_experiment_name
        self._setup_mlflow()

    def _setup_mlflow(self) -> None:
        """Initialize MLflow tracking."""
        try:
            mlflow.set_tracking_uri(self.tracking_uri)
            experiment = mlflow.get_experiment_by_name(self.experiment_name)
            if experiment is None:
                mlflow.create_experiment(self.experiment_name)
            mlflow.set_experiment(self.experiment_name)
            logger.info(
                "mlflow_initialized",
                tracking_uri=self.tracking_uri,
                experiment=self.experiment_name,
            )
        except Exception as e:
            logger.warning("mlflow_init_failed", error=str(e))

    def log_document_processing(
        self,
        document_id: str,
        filename: str,
        chunk_count: int,
        processing_time_ms: float,
        file_size: int,
        status: str,
    ) -> str | None:
        """
        Log document processing metrics to MLflow.

        Returns:
            Run ID if successful, None otherwise
        """
        try:
            with mlflow.start_run(run_name=f"doc-{document_id[:8]}") as run:
                mlflow.log_params(
                    {
                        "document_id": document_id,
                        "filename": filename,
                        "embedding_model": settings.embedding_model,
                        "chunk_size": settings.chunk_size,
                        "chunk_overlap": settings.chunk_overlap,
                    }
                )

                mlflow.log_metrics(
                    {
                        "chunk_count": chunk_count,
                        "processing_time_ms": processing_time_ms,
                        "file_size_bytes": file_size,
                    }
                )

                mlflow.set_tags(
                    {
                        "operation": "document_processing",
                        "status": status,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

                logger.info(
                    "mlflow_document_logged",
                    run_id=run.info.run_id,
                    document_id=document_id,
                )

                return run.info.run_id

        except Exception as e:
            logger.warning("mlflow_logging_failed", error=str(e))
            return None

    def log_rag_query(
        self,
        query_id: str,
        query: str,
        retrieved_count: int,
        latency_ms: float,
        token_count: int | None,
        llm_model: str,
        embedding_model: str,
    ) -> str | None:
        """
        Log RAG query metrics to MLflow.

        Returns:
            Run ID if successful, None otherwise
        """
        try:
            with mlflow.start_run(run_name=f"query-{query_id[:8]}") as run:
                mlflow.log_params(
                    {
                        "query_id": query_id,
                        "llm_model": llm_model,
                        "embedding_model": embedding_model,
                        "top_k": settings.top_k_results,
                    }
                )

                metrics = {
                    "retrieved_count": retrieved_count,
                    "latency_ms": latency_ms,
                    "query_length": len(query),
                }
                if token_count:
                    metrics["token_count"] = token_count

                mlflow.log_metrics(metrics)

                mlflow.set_tags(
                    {
                        "operation": "rag_query",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

                logger.info(
                    "mlflow_query_logged",
                    run_id=run.info.run_id,
                    query_id=query_id,
                )

                return run.info.run_id

        except Exception as e:
            logger.warning("mlflow_logging_failed", error=str(e))
            return None

    def log_embedding_generation(
        self,
        document_id: str,
        batch_size: int,
        total_time_ms: float,
        embedding_dimensions: int,
    ) -> str | None:
        """Log embedding generation metrics."""
        try:
            with mlflow.start_run(run_name=f"embed-{document_id[:8]}") as run:
                mlflow.log_params(
                    {
                        "document_id": document_id,
                        "embedding_model": settings.embedding_model,
                        "embedding_dimensions": embedding_dimensions,
                    }
                )

                mlflow.log_metrics(
                    {
                        "batch_size": batch_size,
                        "total_time_ms": total_time_ms,
                        "avg_time_per_embedding_ms": total_time_ms / batch_size if batch_size > 0 else 0,
                    }
                )

                mlflow.set_tags(
                    {
                        "operation": "embedding_generation",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

                return run.info.run_id

        except Exception as e:
            logger.warning("mlflow_logging_failed", error=str(e))
            return None
