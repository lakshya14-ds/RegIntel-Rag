import pytest
from evaluation.generation_evaluator import GenerationEvaluator


def test_generation_evaluator_judge_insufficient_evidence():
    evaluator = GenerationEvaluator()
    rel, grd, cit, reason = evaluator._judge_answer(
        question="What are the FDA clinical trial guidelines?",
        evidence_text="",
        answer="I could not find sufficient evidence in the indexed regulatory sources."
    )

    assert rel == 5.0
    assert grd == 5.0
    assert cit == 5.0
    assert "without hallucinating" in reason


def test_generation_evaluator_judge_heuristic():
    evaluator = GenerationEvaluator()
    rel, grd, cit, reason = evaluator._judge_answer(
        question="What is the record keeping period for investment advisers?",
        evidence_text="[1] Master Circular: Keep records for 8 years.",
        answer="Investment advisers must keep records for 8 years [1]."
    )

    assert rel >= 3.0
    assert grd >= 3.0
    assert cit >= 3.0
