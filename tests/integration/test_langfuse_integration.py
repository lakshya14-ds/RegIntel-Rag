"""
Integration Tests for Langfuse Tracing (Phase 50).

Gated by environment flag: RUN_LANGFUSE_INTEGRATION=true.
"""

import os
import pytest
from app.rag.pipeline import RAGPipeline
from app.observability.langfuse_tracer import langfuse_tracer


@pytest.mark.skipif(
    os.getenv("RUN_LANGFUSE_INTEGRATION", "false").lower() not in ("true", "1"),
    reason="Live Langfuse integration disabled. Set RUN_LANGFUSE_INTEGRATION=true to enable."
)
def test_live_langfuse_rag_trace():
    if not langfuse_tracer.is_active:
        pytest.skip("Langfuse client is not active or unconfigured.")

    pipeline = RAGPipeline(enable_reranker=False)
    res = pipeline.ask(
        "What are the record keeping requirements for Investment Advisers?",
        request_id="int-test-req-01"
    )

    assert res.question != ""
    assert res.sufficient_evidence is True

    # Flush pending telemetry
    langfuse_tracer.flush()
