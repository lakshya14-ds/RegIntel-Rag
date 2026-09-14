"""
Unit tests for Section Matching and Reordered/Moved Clause Detection (Phase 60.3, 60.4).
"""

import pytest
from app.change_detection.diff_engine import (
    RegulatorySection,
    match_sections_hierarchical
)


def test_exact_section_number_matching():
    """Verify Tier 1: exact section number alignment."""
    old_sec = RegulatorySection(
        section_id="old_1",
        section_number="4.2",
        heading="Old Title",
        content="Prior content",
        order=1
    )
    new_sec = RegulatorySection(
        section_id="new_1",
        section_number="4.2",
        heading="New Title",
        content="Updated content",
        order=1
    )

    pairs = match_sections_hierarchical([old_sec], [new_sec])
    assert len(pairs) == 1
    old_s, new_s, method, is_moved = pairs[0]
    assert method == "section_number"
    assert is_moved is False
    assert old_s.section_id == "old_1"
    assert new_s.section_id == "new_1"


def test_moved_reordered_section_detection():
    """Verify 60.4: Section 4.2 renumbered to Section 5.1 with equivalent content is MOVED."""
    common_content = "Investment Advisers shall preserve records for 8 years."
    old_sec = RegulatorySection(
        section_id="old_sec",
        section_number="4.2",
        heading="Maintenance of Records",
        content=common_content,
        normalized_content=common_content.lower(),
        order=1
    )
    new_sec = RegulatorySection(
        section_id="new_sec",
        section_number="5.1",
        heading="Maintenance of Records",
        content=common_content,
        normalized_content=common_content.lower(),
        order=2
    )

    pairs = match_sections_hierarchical([old_sec], [new_sec])
    assert len(pairs) == 1
    old_s, new_s, method, is_moved = pairs[0]
    assert is_moved is True
    assert old_s.section_number == "4.2"
    assert new_s.section_number == "5.1"


def test_unmatched_added_and_removed():
    """Verify unmatched sections classified as ADDED or REMOVED."""
    old_sec = RegulatorySection(
        section_id="old_orphan",
        section_number="7.1",
        heading="Obsolete Clause",
        content="Deleted rules.",
        normalized_content="deleted rules.",
        order=1
    )
    new_sec = RegulatorySection(
        section_id="new_orphan",
        section_number="9.3",
        heading="Novel Requirement",
        content="New ESG disclosures.",
        normalized_content="new esg disclosures.",
        order=1
    )

    pairs = match_sections_hierarchical([old_sec], [new_sec])
    assert len(pairs) == 2

    # One unmatched new (ADDED)
    added_pair = next(p for p in pairs if p[2] == "unmatched_new")
    assert added_pair[0] is None
    assert added_pair[1].section_id == "new_orphan"

    # One unmatched old (REMOVED)
    removed_pair = next(p for p in pairs if p[2] == "unmatched_old")
    assert removed_pair[0].section_id == "old_orphan"
    assert removed_pair[1] is None
