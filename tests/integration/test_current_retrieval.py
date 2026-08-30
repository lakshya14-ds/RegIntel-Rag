from unittest.mock import patch
import pytest
from app.config import settings
from app.rag.pipeline import RAGPipeline, RAGResponse
from app.retrieval.query_analyzer import QueryAnalyzer, QueryIntent
from app.retrieval.mongodb_vector import RetrievedChunk


def test_integration_current_retrieval_query_understanding():
    pipeline = RAGPipeline(retrieval_mode="hybrid", enable_reranker=False)
    query = "What are the latest SEBI requirements for investment advisers?"

    intent = QueryAnalyzer.analyze(query)
    assert intent.source == "SEBI"
    assert intent.category == "Investment Adviser"
    assert intent.time_intent == "latest"

    # Test candidate retrieval with metadata intent
    mock_candidates = [
        RetrievedChunk(
            chunk_id="chunk_ia_1",
            document_id="doc_ia_1",
            title="SEBI Master Circular for Investment Advisers",
            section="Qualifications",
            content="Investment advisers must hold NISM certification.",
            score=0.92,
            source="SEBI",
            category="Investment Adviser",
            published_date="2024-05-24",
            url="https://sebi.gov.in/ia.html"
        )
    ]
    with patch.object(pipeline, "retrieve_candidates", return_value=mock_candidates):
        candidates = pipeline.retrieve_candidates(query, query_intent=intent)
        assert len(candidates) > 0
        # Top chunk should belong to Investment Adviser
        assert any(c.category == "Investment Adviser" for c in candidates)
