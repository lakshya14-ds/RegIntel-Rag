"""
Unit tests for Full SectionDiff and Table-Aware Diff (Phase 60.13, 60.15, 60.16).
"""

import pytest
from app.change_detection.diff_engine import (
    RegulatoryDiffEngine,
    SectionDiffCache,
    compare_tables
)


def test_table_comparison_unavailable_when_no_tables():
    """Verify that text without table markers returns TABLE_COMPARISON_UNAVAILABLE."""
    old_text = "Simple plain text regulation."
    new_text = "Updated plain text regulation."

    res = compare_tables(old_text, new_text)
    assert res.status == "TABLE_COMPARISON_UNAVAILABLE"


def test_table_comparison_when_markdown_tables_exist():
    """Verify row and cell delta detection when markdown tables are present."""
    old_text = "| Category | Fee Cap |\n|---|---|\n| Individual | 2.5% |\n| Corporate | 5.0% |"
    new_text = "| Category | Fee Cap |\n|---|---|\n| Individual | 2.5% |\n| Corporate | 7.5% |\n| Institutional | 10.0% |"

    res = compare_tables(old_text, new_text)
    assert res.status == "TABLES_COMPARED"
    assert res.rows_added == 1
    assert res.cells_modified >= 1


def test_section_diff_full_flow():
    """Verify complete section diff flow across multiple regulatory sections."""
    doc_old = """
    ## 1. Eligibility
    Page 1. Net worth requirement is INR 25 Lakhs.
    
    ## 2. Reordered Clause
    Common text to preserve.
    
    ## 3. Repealed Clause
    Will be removed in next version.
    """

    doc_new = """
    ## 1. Eligibility
    Page 2. Net worth requirement is INR 50 Lakhs.
    
    ## 4. Reordered Clause
    Common text to preserve.
    
    ## 5. Brand New Section
    Newly created disclosure norms.
    """

    cache = SectionDiffCache()
    engine = RegulatoryDiffEngine(cache=cache)

    report = engine.diff_documents(
        older_doc_id="doc_old",
        older_content=doc_old,
        newer_doc_id="doc_new",
        newer_content=doc_new
    )

    assert report.status == "SUCCESS"
    assert report.statistics["modified"] >= 1
    assert report.statistics["added"] >= 1
    assert report.statistics["removed"] >= 1
    assert report.statistics["moved"] >= 1

    # Check page reference tracking
    sec_eligibility = next(s for s in report.sections if s.heading == "Eligibility")
    assert sec_eligibility.old_page == 1
    assert sec_eligibility.new_page == 2
    assert len(sec_eligibility.numerical_changes) > 0


def test_section_diff_cache():
    """Verify diff caching and retrieval."""
    cache = SectionDiffCache()
    engine = RegulatoryDiffEngine(cache=cache)

    text_a = "## 1. Clause\nContent A."
    text_b = "## 1. Clause\nContent B."

    res1 = engine.diff_documents("doc_1", text_a, "doc_2", text_b)
    assert res1.cached is False

    res2 = engine.diff_documents("doc_1", text_a, "doc_2", text_b)
    assert res2.cached is True

    cache.clear()
    res3 = engine.diff_documents("doc_1", text_a, "doc_2", text_b)
    assert res3.cached is False
