"""
Evaluation Metrics for Retrieval, Generation, Grounding, and Citation Performance.

Implements standard RAG evaluation metrics:
- Recall@K, Mean Reciprocal Rank (MRR), Precision@K
- Citation Integrity Rate, Citation Support Rate, Citation Coverage Rate
- Grounded Claim Rate, Unsupported Claim Rate
- Safe Abstention Rate, Answerability Handling Rate
"""

from typing import List, Set, Any, Dict, Optional


def compute_recall_at_k(retrieved_ids: List[str], expected_ids: List[str], k: int) -> float:
    """
    Returns 1.0 if at least one expected ID appears in top k retrieved IDs, else 0.0.
    Handles matching against either chunk_id or document_id.
    """
    if not expected_ids or not retrieved_ids:
        return 0.0

    top_k_retrieved = set(retrieved_ids[:k])
    expected_set = set(expected_ids)

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
    """Computes fraction of top k retrieved items that are relevant."""
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


def compute_citation_support_rate(supported_count: int, total_cited_claims: int) -> float:
    """Computes percentage of cited substantive claims that are verified as supported by evidence."""
    if total_cited_claims <= 0:
        return 100.0
    return round((supported_count / float(total_cited_claims)) * 100.0, 2)


def compute_citation_coverage_rate(cited_claims_count: int, total_substantive_claims: int) -> float:
    """Computes percentage of substantive claims that contain citations."""
    if total_substantive_claims <= 0:
        return 100.0
    return round((cited_claims_count / float(total_substantive_claims)) * 100.0, 2)


def compute_grounded_claim_rate(supported_claims: int, total_claims: int) -> float:
    """Computes percentage of substantive claims supported by retrieved evidence."""
    if total_claims <= 0:
        return 100.0
    return round((supported_claims / float(total_claims)) * 100.0, 2)


def compute_unsupported_claim_rate(unsupported_claims: int, total_claims: int) -> float:
    """Computes percentage of substantive claims not supported by retrieved evidence."""
    if total_claims <= 0:
        return 0.0
    return round((unsupported_claims / float(total_claims)) * 100.0, 2)


def compute_safe_abstention_rate(correctly_abstained: int, total_unanswerable: int) -> float:
    """Computes percentage of unanswerable questions where the system correctly abstains."""
    if total_unanswerable <= 0:
        return 100.0
    return round((correctly_abstained / float(total_unanswerable)) * 100.0, 2)


def compute_answerability_handling_rate(correct_handling_count: int, total_eval_queries: int) -> float:
    """Computes percentage of evaluation queries handled appropriately according to their answerability class."""
    if total_eval_queries <= 0:
        return 100.0
    return round((correct_handling_count / float(total_eval_queries)) * 100.0, 2)
