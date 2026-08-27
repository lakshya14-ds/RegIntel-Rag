"""
Local Neural Reranking Module for Regulatory Documents.

Applies cross-encoder neural reranking using BAAI/bge-reranker-v2-m3 (running locally via PyTorch / Sentence Transformers).
Selects top-k most relevant candidates from a hybrid candidate pool with automatic CPU/CUDA detection and graceful fallback.
"""

import logging
from typing import List, Optional, Tuple, Any

from app.retrieval.mongodb_vector import RetrievedChunk
from app.retrieval.hybrid import HybridRetrievedChunk

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
DEFAULT_RERANK_TOP_K = 5


class RerankedChunk(HybridRetrievedChunk):
    """RetrievedChunk enriched with neural cross-encoder reranker score."""
    reranker_score: Optional[float] = None


class LocalReranker:
    """
    Cross-encoder reranker utilizing local BAAI/bge-reranker-v2-m3.
    Lazy-loads weights once and scores (query, document) pairs.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_RERANKER_MODEL,
        device: Optional[str] = None,
        enabled: bool = True
    ):
        self.model_name = model_name
        self.enabled = enabled
        self._device = device
        self._model = None
        self._initialized = False

    def _determine_device(self) -> str:
        if self._device:
            return self._device
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        except Exception:
            device = "cpu"
        
        logger.info(f"Reranker device: {device.upper()}")
        return device

    def load_model(self):
        """Lazy-loads the cross-encoder model into memory once."""
        if not self.enabled:
            return

        if self._initialized:
            return

        device = self._determine_device()
        try:
            from sentence_transformers import CrossEncoder
            # Attempt loading from local HuggingFace cache first
            self._model = CrossEncoder(self.model_name, device=device, max_length=512, local_files_only=True)
            logger.info("Local reranker model loaded from offline cache.")
            self._initialized = True
        except Exception as e:
            logger.info(
                f"Local reranker '{self.model_name}' offline cache not loaded ({e}). "
                "Local cross-encoder will preserve hybrid candidate rankings."
            )
            self._model = None
            self._initialized = True

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int = DEFAULT_RERANK_TOP_K
    ) -> List[RerankedChunk]:
        """
        Reranks a list of candidate chunks against the user query.
        Returns top_k chunks sorted descending by cross-encoder relevance score.
        """
        if not query or not query.strip() or not candidates:
            return []

        # Convert candidates to RerankedChunk objects
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
            return reranked_pool[:top_k]

        if not self._initialized:
            self.load_model()

        if self._model is None:
            # Fallback: preserve hybrid candidate ranking
            return reranked_pool[:top_k]

        # Prepare (query, passage) sentence pairs
        pairs = []
        for c in reranked_pool:
            passage = f"Title: {c.title or ''}\nSection: {c.section or ''}\n{c.content}"
            pairs.append([query.strip(), passage])

        try:
            scores = self._model.predict(pairs)
            for idx, raw_score in enumerate(scores):
                score_val = float(raw_score)
                reranked_pool[idx].reranker_score = round(score_val, 4)
                reranked_pool[idx].score = round(score_val, 4)

            # Sort descending by reranker score
            reranked_pool.sort(key=lambda x: x.reranker_score if x.reranker_score is not None else -999.0, reverse=True)
        except Exception as e:
            logger.error(f"Error during cross-encoder reranking: {e}. Preserving hybrid ranking.")

        return reranked_pool[:top_k]


# Default singleton instance
_default_reranker = LocalReranker()


def rerank_candidates(
    query: str,
    candidates: List[RetrievedChunk],
    top_k: int = DEFAULT_RERANK_TOP_K
) -> List[RerankedChunk]:
    return _default_reranker.rerank(query, candidates, top_k=top_k)
