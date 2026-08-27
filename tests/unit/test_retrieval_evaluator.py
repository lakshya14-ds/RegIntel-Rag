import pytest
from evaluation.retrieval_evaluator import RetrievalEvaluator


def test_retrieval_evaluator_method():
    evaluator = RetrievalEvaluator(enable_reranker=False)
    sample_queries = [
        {
            "id": "T001",
            "question": "What are the requirements for investment advisers?",
            "expected_documents": ["69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8"],
            "category": "factual"
        }
    ]

    res = evaluator.evaluate_method("hybrid", sample_queries, max_k=5)
    assert "recall_at_5" in res
    assert "mrr" in res
    assert res["queries_count"] == 1
    assert len(res["results"]) == 1
