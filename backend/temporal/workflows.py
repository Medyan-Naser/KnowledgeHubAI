"""Temporal workflows for document processing."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# NOTE: We don't import activities here - they're registered by the worker
# and referenced by string name in execute_activity calls


@workflow.defn
class DocumentProcessingWorkflow:
    """Workflow for processing uploaded documents."""

    @workflow.run
    async def run(self, document_id: str) -> dict:
        """
        Execute the document processing pipeline.

        Steps:
        1. Extract text from document
        2. Chunk the text
        3. Generate embeddings
        4. Store in database
        5. Log to MLflow
        """
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=60),
            backoff_coefficient=2.0,
            maximum_attempts=3,
        )

        try:
            text = await workflow.execute_activity(
                "extract_text",
                document_id,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )

            chunks = await workflow.execute_activity(
                "chunk_text",
                args=[document_id, text],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=retry_policy,
            )

            chunk_count = await workflow.execute_activity(
                "generate_embeddings",
                args=[document_id, chunks],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=retry_policy,
            )

            await workflow.execute_activity(
                "update_document_status",
                args=[document_id, "completed", chunk_count, None],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            workflow.logger.info(
                f"Document {document_id} processed successfully with {chunk_count} chunks"
            )

            return {
                "document_id": document_id,
                "status": "completed",
                "chunk_count": chunk_count,
            }

        except Exception as e:
            error_message = str(e)

            await workflow.execute_activity(
                "update_document_status",
                args=[document_id, "failed", 0, error_message],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            workflow.logger.error(f"Document {document_id} processing failed: {error_message}")

            return {
                "document_id": document_id,
                "status": "failed",
                "error": error_message,
            }
