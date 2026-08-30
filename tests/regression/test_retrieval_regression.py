"""
Retrieval Regression Tests (Phase 51.15).

Verifies ranking consistency, score monotonicity, and baseline Recall / MRR metrics.
"""

import pytest
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.mongodb_vector import RetrievedChunk
from evaluation.metrics import compute_recall_at_k, compute_reciprocal_rank


def test_rrf_monotonicity():
    # RRF rank 1 must score higher than rank 2
    retriever = HybridRetriever(rrf_k=60, vector_weight=0.6, bm25_weight=0.4)

    c1 = RetrievedChunk(chunk_id="c1", document_id="d1", title="T1", content="Text 1", score=0.9, source="SEBI", published_date="2024-01-01", url="")
    c2 = RetrievedChunk(chunk_id="c2", document_id="d2", title="T2", content="Text 2", score=0.8, source="SEBI", published_date="2024-01-01", url="")

    fused = retriever._fuse_rrf(vector_results=[c1, c2], bm25_results=[c1, c2])

    assert len(fused) == 2
    assert fused[0].chunk_id == "c1"
    assert fused[0].hybrid_score > fused[1].hybrid_score


def test_retrieval_metrics_baseline():
    # Synthetic ground truth test
    retrieved_chunk_ids = ["chk_1", "chk_2", "chk_3", "chk_4", "chk_5"]
    relevant_ids = ["chk_2"]

    recall_at_5 = compute_recall_at_k(retrieved_chunk_ids, relevant_ids, k=5)
    mrr = compute_reciprocal_rank(retrieved_chunk_ids, relevant_ids)

    assert recall_at_5 == 1.0
    assert mrr == 0.5  # Rank 2 = 1/2
