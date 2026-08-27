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
    embedding_model: str = Field(
        default="gemini-embedding-001"
    )
    embedding_dimension: int = Field(
        default=768
    )

    # Chunking Configuration
    target_chunk_tokens: int = Field(default=800)
    max_chunk_tokens: int = Field(default=1000)
    min_chunk_tokens: int = Field(default=150)
    overlap_tokens: int = Field(default=100)

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
