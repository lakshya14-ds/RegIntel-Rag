"""Integration tests for RAG pipeline with neural cross-encoder reranking (Phase 37.12)."""

import pytest
from unittest.mock import MagicMock, patch

from app.rag.pipeline import RAGPipeline, RAGResponse
from app.retrieval.mongodb_vector import RetrievedChunk
from app.retrieval.hybrid import HybridRetrievedChunk
from app.retrieval.reranker import LocalReranker, RerankedChunk
from app.retrieval.query_analyzer import QueryIntent


@pytest.fixture
def mock_candidates():
    return [
        HybridRetrievedChunk(
            chunk_id=f"chunk_{i}",
            document_id=f"doc_{i}",
            title=f"Regulatory Document {i}",
            content=f"Substantive regulatory requirements and guidelines content for chunk {i}.",
            section=f"Section {i}",
            source="SEBI",
            category="Investment Adviser",
            document_type="Circular",
            published_date="2024-05-01",
            effective_date="2024-06-01",
            url=f"https://sebi.gov.in/{i}",
            score=0.90 - (i * 0.05),
            vector_score=0.85 - (i * 0.05),
            bm25_score=5.0 - (i * 0.2),
            hybrid_score=0.90 - (i * 0.05),
            retrieval_methods=["vector", "bm25"]
        )
        for i in range(10)
    ]


def test_rag_pipeline_with_reranker_enabled(mock_candidates):
    # Setup mock reranker that boosts chunk_7 to the very top
    mock_reranker = LocalReranker(enabled=True)
    mock_model = MagicMock()
    # 10 scores where index 7 is highest
    mock_scores = [1.0, 2.0, 1.5, 0.5, 2.2, 1.8, 0.9, 8.5, 1.1, 0.4]
    mock_model.predict.return_value = mock_scores
    mock_reranker._model = mock_model
    mock_reranker._initialized = True

    mock_generator = MagicMock()
    mock_generator.generate_answer.return_value = {
        "answer": "According to the requirements, investment advisers must comply with guidelines [1].",
        "sources": [
            {
                "source_id": 1,
                "chunk_id": "chunk_7",
                "document_id": "doc_7",
                "title": "Regulatory Document 7",
                "section": "Section 7",
                "source": "SEBI",
                "published_date": "2024-05-01",
                "effective_date": "2024-06-01",
                "url": "https://sebi.gov.in/7",
                "score": 8.5
            }
        ]
    }

    mock_hybrid = MagicMock()
    mock_hybrid.search.return_value = mock_candidates

    pipeline = RAGPipeline(
        hybrid_retriever=mock_hybrid,
        reranker=mock_reranker,
        generator=mock_generator,
        enable_reranker=True,
        top_k=5
    )

    resp: RAGResponse = pipeline.answer("What are investment adviser requirements?", enable_reranker=True)

    assert resp.sufficient_evidence is True
    assert resp.reranker_used is True
    assert resp.retrieved_chunks_count == 5
    assert len(resp.sources) == 1
    assert resp.sources[0].chunk_id == "chunk_7"
    assert resp.sources[0].source_id == 1

    # Verify generator received only the top 5 reranked chunks
    call_args = mock_generator.generate_answer.call_args
    passed_chunks = call_args[1]["retrieved_chunks"]
    assert len(passed_chunks) == 5
    assert passed_chunks[0].chunk_id == "chunk_7"


def test_rag_pipeline_with_reranker_disabled(mock_candidates):
    mock_generator = MagicMock()
    mock_generator.generate_answer.return_value = {
        "answer": "Grounded answer [1].",
        "sources": [
            {
                "source_id": 1,
                "chunk_id": "chunk_0",
                "document_id": "doc_0",
                "title": "Regulatory Document 0",
                "section": "Section 0",
                "source": "SEBI",
                "published_date": "2024-05-01",
                "effective_date": "2024-06-01",
                "url": "https://sebi.gov.in/0",
                "score": 0.90
            }
        ]
    }

    mock_hybrid = MagicMock()
    mock_hybrid.search.return_value = mock_candidates

    pipeline = RAGPipeline(
        hybrid_retriever=mock_hybrid,
        generator=mock_generator,
        enable_reranker=False,
        top_k=5
    )

    resp: RAGResponse = pipeline.answer("What are investment adviser requirements?", enable_reranker=False)

    assert resp.sufficient_evidence is True
    assert resp.reranker_used is False
    assert resp.retrieved_chunks_count == 5
    # Passed chunks should be top 5 from candidate list unchanged
    passed_chunks = mock_generator.generate_answer.call_args[1]["retrieved_chunks"]
    assert len(passed_chunks) == 5
    assert passed_chunks[0].chunk_id == "chunk_0"


def test_rag_pipeline_empty_retrieval():
    mock_hybrid = MagicMock()
    mock_hybrid.search.return_value = []

    mock_generator = MagicMock()

    pipeline = RAGPipeline(
        hybrid_retriever=mock_hybrid,
        generator=mock_generator,
        enable_reranker=True
    )

    resp = pipeline.answer("Unknown regulation topic?")
    assert resp.sufficient_evidence is False
    assert resp.retrieved_chunks_count == 0
    assert not mock_generator.generate_answer.called
