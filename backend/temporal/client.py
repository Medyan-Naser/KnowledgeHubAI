"""Temporal client for starting workflows."""

import uuid

import structlog
from temporalio.client import Client

from backend.config import get_settings
from backend.temporal.workflows import DocumentProcessingWorkflow

settings = get_settings()
logger = structlog.get_logger(__name__)

_client: Client | None = None


async def get_temporal_client() -> Client:
    """Get or create Temporal client."""
    global _client
    if _client is None:
        _client = await Client.connect(settings.temporal_host)
    return _client


async def start_document_processing(document_id: str) -> str:
    """
    Start a document processing workflow.

    Args:
        document_id: UUID of the document to process

    Returns:
        Workflow run ID
    """
    client = await get_temporal_client()

    workflow_id = f"doc-processing-{document_id}-{uuid.uuid4().hex[:8]}"

    handle = await client.start_workflow(
        DocumentProcessingWorkflow.run,
        document_id,
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )

    logger.info(
        "workflow_started",
        document_id=document_id,
        workflow_id=workflow_id,
        run_id=handle.result_run_id,
    )

    return workflow_id
