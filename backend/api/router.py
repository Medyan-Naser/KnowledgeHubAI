"""Main API router combining all endpoint routers."""

from fastapi import APIRouter

from backend.api.endpoints import chat, documents, health

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
