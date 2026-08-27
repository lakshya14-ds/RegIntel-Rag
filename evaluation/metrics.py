"""
Evaluation Metrics for Retrieval and Generation Performance.

Implements standard information retrieval metrics:
- Recall@K
- Mean Reciprocal Rank (MRR)
- Precision@K
- Citation Integrity Rate
"""

from typing import List, Set, Any


def compute_recall_at_k(retrieved_ids: List[str], expected_ids: List[str], k: int) -> float:
    """
    Returns 1.0 if at least one expected ID appears in top k retrieved IDs, else 0.0.
    Handles matching against either chunk_id or document_id.
    """
    if not expected_ids or not retrieved_ids:
        return 0.0

    top_k_retrieved = set(retrieved_ids[:k])
    expected_set = set(expected_ids)

    # Check if any expected ID matches directly or is a substring (e.g. doc_id in chunk_id)
    for ret_id in top_k_retrieved:
        if ret_id in expected_set:
            return 1.0
        for exp_id in expected_set:
            if exp_id in ret_id or ret_id in exp_id:
                return 1.0

    return 0.0


def compute_reciprocal_rank(retrieved_ids: List[str], expected_ids: List[str]) -> float:
    """
    Computes 1 / rank of the first relevant retrieved result (1-indexed).
    Returns 0.0 if no relevant result is retrieved.
    """
    if not expected_ids or not retrieved_ids:
        return 0.0

    expected_set = set(expected_ids)

    for rank, ret_id in enumerate(retrieved_ids, start=1):
        if ret_id in expected_set:
            return 1.0 / rank
        for exp_id in expected_set:
            if exp_id in ret_id or ret_id in exp_id:
                return 1.0 / rank

    return 0.0


def compute_precision_at_k(retrieved_ids: List[str], expected_ids: List[str], k: int) -> float:
    """
    Computes fraction of top k retrieved items that are relevant.
    """
    if not expected_ids or not retrieved_ids or k <= 0:
        return 0.0

    top_k = retrieved_ids[:k]
    expected_set = set(expected_ids)

    hits = 0
    for ret_id in top_k:
        if ret_id in expected_set:
            hits += 1
        elif any(exp_id in ret_id or ret_id in exp_id for exp_id in expected_set):
            hits += 1

    return hits / float(k)


def compute_citation_integrity(valid_count: int, total_count: int) -> float:
    """Computes citation integrity percentage (0.0 - 100.0)."""
    if total_count <= 0:
        return 100.0
    return round((valid_count / float(total_count)) * 100.0, 2)
