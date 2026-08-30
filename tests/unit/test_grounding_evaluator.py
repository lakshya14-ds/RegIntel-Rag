"""
Unit tests for GroundingEvaluator (Phase 43).
"""

import pytest
from unittest.mock import MagicMock
from app.rag.pipeline import RAGResponse
from evaluation.grounding_evaluator import GroundingEvaluator


def test_grounding_claim_extraction_filtering():
    evaluator = GroundingEvaluator()
    answer = "Based on the provided documents, Investment Advisers must maintain records for 8 years [1]. In addition, compliance audits are required every 6 months [2]. Thank you."
    claims = evaluator.extract_claims(answer)

    assert len(claims) >= 2
    # Ensure disclaimers were filtered out
    assert not any(c.lower() == "thank you." for c in claims)


def test_grounding_evaluation_deterministic_overlap():
    evaluator = GroundingEvaluator()
    question = "What is the record keeping period for investment advisers?"
    evidence = "[1] Master Circular: Investment advisers must maintain books and records for a minimum period of 8 years."
    claims = [
        "Investment advisers must maintain records for 8 years [1].",
        "Investment advisers must pay an annual tax of 50 percent."
    ]

    results = evaluator.evaluate_grounding_for_claims(question, evidence, claims)
    assert len(results) == 2
    assert results[0]["classification"] in ("SUPPORTED", "PARTIALLY_SUPPORTED")
    assert results[1]["classification"] == "UNSUPPORTED"


def test_grounding_evaluator_unanswerable_refusal():
    mock_pipeline = MagicMock()
    mock_pipeline.answer.return_value = RAGResponse(
        question="What is the FDA regulation on medical devices in USA?",
        answer="I could not find sufficient evidence in the indexed regulatory sources.",
        sources=[],
        retrieved_chunks_count=0,
        top_score=0.0,
        retrieval_mode="hybrid",
        reranker_used=False
    )

    evaluator = GroundingEvaluator(pipeline=mock_pipeline)
    res = evaluator.evaluate_query({
        "id": "Q_UNANS",
        "question": "What is the FDA regulation on medical devices in USA?",
        "answerability": "UNANSWERABLE"
    })

    assert res["is_refusal"] is True
    assert res["safe_abstention"] is True
    assert res["grounded_claim_rate"] == 100.0
    assert res["unsupported_claim_rate"] == 0.0
