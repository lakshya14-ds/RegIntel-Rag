"""
Local Neural Cross-Encoder Reranking Module for RegIntel RAG (Phase 36).

Applies cross-encoder neural reranking using BAAI/bge-reranker-v2-m3 (running locally via PyTorch / Sentence Transformers).
Selects top-k most relevant candidates from a hybrid candidate pool with automatic CPU/CUDA detection,
lazy model initialization, batched inference, and graceful fallback if the model is unavailable.
"""

import time
import logging
from typing import List, Optional, Tuple, Any

from app.config import settings
from app.retrieval.mongodb_vector import RetrievedChunk
from app.retrieval.hybrid import HybridRetrievedChunk

logger = logging.getLogger("regintel.retrieval.reranker")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class RerankedChunk(HybridRetrievedChunk):
    """RetrievedChunk enriched with neural cross-encoder reranker score."""
    reranker_score: Optional[float] = None


class LocalReranker:
    """
    Cross-encoder reranker utilizing local BAAI/bge-reranker-v2-m3.
    Lazy-loads weights once and scores (query, document) pairs in batches.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        enabled: Optional[bool] = None,
        default_top_k: Optional[int] = None
    ):
        self.model_name = model_name or settings.reranker_model
        self.enabled = settings.enable_reranker if enabled is None else enabled
        self._device_setting = device or settings.reranker_device
        self.default_top_k = default_top_k or settings.reranker_top_k
        self._device = None
        self._model = None
        self._initialized = False

    @property
    def device(self) -> str:
        """Returns the configured or detected compute device."""
        if self._device is not None:
            return self._device
        return self._device_setting or "auto"

    def _determine_device(self) -> str:
        """Determines the compute device (CUDA or CPU)."""
        if self._device_setting and self._device_setting.lower() != "auto":
            dev = self._device_setting.lower()
            logger.info(f"Reranker device: {dev.upper()}")
            return dev

        try:
            import torch
            dev = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            dev = "cpu"

        logger.info(f"Reranker device: {dev.upper()}")
        return dev

    def load_model(self) -> None:
        """Lazy-loads the cross-encoder model into memory once."""
        if not self.enabled or self._initialized:
            return

        self._device = self._determine_device()
        try:
            import torch
            import os
            if self._device == "cpu":
                threads = min(8, os.cpu_count() or 4)
                torch.set_num_threads(threads)
                logger.info(f"PyTorch CPU multithreading configured with {threads} threads.")

            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name, device=self._device, max_length=384)
            logger.info(f"Local cross-encoder '{self.model_name}' loaded successfully on {self._device.upper()}.")
            self._initialized = True
        except Exception as e:
            logger.warning(
                f"Local reranker '{self.model_name}' could not be initialized ({e}). "
                "Local cross-encoder will preserve hybrid candidate rankings."
            )
            self._model = None
            self._initialized = True

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: Optional[int] = None
    ) -> List[RerankedChunk]:
        """
        Reranks candidate chunks against the query using cross-encoder sentence pairs.
        Returns top_k chunks sorted descending by cross-encoder relevance score.
        """
        k = top_k if top_k is not None else self.default_top_k

        if not query or not query.strip() or not candidates:
            return []

        # Convert candidates to RerankedChunk objects preserving original metadata
        reranked_pool: List[RerankedChunk] = []
        for c in candidates:
            if isinstance(c, HybridRetrievedChunk):
                r_chunk = RerankedChunk(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    title=c.title,
                    content=c.content,
                    section=c.section,
                    source=c.source,
                    category=c.category,
                    document_type=c.document_type,
                    published_date=c.published_date,
                    effective_date=c.effective_date,
                    url=c.url,
                    score=c.score,
                    vector_score=c.vector_score,
                    bm25_score=c.bm25_score,
                    hybrid_score=c.hybrid_score,
                    retrieval_methods=c.retrieval_methods,
                    reranker_score=None
                )
            else:
                r_chunk = RerankedChunk(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    title=c.title,
                    content=c.content,
                    section=c.section,
                    source=c.source,
                    category=c.category,
                    document_type=c.document_type,
                    published_date=c.published_date,
                    effective_date=c.effective_date,
                    url=c.url,
                    score=c.score,
                    vector_score=c.score,
                    bm25_score=None,
                    hybrid_score=c.score,
                    retrieval_methods=["vector"],
                    reranker_score=None
                )
            reranked_pool.append(r_chunk)

        # If reranking disabled, return candidate pool directly
        if not self.enabled:
            return reranked_pool[:k]

        if not self._initialized:
            self.load_model()

        if self._model is None:
            # Fallback: preserve original candidate ranking
            return reranked_pool[:k]

        # Prepare (query, passage) sentence pairs for batch inference
        pairs = []
        for c in reranked_pool:
            passage = f"Title: {c.title or 'N/A'}\nSection: {c.section or 'General'}\n{c.content}"
            pairs.append([query.strip(), passage])

        try:
            scores = self._model.predict(pairs, batch_size=16)
            for idx, raw_score in enumerate(scores):
                score_val = float(raw_score)
                reranked_pool[idx].reranker_score = round(score_val, 4)
                reranked_pool[idx].score = round(score_val, 4)

            # Sort descending by cross-encoder score
            reranked_pool.sort(
                key=lambda x: x.reranker_score if x.reranker_score is not None else -999.0,
                reverse=True
            )
        except Exception as e:
            logger.error(f"Error during cross-encoder reranking ({e}). Preserving candidate ranking.")

        return reranked_pool[:k]


# Singleton default instance
_default_reranker = LocalReranker()


def rerank_candidates(
    query: str,
    candidates: List[RetrievedChunk],
    top_k: Optional[int] = None
) -> List[RerankedChunk]:
    """Convenience function to rerank candidates with the default singleton reranker."""
    return _default_reranker.rerank(query, candidates, top_k=top_k)
