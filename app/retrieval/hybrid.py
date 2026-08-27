"""
Hybrid Retrieval Module for Regulatory Intelligence.

Fuses semantic vector retrieval (MongoDB Vector Search) with lexical retrieval (BM25Okapi)
using Reciprocal Rank Fusion (RRF) or Min-Max weighted normalization.
"""

import logging
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

from app.retrieval.mongodb_vector import MongoDBVectorRetriever, RetrievedChunk
from app.retrieval.bm25 import BM25Retriever

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Configurable Hybrid Retrieval Defaults
DEFAULT_VECTOR_WEIGHT = 0.6
DEFAULT_BM25_WEIGHT = 0.4
DEFAULT_CANDIDATE_POOL = 20
DEFAULT_HYBRID_TOP_K = 5
DEFAULT_RRF_K = 60


class HybridRetrievedChunk(RetrievedChunk):
    """Extended RetrievedChunk containing multi-channel scores and provenance."""
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    hybrid_score: float = 0.0
    retrieval_methods: List[str] = Field(default_factory=list)


class HybridRetriever:
    """
    Orchestrates multi-channel retrieval across MongoDB Vector Search and BM25 Keyword Search.
    Merges, normalizes, and ranks candidate chunks.
    """

    def __init__(
        self,
        vector_retriever: Optional[MongoDBVectorRetriever] = None,
        bm25_retriever: Optional[BM25Retriever] = None,
        vector_weight: float = DEFAULT_VECTOR_WEIGHT,
        bm25_weight: float = DEFAULT_BM25_WEIGHT,
        candidate_pool: int = DEFAULT_CANDIDATE_POOL,
        rrf_k: int = DEFAULT_RRF_K,
        fusion_method: Literal["rrf", "min_max"] = "rrf"
    ):
        self.vector_retriever = vector_retriever or MongoDBVectorRetriever(default_top_k=candidate_pool)
        self.bm25_retriever = bm25_retriever or BM25Retriever()
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.candidate_pool = candidate_pool
        self.rrf_k = rrf_k
        self.fusion_method = fusion_method

    def _normalize_min_max(self, scores: List[float]) -> List[float]:
        """Applies min-max scaling to a list of scores to bound them in [0, 1]."""
        if not scores:
            return []
        min_s = min(scores)
        max_s = max(scores)
        diff = max_s - min_s
        if diff < 1e-9:
            return [1.0] * len(scores)
        return [(s - min_s) / diff for s in scores]

    def _fuse_rrf(
        self,
        vector_results: List[RetrievedChunk],
        bm25_results: List[RetrievedChunk]
    ) -> List[HybridRetrievedChunk]:
        """
        Applies Reciprocal Rank Fusion (RRF) with channel weighting:
        RRF_score(d) = (w_vec / (k + rank_vec)) + (w_bm25 / (k + rank_bm25))
        Scales to [0.0, 1.0] relative to theoretical rank-1 maximum.
        """
        combined_chunks: Dict[str, HybridRetrievedChunk] = {}
        rrf_scores: Dict[str, float] = {}

        # 1. Process Vector Search candidates
        for rank, chunk in enumerate(vector_results, start=1):
            cid = chunk.chunk_id
            score_contrib = self.vector_weight * (1.0 / (self.rrf_k + rank))
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score_contrib

            combined_chunks[cid] = HybridRetrievedChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                title=chunk.title,
                content=chunk.content,
                section=chunk.section,
                source=chunk.source,
                category=chunk.category,
                document_type=chunk.document_type,
                published_date=chunk.published_date,
                effective_date=chunk.effective_date,
                url=chunk.url,
                score=0.0,
                vector_score=chunk.score,
                bm25_score=None,
                hybrid_score=0.0,
                retrieval_methods=["vector"]
            )

        # 2. Process BM25 candidates
        for rank, chunk in enumerate(bm25_results, start=1):
            cid = chunk.chunk_id
            score_contrib = self.bm25_weight * (1.0 / (self.rrf_k + rank))
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score_contrib

            if cid in combined_chunks:
                combined_chunks[cid].bm25_score = chunk.score
                if "bm25" not in combined_chunks[cid].retrieval_methods:
                    combined_chunks[cid].retrieval_methods.append("bm25")
            else:
                combined_chunks[cid] = HybridRetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    content=chunk.content,
                    section=chunk.section,
                    source=chunk.source,
                    category=chunk.category,
                    document_type=chunk.document_type,
                    published_date=chunk.published_date,
                    effective_date=chunk.effective_date,
                    url=chunk.url,
                    score=0.0,
                    vector_score=None,
                    bm25_score=chunk.score,
                    hybrid_score=0.0,
                    retrieval_methods=["bm25"]
                )

        # 3. Normalize RRF scores: max possible is (w_vec + w_bm25) / (rrf_k + 1)
        max_possible_rrf = (self.vector_weight + self.bm25_weight) / (self.rrf_k + 1.0)
        scale_factor = (1.0 / max_possible_rrf) if max_possible_rrf > 0 else 1.0

        for cid, h_chunk in combined_chunks.items():
            norm_score = rrf_scores[cid] * scale_factor
            h_chunk.hybrid_score = round(norm_score, 4)
            h_chunk.score = h_chunk.hybrid_score

        # Sort descending by hybrid RRF score
        sorted_results = sorted(combined_chunks.values(), key=lambda x: x.hybrid_score, reverse=True)
        return sorted_results

    def _fuse_min_max(
        self,
        vector_results: List[RetrievedChunk],
        bm25_results: List[RetrievedChunk]
    ) -> List[HybridRetrievedChunk]:
        """
        Fuses scores by min-max normalizing vector and BM25 scores and computing linear combination:
        hybrid_score = w_vec * norm(vec_score) + w_bm25 * norm(bm25_score)
        """
        combined_chunks: Dict[str, HybridRetrievedChunk] = {}

        vec_raw_scores = [c.score for c in vector_results]
        vec_norm_scores = self._normalize_min_max(vec_raw_scores)

        for chunk, norm_s in zip(vector_results, vec_norm_scores):
            cid = chunk.chunk_id
            combined_chunks[cid] = HybridRetrievedChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                title=chunk.title,
                content=chunk.content,
                section=chunk.section,
                source=chunk.source,
                category=chunk.category,
                document_type=chunk.document_type,
                published_date=chunk.published_date,
                effective_date=chunk.effective_date,
                url=chunk.url,
                score=0.0,
                vector_score=chunk.score,
                bm25_score=None,
                hybrid_score=self.vector_weight * norm_s,
                retrieval_methods=["vector"]
            )

        bm25_raw_scores = [c.score for c in bm25_results]
        bm25_norm_scores = self._normalize_min_max(bm25_raw_scores)

        for chunk, norm_s in zip(bm25_results, bm25_norm_scores):
            cid = chunk.chunk_id
            bm25_contrib = self.bm25_weight * norm_s
            if cid in combined_chunks:
                combined_chunks[cid].bm25_score = chunk.score
                combined_chunks[cid].hybrid_score += bm25_contrib
                if "bm25" not in combined_chunks[cid].retrieval_methods:
                    combined_chunks[cid].retrieval_methods.append("bm25")
            else:
                combined_chunks[cid] = HybridRetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    content=chunk.content,
                    section=chunk.section,
                    source=chunk.source,
                    category=chunk.category,
                    document_type=chunk.document_type,
                    published_date=chunk.published_date,
                    effective_date=chunk.effective_date,
                    url=chunk.url,
                    score=0.0,
                    vector_score=None,
                    bm25_score=chunk.score,
                    hybrid_score=bm25_contrib,
                    retrieval_methods=["bm25"]
                )

        for h_chunk in combined_chunks.values():
            h_chunk.hybrid_score = round(h_chunk.hybrid_score, 4)
            h_chunk.score = h_chunk.hybrid_score

        sorted_results = sorted(combined_chunks.values(), key=lambda x: x.hybrid_score, reverse=True)
        return sorted_results

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_HYBRID_TOP_K,
        candidate_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[HybridRetrievedChunk]:
        """
        Executes hybrid retrieval combining Vector and BM25 retrieval.
        Returns top_k fused candidate chunks.
        """
        if not query or not query.strip():
            return []

        c_pool = candidate_k or self.candidate_pool

        # 1. Retrieve Vector Search candidates
        try:
            vector_candidates = self.vector_retriever.retrieve(
                query_text=query.strip(),
                limit=c_pool,
                filter_dict=filter_dict
            )
        except Exception as e:
            logger.warning(f"Vector search failed in hybrid retriever: {e}")
            vector_candidates = []

        # 2. Retrieve BM25 Keyword Search candidates
        try:
            bm25_candidates = self.bm25_retriever.search(
                query=query.strip(),
                top_k=c_pool,
                filter_dict=filter_dict
            )
        except Exception as e:
            logger.warning(f"BM25 search failed in hybrid retriever: {e}")
            bm25_candidates = []

        # 3. Fuse candidates
        if self.fusion_method == "min_max":
            fused = self._fuse_min_max(vector_candidates, bm25_candidates)
        else:
            fused = self._fuse_rrf(vector_candidates, bm25_candidates)

        return fused[:top_k]

    def search_debug(
        self,
        query: str,
        top_k: int = DEFAULT_HYBRID_TOP_K,
        candidate_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Retrieval diagnostic tool providing visibility into vector, BM25, and hybrid ranks.
        """
        c_pool = candidate_k or self.candidate_pool
        vector_candidates = self.vector_retriever.retrieve(query.strip(), limit=c_pool, filter_dict=filter_dict)
        bm25_candidates = self.bm25_retriever.search(query.strip(), top_k=c_pool, filter_dict=filter_dict)
        hybrid_results = self.search(query, top_k=top_k, candidate_k=c_pool, filter_dict=filter_dict)

        return {
            "query": query,
            "vector_results": [c.model_dump() for c in vector_candidates[:top_k]],
            "bm25_results": [c.model_dump() for c in bm25_candidates[:top_k]],
            "hybrid_results": [c.model_dump() for c in hybrid_results]
        }


# Default singleton instance
_default_hybrid_retriever = HybridRetriever()


def search_hybrid(
    query: str,
    top_k: int = DEFAULT_HYBRID_TOP_K,
    candidate_k: Optional[int] = None,
    filter_dict: Optional[Dict[str, Any]] = None
) -> List[HybridRetrievedChunk]:
    return _default_hybrid_retriever.search(query, top_k=top_k, candidate_k=candidate_k, filter_dict=filter_dict)
