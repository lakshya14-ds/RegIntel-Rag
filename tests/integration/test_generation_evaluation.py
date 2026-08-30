"""
Integration tests for Generation Evaluation Pipeline (Phase 42).
"""

import os
import pytest
from evaluation.generation_evaluator import GenerationEvaluator


@pytest.mark.skipif(
    os.getenv("RUN_GEMINI_INTEGRATION", "false").lower() not in ("true", "1") or os.getenv("GEMINI_API_KEY") in (None, "", "mock_test_key"),
    reason="Live Gemini integration test disabled. Set RUN_GEMINI_INTEGRATION=true."
)
def test_integration_generation_evaluator_subset():
    evaluator = GenerationEvaluator(enable_cache=True)
    dataset = evaluator.load_dataset()
    assert len(dataset) >= 5

    # Run on a sample of 2 questions (1 answerable, 1 unanswerable)
    sample_queries = [
        q for q in dataset if q.get("answerability") == "ANSWERABLE"
    ][:1] + [
        q for q in dataset if q.get("answerability") == "UNANSWERABLE"
    ][:1]

    for item in sample_queries:
        result = evaluator.evaluate_item(item)
        assert result is not None
        assert "scores" in result
        assert "latencies_ms" in result
        assert result["scores"]["relevance"] >= 1.0
        assert result["latencies_ms"]["total"] > 0.0
