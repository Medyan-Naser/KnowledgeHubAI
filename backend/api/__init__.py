"""API module.

NOTE: Using lazy imports to avoid circular import issues.
"""

# Lazy import to avoid circular dependencies
def __getattr__(name):
    if name == "api_router":
        from backend.api.router import api_router
        return api_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["api_router"]
