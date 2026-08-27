import pytest
from unittest.mock import MagicMock

from app.retrieval.mongodb_vector import RetrievedChunk
from app.retrieval.reranker import LocalReranker, RerankedChunk


@pytest.fixture
def sample_candidates():
    return [
        RetrievedChunk(
            chunk_id="chunk_1",
            document_id="doc_1",
            title="SEBI Circular",
            content="Passage about IA qualification.",
            source="SEBI",
            url="https://sebi.gov.in/1",
            score=0.70
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            document_id="doc_2",
            title="SEBI Circular",
            content="Passage about mutual funds.",
            source="SEBI",
            url="https://sebi.gov.in/2",
            score=0.60
        )
    ]


def test_reranker_disabled(sample_candidates):
    reranker = LocalReranker(enabled=False)
    results = reranker.rerank("IA qualification", sample_candidates, top_k=2)

    assert len(results) == 2
    assert results[0].chunk_id == "chunk_1"
    assert results[0].reranker_score is None


def test_reranker_mocked_model(sample_candidates):
    reranker = LocalReranker(enabled=True)
    mock_model = MagicMock()
    # Mock scores giving higher score to chunk_2
    mock_model.predict.return_value = [0.25, 0.95]
    reranker._model = mock_model
    reranker._initialized = True

    results = reranker.rerank("mutual funds", sample_candidates, top_k=2)
    assert len(results) == 2
    assert results[0].chunk_id == "chunk_2"
    assert results[0].reranker_score == 0.95
    assert results[1].chunk_id == "chunk_1"
    assert results[1].reranker_score == 0.25


def test_reranker_empty_candidates():
    reranker = LocalReranker()
    assert reranker.rerank("test", []) == []
    assert reranker.rerank("", []) == []
