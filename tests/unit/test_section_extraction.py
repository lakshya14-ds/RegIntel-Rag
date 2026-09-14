"""
Unit tests for Hierarchical Section Extraction (Phase 60.2, 60.14).
"""

import pytest
from app.change_detection.diff_engine import extract_hierarchical_sections, extract_page_number


def test_hierarchical_chapter_and_sections():
    """Verify that chapter hierarchy is preserved across sections."""
    text = """
    Chapter I: Preliminary
    1. Short Title and Commencement
    These regulations may be called SEBI IA Regulations.
    
    1.2 Definitions
    In these regulations, IA means Investment Adviser.

    Chapter II: Registration
    3. Application for Registration
    An application shall be made in Form A.
    """
    sections = extract_hierarchical_sections(text, document_id="test_doc")
    assert len(sections) == 3

    sec1 = sections[0]
    assert sec1.section_number == "1"
    assert "Chapter I" in (sec1.parent_section or "")

    sec2 = sections[1]
    assert sec2.section_number == "1.2"
    assert "Chapter I" in (sec2.parent_section or "")

    sec3 = sections[2]
    assert sec3.section_number == "3"
    assert "Chapter II" in (sec3.parent_section or "")


def test_extract_page_numbers():
    """Verify page number extraction from content."""
    assert extract_page_number("Published on Page 7 of 24") == 7
    assert extract_page_number("Clause starts at Pg. 12.") == 12
    assert extract_page_number("No page info here") is None


def test_fallback_unstructured_content():
    """Verify fallback to General Provisions when no explicit headers exist."""
    text = "This is a simple unstructured regulatory notice issued by SEBI."
    sections = extract_hierarchical_sections(text, document_id="doc_unstructured")
    assert len(sections) == 1
    assert sections[0].heading == "General Provisions"
    assert sections[0].content == text
