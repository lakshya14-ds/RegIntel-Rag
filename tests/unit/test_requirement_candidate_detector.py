"""
Unit tests for Requirement Candidate Detection (Phase 61.3).
"""

import pytest
from app.compliance.candidate_detector import (
    detect_candidate_requirements_in_text,
    is_noise_statement,
    split_into_sentences,
)


def test_detect_mandatory_shall():
    text = "The registered investment adviser shall maintain records for a minimum period of 8 years."
    candidates = detect_candidate_requirements_in_text(text)
    assert len(candidates) >= 1
    assert any("shall" in c.trigger_cues or "shall maintain" in c.trigger_cues for c in candidates)
    assert "MANDATORY" in candidates[0].cue_categories or "MANDATORY_MAINTAIN" in candidates[0].cue_categories


def test_detect_prohibition():
    text = "The intermediary shall not charge any fees prior to signing the agreement with the client."
    candidates = detect_candidate_requirements_in_text(text)
    assert len(candidates) >= 1
    assert any("shall not" in c.trigger_cues for c in candidates)
    assert "PROHIBITION" in candidates[0].cue_categories


def test_detect_temporal_deadlines_and_numerics():
    text = "The entity shall submit the compliance certificate within 15 days of the end of each quarter."
    candidates = detect_candidate_requirements_in_text(text)
    assert len(candidates) >= 1
    assert any("within 15 days" in c.trigger_cues for c in candidates)
    assert "TEMPORAL_DEADLINE" in candidates[0].cue_categories


def test_detect_proviso_conditional():
    text = "Provided that where the net worth falls below ₹50 Lakhs, the broker shall immediately intimate SEBI."
    candidates = detect_candidate_requirements_in_text(text)
    assert len(candidates) >= 1
    assert any("provided that" in c.trigger_cues or "shall" in c.trigger_cues for c in candidates)


def test_filter_noise_recitals():
    recital = "Whereas the Securities and Exchange Board of India is established under Section 3."
    assert is_noise_statement(recital) is True
    candidates = detect_candidate_requirements_in_text(recital)
    assert len(candidates) == 0


def test_table_row_candidate_detection():
    table_text = """
| Requirement Category | Parameter | Timeline |
| --- | --- | --- |
| Compliance Audit | Shall conduct audit | within 30 days |
| Financial Net Worth | Shall maintain ₹50 Lakhs | Immediate |
"""
    candidates = detect_candidate_requirements_in_text(table_text)
    assert any(c.is_table for c in candidates)
