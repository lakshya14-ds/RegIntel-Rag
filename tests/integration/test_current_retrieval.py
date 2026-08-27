import pytest
from app.config import settings
from app.rag.pipeline import RAGPipeline, RAGResponse
from app.retrieval.query_analyzer import QueryAnalyzer, QueryIntent


def test_integration_current_retrieval_query_understanding():
    pipeline = RAGPipeline(retrieval_mode="hybrid", enable_reranker=False)
    query = "What are the latest SEBI requirements for investment advisers?"

    intent = QueryAnalyzer.analyze(query)
    assert intent.source == "SEBI"
    assert intent.category == "Investment Adviser"
    assert intent.time_intent == "latest"

    # Test candidate retrieval with metadata intent
    candidates = pipeline.retrieve_candidates(query, query_intent=intent)
    assert len(candidates) > 0
    # Top chunk should belong to Investment Adviser
    assert any(c.category == "Investment Adviser" for c in candidates)
