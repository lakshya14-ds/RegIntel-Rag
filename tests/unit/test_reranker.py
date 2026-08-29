"""Unit tests for LocalReranker module (Phase 36.14)."""

import pytest
from unittest.mock import MagicMock, patch

from app.retrieval.mongodb_vector import RetrievedChunk
from app.retrieval.hybrid import HybridRetrievedChunk
from app.retrieval.reranker import LocalReranker, RerankedChunk


@pytest.fixture
def sample_candidates():
    return [
        RetrievedChunk(
            chunk_id="chunk_1",
            document_id="doc_1",
            title="SEBI Master Circular IA",
            content="Requirements for Investment Advisers qualification and certification.",
            section="Chapter II - Qualifications",
            source="SEBI",
            category="Investment Adviser",
            document_type="Master Circular",
            published_date="2024-05-15",
            effective_date="2024-06-01",
            url="https://sebi.gov.in/ia",
            score=0.75
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            document_id="doc_2",
            title="SEBI Mutual Fund Regulations",
            content="Regulations governing mutual fund overseas investments and limits.",
            section="Chapter IV - Investments",
            source="SEBI",
            category="Mutual Funds",
            document_type="Circular",
            published_date="2023-11-01",
            effective_date="2023-11-15",
            url="https://sebi.gov.in/mf",
            score=0.60
        ),
        HybridRetrievedChunk(
            chunk_id="chunk_3",
            document_id="doc_3",
            title="SEBI Stock Brokers Circular",
            content="Algorithmic trading controls and co-location latency testing requirements.",
            section="Technical Guidelines",
            source="SEBI",
            category="Market Intermediaries",
            document_type="Circular",
            published_date="2024-03-20",
            effective_date="2024-04-01",
            url="https://sebi.gov.in/broker",
            score=0.85,
            vector_score=0.80,
            bm25_score=4.5,
            hybrid_score=0.85,
            retrieval_methods=["vector", "bm25"]
        )
    ]


def test_reranker_disabled(sample_candidates):
    reranker = LocalReranker(enabled=False)
    results = reranker.rerank("IA qualification", sample_candidates, top_k=2)

    assert len(results) == 2
    assert results[0].chunk_id == "chunk_1"
    assert results[0].reranker_score is None


def test_reranker_mocked_model_scoring_and_ordering(sample_candidates):
    reranker = LocalReranker(enabled=True)
    mock_model = MagicMock()
    # Mock scores giving highest score to chunk_2 (mutual funds)
    mock_model.predict.return_value = [1.2, 5.8, -0.5]
    reranker._model = mock_model
    reranker._initialized = True

    results = reranker.rerank("overseas mutual fund limits", sample_candidates, top_k=2)
    assert len(results) == 2
    assert results[0].chunk_id == "chunk_2"
    assert results[0].reranker_score == 5.8
    assert results[0].score == 5.8
    assert results[1].chunk_id == "chunk_1"
    assert results[1].reranker_score == 1.2


def test_reranker_metadata_preservation(sample_candidates):
    reranker = LocalReranker(enabled=True)
    mock_model = MagicMock()
    mock_model.predict.return_value = [2.0, 1.0, 3.0]
    reranker._model = mock_model
    reranker._initialized = True

    results = reranker.rerank("algo trading", sample_candidates, top_k=3)
    assert len(results) == 3
    top = results[0]
    assert top.chunk_id == "chunk_3"
    assert top.category == "Market Intermediaries"
    assert top.section == "Technical Guidelines"
    assert top.retrieval_methods == ["vector", "bm25"]
    assert top.hybrid_score == 0.85
    assert top.reranker_score == 3.0


def test_reranker_empty_and_blank_inputs(sample_candidates):
    reranker = LocalReranker()
    assert reranker.rerank("valid query", []) == []
    assert reranker.rerank("", sample_candidates) == []
    assert reranker.rerank("   ", sample_candidates) == []


def test_reranker_single_candidate(sample_candidates):
    reranker = LocalReranker(enabled=True)
    mock_model = MagicMock()
    mock_model.predict.return_value = [4.5]
    reranker._model = mock_model
    reranker._initialized = True

    results = reranker.rerank("test query", [sample_candidates[0]], top_k=5)
    assert len(results) == 1
    assert results[0].chunk_id == "chunk_1"
    assert results[0].reranker_score == 4.5


def test_reranker_device_detection():
    reranker = LocalReranker(device="cpu")
    assert reranker._determine_device() == "cpu"


def test_reranker_fallback_on_model_none(sample_candidates):
    reranker = LocalReranker(enabled=True)
    reranker._model = None
    reranker._initialized = True

    results = reranker.rerank("test query", sample_candidates, top_k=2)
    assert len(results) == 2
    assert results[0].chunk_id == "chunk_1"
