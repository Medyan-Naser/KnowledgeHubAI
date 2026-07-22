"""Services module.

NOTE: Using lazy imports to avoid circular import issues.
Import services directly from their modules instead of from this package.
Example: from backend.services.document_service import DocumentService
"""

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "DocumentService":
        from backend.services.document_service import DocumentService
        return DocumentService
    elif name == "EmbeddingService":
        from backend.services.embedding_service import EmbeddingService
        return EmbeddingService
    elif name == "RAGService":
        from backend.services.rag_service import RAGService
        return RAGService
    elif name == "LLMService":
        from backend.services.llm_service import LLMService
        return LLMService
    elif name == "TextProcessor":
        from backend.services.text_processor import TextProcessor
        return TextProcessor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["DocumentService", "EmbeddingService", "RAGService", "LLMService", "TextProcessor"]
