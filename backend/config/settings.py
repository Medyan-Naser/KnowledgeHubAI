"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Enterprise Knowledge Assistant"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # API
    api_prefix: str = "/api/v1"
    allowed_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:8000"])

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "enterprise_rag"

    @computed_field
    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """Construct synchronous PostgreSQL connection URL for Alembic."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Ollama
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "llama3"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768

    # RAG Configuration
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k_results: int = 5
    similarity_threshold: float = 0.7

    # Resource Management (GPU/Memory protection)
    embedding_batch_size: int = 5  # Process N chunks before pausing
    embedding_batch_delay_seconds: float = 0.5  # Delay between batches
    embedding_request_timeout: float = 30.0  # Timeout per embedding request
    max_concurrent_embeddings: int = 1  # Max parallel embedding requests

    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "document-processing"

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "enterprise-rag"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # File Upload
    upload_dir: str = "data/uploads"
    max_file_size_mb: int = 50
    allowed_extensions: list[str] = Field(default=[".pdf", ".md", ".txt"])


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
