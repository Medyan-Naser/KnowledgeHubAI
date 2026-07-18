"""Health check endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_async_session

router = APIRouter()
settings = get_settings()


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    version: str
    environment: str
    timestamp: datetime
    database: str
    ollama: str


@router.get("/health", response_model=HealthResponse)
async def health_check(
    session: AsyncSession = Depends(get_async_session),
) -> HealthResponse:
    """
    Check application health status.

    Returns status of all critical services.
    """
    db_status = "healthy"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    ollama_status = "unknown"
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_host}/api/tags")
            ollama_status = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception:
        ollama_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
        database=db_status,
        ollama=ollama_status,
    )
