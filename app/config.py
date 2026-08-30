import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(PROJECT_ROOT / ".env")


class ConfigurationError(Exception):
    """Raised when application configuration is invalid or missing required variables."""
    pass


class Settings(BaseSettings):
    """Application settings with type validation."""
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # MongoDB Configuration
    mongodb_uri: str = Field(
        default_factory=lambda: os.getenv("MONGODB_URI", "")
    )
    mongodb_db: str = Field(
        default_factory=lambda: os.getenv("MONGODB_DB") or os.getenv("MONGODB_DB_NAME", "regintel")
    )
    mongodb_collection: str = Field(
        default_factory=lambda: os.getenv("MONGODB_COLLECTION") or os.getenv("MONGODB_COLLECTION_NAME", "documents")
    )
    mongodb_chunks_collection: str = Field(
        default_factory=lambda: os.getenv("MONGODB_CHUNKS_COLLECTION", "chunks")
    )

    # Gemini / LLM key & Embedding Settings
    gemini_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    embedding_provider: str = Field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "gemini")
    )
    embedding_model: str = Field(
        default="gemini-embedding-001"
    )
    embedding_dimension: int = Field(
        default=768
    )

    # LLM Generation Provider Settings (Phase 48-49)
    llm_provider: str = Field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini").lower()
    )
    llm_fallback_enabled: bool = Field(
        default_factory=lambda: os.getenv("LLM_FALLBACK_ENABLED", "false").lower() in ("true", "1")
    )
    gemini_generation_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_GENERATION_MODEL", "models/gemini-flash-lite-latest")
    )
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    )
    ollama_model: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2")
    )
    ollama_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30.0"))
    )

    # Chunking Configuration
    target_chunk_tokens: int = Field(default=800)
    max_chunk_tokens: int = Field(default=1000)
    min_chunk_tokens: int = Field(default=150)
    overlap_tokens: int = Field(default=100)

    # Temporal & Change Detection Settings
    temporal_boost_weight: float = Field(default=0.10)
    change_max_sections: int = Field(default=30)
    change_max_candidate_predecessors: int = Field(default=10)
    # Reranker Configuration (Phase 36-37)
    enable_reranker: bool = Field(default_factory=lambda: os.getenv("ENABLE_RERANKER", "true").lower() in ("true", "1"))
    reranker_model: str = Field(default_factory=lambda: os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"))
    reranker_candidates: int = Field(default_factory=lambda: int(os.getenv("RERANKER_CANDIDATES", "20")))
    reranker_top_k: int = Field(default_factory=lambda: int(os.getenv("RERANKER_TOP_K", "5")))
    reranker_device: str = Field(default_factory=lambda: os.getenv("RERANKER_DEVICE", "auto"))

    # Version & Status
    regintel_version: str = Field(default_factory=lambda: os.getenv("REGINTEL_VERSION", "0.1.0"))

    # API & Frontend Configuration
    fastapi_host: str = Field(default_factory=lambda: os.getenv("FASTAPI_HOST", "0.0.0.0"))
    fastapi_port: int = Field(default_factory=lambda: int(os.getenv("FASTAPI_PORT", "8000")))
    cors_origins: str = Field(default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501,http://localhost:8000,http://127.0.0.1:8000"))
    debug_mode: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() in ("true", "1"))
    fastapi_base_url: str = Field(default_factory=lambda: os.getenv("FASTAPI_BASE_URL", "http://localhost:8000"))

    # Observability — MLflow Configuration (Phase 32)
    mlflow_tracking_uri: str = Field(default_factory=lambda: os.getenv("MLFLOW_TRACKING_URI", str(PROJECT_ROOT / "mlruns")))
    mlflow_experiment_name: str = Field(default_factory=lambda: os.getenv("MLFLOW_EXPERIMENT_NAME", "RegIntel-RAG"))
    mlflow_enabled: bool = Field(default_factory=lambda: os.getenv("MLFLOW_ENABLED", "true").lower() in ("true", "1"))

    # Observability — Langfuse Configuration (Phase 33)
    langfuse_public_key: Optional[str] = Field(default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY"))
    langfuse_secret_key: Optional[str] = Field(default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY"))
    langfuse_host: str = Field(default_factory=lambda: os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"))
    langfuse_enabled: bool = Field(default_factory=lambda: os.getenv("LANGFUSE_ENABLED", "false").lower() in ("true", "1"))

    # Paths
    raw_data_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "raw"
    )
    processed_data_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "processed"
    )
    chunks_data_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "processed" / "chunks"
    )

    @field_validator("mongodb_uri")
    @classmethod
    def validate_mongodb_uri(cls, v: str) -> str:
        if not v or not v.strip():
            raise ConfigurationError("MONGODB_URI environment variable is required and cannot be empty.")
        return v.strip()


def get_settings() -> Settings:
    """Instantiate and return settings, ensuring required storage directories exist."""
    try:
        settings = Settings()
    except Exception as e:
        raise ConfigurationError(f"Failed to load application configuration: {e}") from e

    # Ensure required data directories exist
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_data_dir.mkdir(parents=True, exist_ok=True)
    settings.chunks_data_dir.mkdir(parents=True, exist_ok=True)
    return settings


# Lazy/Singleton instance
settings = get_settings()
