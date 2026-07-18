"""Temporal workflow module.

NOTE: Using lazy imports to avoid issues with Temporal's workflow sandbox.
Import directly from submodules instead of from this package.
"""


def __getattr__(name):
    """Lazy import to avoid sandbox issues."""
    if name == "DocumentProcessingWorkflow":
        from backend.temporal.workflows import DocumentProcessingWorkflow
        return DocumentProcessingWorkflow
    elif name == "DocumentActivities":
        from backend.temporal.activities import DocumentActivities
        return DocumentActivities
    elif name == "create_worker":
        from backend.temporal.worker import create_worker
        return create_worker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["DocumentProcessingWorkflow", "DocumentActivities", "create_worker"]
