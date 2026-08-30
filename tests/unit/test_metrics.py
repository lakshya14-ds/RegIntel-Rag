"""
Unit tests for retrieval, generation, grounding, and citation metrics.
"""

import pytest
from evaluation.metrics import (
    compute_recall_at_k,
    compute_reciprocal_rank,
    compute_precision_at_k,
    compute_citation_integrity,
    compute_citation_support_rate,
    compute_citation_coverage_rate,
    compute_grounded_claim_rate,
    compute_unsupported_claim_rate,
    compute_safe_abstention_rate,
    compute_answerability_handling_rate
)


def test_retrieval_metrics():
    retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
    expected = ["doc3"]

    assert compute_recall_at_k(retrieved, expected, k=5) == 1.0
    assert compute_recall_at_k(retrieved, expected, k=2) == 0.0
    assert compute_reciprocal_rank(retrieved, expected) == 1.0 / 3.0
    assert compute_precision_at_k(retrieved, expected, k=5) == 0.2


def test_citation_metrics():
    assert compute_citation_integrity(valid_count=5, total_count=5) == 100.0
    assert compute_citation_integrity(valid_count=4, total_count=5) == 80.0
    assert compute_citation_integrity(valid_count=0, total_count=0) == 100.0

    assert compute_citation_support_rate(supported_count=4, total_cited_claims=5) == 80.0
    assert compute_citation_coverage_rate(cited_claims_count=8, total_substantive_claims=10) == 80.0


def test_grounding_and_abstention_metrics():
    assert compute_grounded_claim_rate(supported_claims=9, total_claims=10) == 90.0
    assert compute_unsupported_claim_rate(unsupported_claims=1, total_claims=10) == 10.0
    assert compute_safe_abstention_rate(correctly_abstained=5, total_unanswerable=5) == 100.0
    assert compute_safe_abstention_rate(correctly_abstained=4, total_unanswerable=5) == 80.0
    assert compute_answerability_handling_rate(correct_handling_count=28, total_eval_queries=30) == 93.33
