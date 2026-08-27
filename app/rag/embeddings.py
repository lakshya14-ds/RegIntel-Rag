"""
Gemini Embedding Service for Regulatory Documents.

Generates 768-dimensional normalized vector embeddings using Google's GenAI SDK (gemini-embedding-001).
Handles enriched regulatory context, L2 normalization, duplicate avoidance, and exponential backoff retries.
"""

import os
import sys
import time
import math
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from google import genai
from google.genai import types

from app.config import settings
from app.ingestion.models import DocumentChunk, from_mongo
from app.ingestion.repository import save_chunks, create_chunk_indexes

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class EmbeddingError(Exception):
    """Raised when embedding generation fails or produces an invalid vector."""
    pass


def normalize_embedding(vector: List[float]) -> List[float]:
    """
    Applies L2 normalization to a vector: v / ||v||_2.
    Safely rejects zero or invalid vectors.
    """
    if not vector:
        raise EmbeddingError("Cannot normalize an empty vector.")

    squared_sum = sum(x * x for x in vector)
    norm = math.sqrt(squared_sum)

    if norm < 1e-12 or math.isnan(norm) or math.isinf(norm):
        raise EmbeddingError("Zero or invalid vector cannot be normalized.")

    return [x / norm for x in vector]


def validate_embedding(vector: Optional[List[float]], expected_dim: int = 768, tolerance: float = 1e-3) -> bool:
    """
    Validates that the embedding vector is 768-dimensional, strictly numeric,
    contains no NaN/Inf, and is L2-normalized.
    """
    if not vector or not isinstance(vector, (list, tuple)):
        return False

    if len(vector) != expected_dim:
        return False

    norm_sq = 0.0
    for val in vector:
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            return False
        norm_sq += val * val

    norm = math.sqrt(norm_sq)
    if abs(1.0 - norm) > tolerance:
        return False

    return True


@dataclass
class EmbeddingSummary:
    """Execution summary of the embedding generation pipeline."""
    total_chunks: int = 0
    successful: int = 0
    skipped: int = 0
    failed: int = 0
    failed_chunk_ids: List[str] = field(default_factory=list)
    failure_details: Dict[str, str] = field(default_factory=dict)

    def print_summary(self):
        print("\n" + "=" * 40)
        print("Embedding Summary")
        print("-" * 40)
        print(f"Total chunks     : {self.total_chunks}")
        print(f"Successful       : {self.successful}")
        print(f"Skipped (cached) : {self.skipped}")
        print(f"Failed           : {self.failed}")
        if self.failed_chunk_ids:
            print("-" * 40)
            print("Failed Chunk IDs:")
            for cid in self.failed_chunk_ids[:10]:
                print(f"  • {cid}: {self.failure_details.get(cid, 'Unknown error')}")
            if len(self.failed_chunk_ids) > 10:
                print(f"  ... and {len(self.failed_chunk_ids) - 10} more.")
        print("=" * 40 + "\n")


class GeminiEmbeddingService:
    """
    Client interface for generating normalized embeddings via Google GenAI SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        output_dimensionality: int = 768,
        client: Optional[Any] = None
    ):
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key and client is None:
            logger.warning("GEMINI_API_KEY is not configured in environment.")

        self.model_name = model_name or settings.embedding_model or "gemini-embedding-001"
        self.output_dimensionality = output_dimensionality or settings.embedding_dimension or 768
        self._client: Optional[Any] = client

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise EmbeddingError("GEMINI_API_KEY is missing. Cannot initialize Gemini GenAI client.")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @client.setter
    def client(self, value: Any):
        self._client = value

    def _call_api_with_retry(
        self,
        text: str,
        task_type: str,
        max_retries: int = 3,
        backoff_base: float = 1.5
    ) -> List[float]:
        """Executes the embed_content API request with exponential backoff for transient rate limits."""
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                config = types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.output_dimensionality
                )
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=text,
                    config=config
                )

                if not response.embeddings or not response.embeddings[0].values:
                    raise EmbeddingError("Gemini API returned an empty embedding response.")

                raw_values = response.embeddings[0].values
                if len(raw_values) != self.output_dimensionality:
                    raise EmbeddingError(
                        f"Expected {self.output_dimensionality} dimensions, got {len(raw_values)}"
                    )

                # Normalize to unit vector
                return normalize_embedding(raw_values)

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Gemini embedding attempt {attempt}/{max_retries} failed: {type(e).__name__} - {e}. "
                    f"Retrying in {backoff_base ** attempt:.1f}s..."
                )
                time.sleep(backoff_base ** attempt)

        raise EmbeddingError(f"Embedding request failed after {max_retries} retries: {last_error}") from last_error

    def embed_document(self, text: str) -> List[float]:
        """
        Embeds document or chunk text using RETRIEVAL_DOCUMENT task type.
        Returns a 768-dimensional L2-normalized vector.
        """
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed empty document text.")
        return self._call_api_with_retry(text.strip(), task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> List[float]:
        """
        Embeds a user search query using RETRIEVAL_QUERY task type.
        Returns a 768-dimensional L2-normalized vector.
        """
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed empty query text.")
        return self._call_api_with_retry(text.strip(), task_type="RETRIEVAL_QUERY")

    def embed_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        """
        Embeds a single DocumentChunk, populating embedding fields.
        Skips generation if valid 768-dim embedding already exists.
        """
        if validate_embedding(chunk.embedding, expected_dim=self.output_dimensionality):
            return chunk

        text_to_embed = chunk.embedding_text or chunk.content
        vector = self.embed_document(text_to_embed)

        chunk.embedding = vector
        chunk.embedding_model = self.model_name
        chunk.embedding_dimensions = self.output_dimensionality
        return chunk

    def embed_chunks(
        self,
        chunks: List[DocumentChunk],
        batch_size: int = 10,
        persist_db: bool = False,
        rate_limit_delay: float = 0.1
    ) -> EmbeddingSummary:
        """
        Iterates over DocumentChunks, generates embeddings, persists updated chunks to disk,
        and optionally saves them to MongoDB Atlas.
        """
        summary = EmbeddingSummary(total_chunks=len(chunks))
        updated_chunks: List[DocumentChunk] = []

        logger.info(f"Starting embedding generation for {len(chunks)} chunks (model={self.model_name}, dim={self.output_dimensionality})")

        for idx, chunk in enumerate(chunks):
            # Check cache / existing valid embedding
            if validate_embedding(chunk.embedding, expected_dim=self.output_dimensionality):
                summary.skipped += 1
                updated_chunks.append(chunk)
                continue

            try:
                text_to_embed = chunk.embedding_text or chunk.content
                vector = self.embed_document(text_to_embed)

                chunk.embedding = vector
                chunk.embedding_model = self.model_name
                chunk.embedding_dimensions = self.output_dimensionality

                summary.successful += 1
                updated_chunks.append(chunk)

                if rate_limit_delay > 0:
                    time.sleep(rate_limit_delay)

            except Exception as e:
                summary.failed += 1
                summary.failed_chunk_ids.append(chunk.chunk_id)
                summary.failure_details[chunk.chunk_id] = str(e)
                logger.error(f"Failed to embed chunk {chunk.chunk_id}: {e}")
                updated_chunks.append(chunk)

            if (idx + 1) % 25 == 0 or (idx + 1) == len(chunks):
                logger.info(f"Embedding progress: {idx + 1}/{len(chunks)} processed ({summary.successful} success, {summary.skipped} skipped, {summary.failed} failed)")

        # Persist updated chunks to local chunk JSON files
        from app.ingestion.chunker import save_chunks_to_file
        save_chunks_to_file(updated_chunks)

        # Optionally persist to MongoDB chunks collection
        if persist_db:
            try:
                create_chunk_indexes()
                saved_count = save_chunks(updated_chunks)
                logger.info(f"Persisted {saved_count} chunks with embeddings to MongoDB Atlas")
            except Exception as e:
                logger.error(f"Failed to save embedded chunks to MongoDB: {e}")

        return summary


# Default service instance
_default_embedding_service = GeminiEmbeddingService()


def embed_document(text: str) -> List[float]:
    return _default_embedding_service.embed_document(text)


def embed_query(text: str) -> List[float]:
    return _default_embedding_service.embed_query(text)


def embed_chunks(
    chunks: List[DocumentChunk],
    batch_size: int = 10,
    persist_db: bool = False
) -> EmbeddingSummary:
    return _default_embedding_service.embed_chunks(chunks, batch_size=batch_size, persist_db=persist_db)


def run_embedding_pipeline(
    chunks_dir: Optional[Path] = None,
    store_db: bool = False,
    limit: Optional[int] = None
) -> EmbeddingSummary:
    """
    Loads all chunk files from data/processed/chunks/, runs the embedding service,
    and reports execution metrics.
    """
    from app.ingestion.chunk_validator import load_all_chunks

    chunks = load_all_chunks(chunks_dir=chunks_dir)
    if not chunks:
        print("No chunks found in data/processed/chunks/. Run chunker first (python -m app.ingestion.chunker)")
        return EmbeddingSummary()

    if limit and limit > 0:
        chunks = chunks[:limit]
        logger.info(f"Limiting embedding generation to first {limit} chunks")

    service = GeminiEmbeddingService()
    summary = service.embed_chunks(chunks, persist_db=store_db)
    summary.print_summary()
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate Gemini embeddings for regulatory document chunks.")
    parser.add_argument("--store-db", action="store_true", help="Persist chunks and embeddings to MongoDB Atlas.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of chunks to process.")
    args = parser.parse_args()

    run_embedding_pipeline(store_db=args.store_db, limit=args.limit)
