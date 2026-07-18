"""Temporal worker for document processing."""

import asyncio

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from backend.config import get_settings
from backend.temporal.activities import DocumentActivities
from backend.temporal.workflows import DocumentProcessingWorkflow

settings = get_settings()
logger = structlog.get_logger(__name__)


async def create_worker() -> Worker:
    """Create and return a Temporal worker."""
    client = await Client.connect(settings.temporal_host)

    activities = DocumentActivities()

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[DocumentProcessingWorkflow],
        activities=[
            activities.extract_text,
            activities.chunk_text,
            activities.generate_embeddings,
            activities.update_document_status,
        ],
    )

    logger.info(
        "temporal_worker_created",
        task_queue=settings.temporal_task_queue,
        namespace=settings.temporal_namespace,
    )

    return worker


async def run_worker():
    """Run the Temporal worker."""
    worker = await create_worker()
    logger.info("temporal_worker_starting")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
