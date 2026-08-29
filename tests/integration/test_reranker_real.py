"""Integration test for real BGE reranker model (Phase 36.14)."""

import os
import pytest
from app.retrieval.mongodb_vector import RetrievedChunk
from app.retrieval.reranker import LocalReranker


@pytest.mark.integration
def test_real_reranker_execution_if_enabled():
    if os.getenv("RUN_MODEL_INTEGRATION", "false").lower() not in ("true", "1"):
        pytest.skip("Skipping real neural reranker model download/inference test. Set RUN_MODEL_INTEGRATION=true to run.")

    reranker = LocalReranker(enabled=True)
    reranker.load_model()
    if reranker._model is None:
        pytest.skip("Local reranker model could not be loaded from HuggingFace.")

    candidates = [
        RetrievedChunk(
            chunk_id="c1",
            document_id="d1",
            title="SEBI Investment Adviser Rules",
            content="Investment Advisers must maintain net worth requirements.",
            source="SEBI",
            url="https://sebi.gov.in/1",
            score=0.7
        ),
        RetrievedChunk(
            chunk_id="c2",
            document_id="d2",
            title="SEBI Mutual Fund Rules",
            content="Mutual funds must comply with NAV calculation guidelines.",
            source="SEBI",
            url="https://sebi.gov.in/2",
            score=0.7
        )
    ]

    results = reranker.rerank("What are the net worth rules for investment advisers?", candidates, top_k=2)
    assert len(results) == 2
    assert results[0].reranker_score is not None
    assert results[0].chunk_id == "c1"
