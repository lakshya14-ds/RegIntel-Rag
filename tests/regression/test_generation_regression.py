"""
Generation & Abstention Regression Tests (Phase 51.16).

Verifies:
1. Answerable questions return grounded answer and sources.
2. Unanswerable questions return clean abstention without hallucinating sources.
3. Empty question inputs return validation guidance.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.rag.pipeline import RAGPipeline
from app.retrieval.mongodb_vector import RetrievedChunk


def test_generation_answerable_query():
    pipeline = RAGPipeline(enable_reranker=False)

    mock_chunks = [
        RetrievedChunk(
            chunk_id="chk_ia_1",
            document_id="doc_ia",
            title="SEBI Rules",
            section="Registration",
            content="Eligibility criteria requires capital adequacy of 50 Lakhs.",
            score=0.95,
            source="SEBI",
            published_date="2024-01-01",
            url=""
        )
    ]

    with patch.object(pipeline, "retrieve_candidates", return_value=mock_chunks):
        with patch.object(pipeline.generator, "generate_answer", return_value={
            "answer": "The net worth requirement is 50 Lakhs [1].",
            "sources": [{"source_id": 1, "chunk_id": "chk_ia_1", "document_id": "doc_ia", "title": "SEBI Rules", "score": 0.95, "url": "", "published_date": "2024-01-01", "source": "SEBI"}],
            "provider": "gemini",
            "model": "gemini-1.5-flash"
        }):
            res = pipeline.ask("What is the net worth requirement?")
            assert res.sufficient_evidence is True
            assert "[1]" in res.answer
            assert len(res.sources) == 1


def test_generation_abstention_on_zero_evidence():
    pipeline = RAGPipeline(enable_reranker=False)

    with patch.object(pipeline, "retrieve_candidates", return_value=[]):
        res = pipeline.ask("What are the cryptocurrency regulations for planetary mining?")
        assert res.sufficient_evidence is False
        assert "not find sufficient evidence" in res.answer.lower()
        assert len(res.sources) == 0


def test_generation_abstention_on_empty_input():
    pipeline = RAGPipeline(enable_reranker=False)
    res = pipeline.ask("   ")
    assert res.sufficient_evidence is False
    assert "empty" in res.answer.lower()
