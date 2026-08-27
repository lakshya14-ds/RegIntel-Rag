import pytest
from unittest.mock import MagicMock

from app.retrieval.mongodb_vector import RetrievedChunk
from app.retrieval.hybrid import HybridRetriever, HybridRetrievedChunk


@pytest.fixture
def mock_vector_results():
    return [
        RetrievedChunk(
            chunk_id="chunk_A",
            document_id="doc_1",
            title="IA Circular",
            content="Vector content A",
            source="SEBI",
            url="https://sebi.gov.in/a",
            score=0.85
        ),
        RetrievedChunk(
            chunk_id="chunk_B",
            document_id="doc_1",
            title="IA Circular",
            content="Vector content B",
            source="SEBI",
            url="https://sebi.gov.in/b",
            score=0.72
        )
    ]


@pytest.fixture
def mock_bm25_results():
    return [
        RetrievedChunk(
            chunk_id="chunk_A",
            document_id="doc_1",
            title="IA Circular",
            content="BM25 content A",
            source="SEBI",
            url="https://sebi.gov.in/a",
            score=5.4
        ),
        RetrievedChunk(
            chunk_id="chunk_C",
            document_id="doc_2",
            title="MF Circular",
            content="BM25 content C",
            source="SEBI",
            url="https://sebi.gov.in/c",
            score=3.1
        )
    ]


def test_hybrid_rrf_fusion(mock_vector_results, mock_bm25_results):
    mock_vec = MagicMock()
    mock_vec.retrieve.return_value = mock_vector_results
    mock_bm25 = MagicMock()
    mock_bm25.search.return_value = mock_bm25_results

    hybrid = HybridRetriever(
        vector_retriever=mock_vec,
        bm25_retriever=mock_bm25,
        fusion_method="rrf",
        vector_weight=0.6,
        bm25_weight=0.4
    )

    results = hybrid.search("test query", top_k=5)
    assert len(results) == 3

    # chunk_A appeared in both -> should have highest fused score and both retrieval methods
    assert results[0].chunk_id == "chunk_A"
    assert "vector" in results[0].retrieval_methods
    assert "bm25" in results[0].retrieval_methods
    assert results[0].vector_score == 0.85
    assert results[0].bm25_score == 5.4


def test_hybrid_min_max_fusion(mock_vector_results, mock_bm25_results):
    mock_vec = MagicMock()
    mock_vec.retrieve.return_value = mock_vector_results
    mock_bm25 = MagicMock()
    mock_bm25.search.return_value = mock_bm25_results

    hybrid = HybridRetriever(
        vector_retriever=mock_vec,
        bm25_retriever=mock_bm25,
        fusion_method="min_max",
        vector_weight=0.6,
        bm25_weight=0.4
    )

    results = hybrid.search("test query", top_k=5)
    assert len(results) == 3
    assert results[0].chunk_id == "chunk_A"
    assert results[0].hybrid_score <= 1.0
