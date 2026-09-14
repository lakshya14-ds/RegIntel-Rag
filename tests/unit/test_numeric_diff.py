"""
Unit tests for Deterministic Numerical and Regulatory Keyword Change Detection (Phase 60.11, 60.12).
"""

import pytest
from app.change_detection.diff_engine import (
    detect_numerical_changes,
    detect_keyword_changes
)


def test_deadline_and_duration_change():
    """Verify detection of deadline shifts: 30 days -> 15 days."""
    old_text = "The intermediary shall submit the compliance certificate within 30 days of fiscal year end."
    new_text = "The intermediary shall submit the compliance certificate within 15 days of fiscal year end."

    changes = detect_numerical_changes(old_text, new_text)
    assert len(changes) >= 1
    match = next(c for c in changes if "30 days" in c.previous_value and "15 days" in c.new_value)
    assert match.change_type == "NUMERICAL_CHANGE"
    assert match.previous_value == "30 days"
    assert match.new_value == "15 days"


def test_percentage_threshold_change():
    """Verify detection of percentage shifts: 5% -> 10%."""
    old_text = "The maximum fee allowed is 5% of AUM."
    new_text = "The maximum fee allowed is 10% of AUM."

    changes = detect_numerical_changes(old_text, new_text)
    assert len(changes) >= 1
    match = next(c for c in changes if "5%" in c.previous_value and "10%" in c.new_value)
    assert match.previous_value == "5%"
    assert match.new_value == "10%"


def test_currency_threshold_change():
    """Verify detection of monetary thresholds: INR 25 Lakhs -> INR 50 Lakhs."""
    old_text = "Corporate IAs must maintain a net worth of INR 25 Lakhs."
    new_text = "Corporate IAs must maintain a net worth of INR 50 Lakhs."

    changes = detect_numerical_changes(old_text, new_text)
    assert len(changes) >= 1
    match = next(c for c in changes if "25 Lakhs" in c.previous_value and "50 Lakhs" in c.new_value)
    assert match.change_type == "NUMERICAL_CHANGE"


def test_regulatory_keyword_shift():
    """Verify detection of deontic modal keywords: 'shall' -> 'may', and 'prohibited' added."""
    old_text = "The entity shall disclose conflict of interest."
    new_text = "The entity may disclose conflict of interest. Trading on inside tips is prohibited."

    kw_changes = detect_keyword_changes(old_text, new_text)
    keywords_added = [k.keyword for k in kw_changes if k.change_type == "ADDED"]
    keywords_removed = [k.keyword for k in kw_changes if k.change_type == "REMOVED"]

    assert "may" in keywords_added
    assert "prohibited" in keywords_added
    assert "shall" in keywords_removed
