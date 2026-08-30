"""
Unit tests for FailureAnalyzer and QualityGate (Phase 44).
"""

import pytest
from evaluation.failure_analyzer import FailureAnalyzer, QualityGateConfig, QualityGateResult


def test_failure_analyzer_abstention_failure():
    analyzer = FailureAnalyzer()
    gen_result = {
        "id": "Q_UNANS_FAIL",
        "question": "What are the FDA medical guidelines?",
        "answerability": "UNANSWERABLE",
        "generated_answer": "The FDA mandates clinical trial phase 3 results within 180 days.",
        "scores": {"relevance": 5.0}
    }

    diag = analyzer.diagnose_query(gen_result)
    assert diag is not None
    assert diag["failure_stage"] == "generation"
    assert diag["failure_type"] == "poor_abstention"


def test_failure_analyzer_retrieval_failure():
    analyzer = FailureAnalyzer()
    gen_result = {
        "id": "Q_ANS_FAIL",
        "question": "What is the fee limit for investment advisers?",
        "answerability": "ANSWERABLE",
        "expected_sources": ["doc_123"],
        "generated_answer": "I could not find sufficient evidence in the indexed regulatory sources.",
        "scores": {"relevance": 1.0}
    }

    diag = analyzer.diagnose_query(gen_result)
    assert diag is not None
    assert diag["failure_stage"] == "retrieval"
    assert diag["failure_type"] == "missing_relevant_document"


def test_failure_analyzer_reranking_failure():
    analyzer = FailureAnalyzer()
    gen_result = {
        "id": "Q_RERANK_FAIL",
        "question": "What are the KYC norms for stock brokers?",
        "answerability": "ANSWERABLE",
        "expected_sources": ["doc_broker_kyc"],
        "generated_answer": "Brokers follow general market guidelines.",
        "scores": {"relevance": 3.0}
    }

    diag = analyzer.diagnose_query(
        gen_result,
        retrieval_candidate_ids=["doc_broker_kyc_chunk_1", "other_chunk"],
        top_k_ids=["other_chunk", "unrelated_chunk"]
    )
    assert diag is not None
    assert diag["failure_stage"] == "reranking"
    assert diag["failure_type"] == "relevant_chunk_demoted"


def test_quality_gate_evaluation():
    analyzer = FailureAnalyzer(QualityGateConfig(
        min_recall_at_5=0.20,
        min_grounded_claim_rate=80.0,
        min_citation_integrity=95.0,
        min_safe_abstention_rate=80.0
    ))

    # Passing summary
    qg_pass = analyzer.evaluate_quality_gate(
        retrieval_summary={"metrics": {"recall_at_5": 0.60}},
        generation_summary={"metrics": {"average_citation_integrity": 100.0, "safe_abstention_rate": 100.0}},
        grounding_summary={"grounding_metrics": {"grounded_claim_rate": 90.0, "safe_abstention_rate": 100.0}, "citation_metrics": {"citation_integrity": 100.0}}
    )
    assert qg_pass.status == "PASS"

    # Failing summary
    qg_fail = analyzer.evaluate_quality_gate(
        retrieval_summary={"metrics": {"recall_at_5": 0.05}},
        generation_summary={"metrics": {"average_citation_integrity": 70.0, "safe_abstention_rate": 50.0}},
        grounding_summary={"grounding_metrics": {"grounded_claim_rate": 50.0, "safe_abstention_rate": 50.0}, "citation_metrics": {"citation_integrity": 70.0}}
    )
    assert qg_fail.status == "FAIL"
