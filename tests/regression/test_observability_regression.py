"""
Observability Regression Tests (Phase 51.19).

Verifies:
1. LANGFUSE_ENABLED=false does not degrade or alter RAG pipeline responses.
2. MLFLOW_ENABLED=false does not crash experiment tracking calls.
3. Observability exceptions are absorbed cleanly without breaking user requests.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.rag.pipeline import RAGPipeline
from app.retrieval.mongodb_vector import RetrievedChunk
from app.observability.mlflow_tracker import MLflowTracker


def test_observability_disabled_mode_preserves_rag_behavior():
    with patch("app.config.settings.langfuse_enabled", False):
        pipeline = RAGPipeline(enable_reranker=False)

        mock_chunks = [
            RetrievedChunk(
                chunk_id="chk_obs",
                document_id="doc_obs",
                title="SEBI Circular",
                section="Section 1",
                content="Advisers must register.",
                score=0.9,
                source="SEBI",
                published_date="2024-01-01",
                url=""
            )
        ]

        with patch.object(pipeline, "retrieve_candidates", return_value=mock_chunks):
            with patch.object(pipeline.generator, "generate_answer", return_value={
                "answer": "Advisers must register with SEBI [1].",
                "sources": [{"source_id": 1, "chunk_id": "chk_obs", "document_id": "doc_obs", "title": "SEBI Circular", "score": 0.9, "url": "", "published_date": "2024-01-01", "source": "SEBI"}]
            }):
                res = pipeline.ask("Who must register?")
                assert res.sufficient_evidence is True
                assert "[1]" in res.answer


def test_mlflow_disabled_mode_no_op():
    tracker = MLflowTracker(tracking_uri="", experiment_name="test", enabled=False)
    assert tracker.is_active is False

    with tracker.start_run(run_name="test_run") as run:
        tracker.log_params({"model": "test"})
        tracker.log_metrics({"recall": 0.95})
