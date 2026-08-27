import pytest
from evaluation.metrics import (
    compute_recall_at_k,
    compute_reciprocal_rank,
    compute_precision_at_k,
    compute_citation_integrity
)


def test_compute_recall_at_k():
    retrieved = ["doc_1", "doc_2", "doc_3", "doc_4"]
    expected = ["doc_3"]

    assert compute_recall_at_k(retrieved, expected, k=2) == 0.0
    assert compute_recall_at_k(retrieved, expected, k=3) == 1.0
    assert compute_recall_at_k(retrieved, expected, k=10) == 1.0
    assert compute_recall_at_k([], expected, k=5) == 0.0
    assert compute_recall_at_k(retrieved, [], k=5) == 0.0


def test_compute_reciprocal_rank():
    retrieved = ["doc_a", "doc_b", "doc_c"]
    assert compute_reciprocal_rank(retrieved, ["doc_a"]) == 1.0
    assert compute_reciprocal_rank(retrieved, ["doc_b"]) == 0.5
    assert compute_reciprocal_rank(retrieved, ["doc_c"]) == 1.0 / 3.0
    assert compute_reciprocal_rank(retrieved, ["doc_z"]) == 0.0


def test_compute_precision_at_k():
    retrieved = ["doc_1", "doc_2", "doc_3", "doc_4"]
    expected = ["doc_1", "doc_3"]

    assert compute_precision_at_k(retrieved, expected, k=2) == 0.5   # 1/2
    assert compute_precision_at_k(retrieved, expected, k=4) == 0.5   # 2/4


def test_compute_citation_integrity():
    assert compute_citation_integrity(48, 50) == 96.0
    assert compute_citation_integrity(0, 0) == 100.0
    assert compute_citation_integrity(10, 10) == 100.0
