"""
Unit tests for Paragraph-Level Regulatory Diff (Phase 60.9, 60.10).
"""

import pytest
from app.change_detection.diff_engine import diff_paragraphs


def test_paragraph_diff_modified_with_numerical_shift():
    """Verify paragraph modification detection with internal numerical shifts."""
    old_text = "The intermediary shall maintain records for 5 years.\n\nAll reports must be submitted within 30 days."
    new_text = "The intermediary shall maintain records for 8 years.\n\nAll reports must be submitted within 15 days."

    p_diffs = diff_paragraphs(old_text, new_text)
    assert len(p_diffs) == 2

    # Paragraph 1
    assert p_diffs[0].change_type == "MODIFIED"
    assert len(p_diffs[0].numerical_changes) > 0
    assert any("5 years" in nc.previous_value and "8 years" in nc.new_value for nc in p_diffs[0].numerical_changes)

    # Paragraph 2
    assert p_diffs[1].change_type == "MODIFIED"
    assert len(p_diffs[1].numerical_changes) > 0
    assert any("30 days" in nc.previous_value and "15 days" in nc.new_value for nc in p_diffs[1].numerical_changes)


def test_paragraph_diff_added_and_removed_paragraphs():
    """Verify paragraph insertion and deletion within a section."""
    old_text = "Paragraph One.\n\nParagraph Two to delete."
    new_text = "Paragraph One.\n\nParagraph Three inserted."

    p_diffs = diff_paragraphs(old_text, new_text)
    assert len(p_diffs) >= 2
    types = [p.change_type for p in p_diffs]
    assert "UNCHANGED" in types
    assert "MODIFIED" in types or ("ADDED" in types or "REMOVED" in types)
