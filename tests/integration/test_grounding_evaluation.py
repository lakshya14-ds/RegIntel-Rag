"""
Integration tests for Grounding and Citation Evaluation Pipeline (Phase 43).
"""

import os
import pytest
from evaluation.grounding_evaluator import GroundingEvaluator


@pytest.mark.skipif(
    os.getenv("RUN_GEMINI_INTEGRATION", "false").lower() not in ("true", "1") or os.getenv("GEMINI_API_KEY") in (None, "", "mock_test_key"),
    reason="Live Gemini integration test disabled. Set RUN_GEMINI_INTEGRATION=true."
)
def test_integration_grounding_evaluator_subset():
    evaluator = GroundingEvaluator(enable_cache=True)
    with open(evaluator.dataset_path, "r", encoding="utf-8") as f:
        import json
        dataset = json.load(f)

    sample_queries = [
        q for q in dataset if q.get("answerability") == "ANSWERABLE"
    ][:1] + [
        q for q in dataset if q.get("answerability") == "UNANSWERABLE"
    ][:1]

    for item in sample_queries:
        result = evaluator.evaluate_query(item)
        assert result is not None
        assert "grounded_claim_rate" in result
        assert "citation_integrity" in result
        assert 0.0 <= result["grounded_claim_rate"] <= 100.0
        assert 0.0 <= result["citation_integrity"] <= 100.0
