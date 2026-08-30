"""
Unit tests for GenerationEvaluator (Phase 42).
"""

import pytest
from evaluation.generation_evaluator import GenerationEvaluator


def test_generation_evaluator_judge_insufficient_evidence():
    evaluator = GenerationEvaluator()
    rel, comp, grd, reason = evaluator._judge_answer(
        question="What are the FDA clinical trial guidelines?",
        evidence_text="",
        answer="I could not find sufficient evidence in the indexed regulatory sources.",
        answerability="UNANSWERABLE"
    )

    assert rel == 5.0
    assert comp == 5.0
    assert grd == 5.0
    assert "without hallucinating" in reason


def test_generation_evaluator_judge_heuristic():
    evaluator = GenerationEvaluator()
    rel, comp, grd, reason = evaluator._judge_answer(
        question="What is the record keeping period for investment advisers?",
        evidence_text="[1] Master Circular: Keep records for 8 years.",
        answer="Investment advisers must keep records for 8 years [1].",
        reference_answer="Keep records for 8 years.",
        answerability="ANSWERABLE"
    )

    assert rel >= 3.0
    assert comp >= 3.0
    assert grd >= 3.0


def test_generation_evaluator_caching(tmp_path):
    evaluator = GenerationEvaluator()
    key = evaluator._compute_cache_key("Q1", "E1", "A1", "R1")
    evaluator._judge_cache[key] = {
        "relevance": 4.8,
        "completeness": 4.6,
        "groundedness": 5.0,
        "reason": "Mock cached test result"
    }

    rel, comp, grd, reason = evaluator._judge_answer("Q1", "E1", "A1", "R1")
    assert rel == 4.8
    assert comp == 4.6
    assert grd == 5.0
    assert reason == "Mock cached test result"
