import math
import pytest
from unittest.mock import MagicMock

from app.retrieval.mongodb_vector import (
    RetrievedChunk,
    MongoDBVectorRetriever,
    compute_cosine_similarity,
    VECTOR_INDEX_NAME
)


def test_retrieved_chunk_model():
    chunk = RetrievedChunk(
        chunk_id="chk_001",
        document_id="doc_001",
        title="SEBI Master Circular",
        content="Section 4 details.",
        section="4. Eligibility",
        source="SEBI",
        category="Investment Adviser",
        published_date="2024-05-24",
        url="https://sebi.gov.in/circ.html",
        score=0.8842
    )
    assert chunk.chunk_id == "chk_001"
    assert chunk.score == 0.8842
    assert chunk.category == "Investment Adviser"


def test_compute_cosine_similarity():
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [1.0, 0.0, 0.0]
    assert pytest.approx(compute_cosine_similarity(vec_a, vec_b)) == 1.0

    vec_c = [0.0, 1.0, 0.0]
    assert pytest.approx(compute_cosine_similarity(vec_a, vec_c)) == 0.0

    # Opposite
    vec_d = [-1.0, 0.0, 0.0]
    assert pytest.approx(compute_cosine_similarity(vec_a, vec_d)) == -1.0


def test_retriever_query_vector_validation():
    retriever = MongoDBVectorRetriever()
    
    # Invalid dimensionality (512 instead of 768)
    with pytest.raises(ValueError, match="768 dimensions"):
        retriever.search([0.1] * 512)


def test_retriever_search_live_or_fallback():
    retriever = MongoDBVectorRetriever(default_top_k=3)
    query_vec = [1.0 / math.sqrt(768)] * 768

    results = retriever.search(query_vec, limit=3)
    assert isinstance(results, list)
    if results:
        assert len(results) <= 3
        for r in results:
            assert isinstance(r, RetrievedChunk)
            assert r.score >= -1.0
            assert r.score <= 1.0
