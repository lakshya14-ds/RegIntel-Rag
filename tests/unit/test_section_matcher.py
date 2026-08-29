"""
Unit tests for 4-Tier Structural Section Matcher Module.
"""

import pytest
from app.change_detection.section_matcher import SectionMatcher, ExtractedSection


def test_extract_sections_with_markdown_headings():
    content = """# 1. Net Worth
The net worth requirement shall be INR 50 Lakhs.

# 2. Client Agreements
Advisers must enter into written agreements.

# 3. Compliance Audit
Annual audit required.
"""
    sections = SectionMatcher.extract_sections(content, document_id="doc_test")
    assert len(sections) == 3
    assert sections[0].section_number == "1"
    assert sections[0].heading == "Net Worth"
    assert sections[1].section_number == "2"
    assert sections[1].heading == "Client Agreements"
    assert sections[2].section_number == "3"
    assert sections[2].heading == "Compliance Audit"


def test_extract_sections_fallback_no_headers():
    content = "This circular establishes uniform grievance redressal guidelines."
    sections = SectionMatcher.extract_sections(content, document_id="doc_no_headers")
    assert len(sections) == 1
    assert sections[0].heading == "General Provisions"
    assert sections[0].section_number is None


def test_match_sections_4_tiers():
    older_content = """# 1. Eligibility Criteria
Experience requirement of 5 years.

# 2. Record Maintenance
Maintain physical records for 5 years.

# 3. Paper Submissions
Submit physical filings.
"""
    newer_content = """# 1. Eligibility Criteria
Experience requirement of 5 years.

# 2. Maintenance of Records
Maintain digital records for 8 years.

# 4. Digital Portal Submission
Submit filings via SEBI portal.
"""
    older_secs = SectionMatcher.extract_sections(older_content, document_id="old_doc")
    newer_secs = SectionMatcher.extract_sections(newer_content, document_id="new_doc")

    pairs = SectionMatcher.match_sections(older_secs, newer_secs)

    # We expect:
    # 1. Sec 1: exact section number match ("section_number", high confidence)
    # 2. Sec 2: exact section number match ("section_number", high confidence)
    # 3. Sec 4: unmatched new ("unmatched_new", none)
    # 4. Sec 3: unmatched old ("unmatched_old", none)
    assert len(pairs) == 4

    matched_by_num = [p for p in pairs if p.matching_method == "section_number"]
    assert len(matched_by_num) == 2

    added = [p for p in pairs if p.matching_method == "unmatched_new"]
    assert len(added) == 1
    assert added[0].newer_section.heading == "Digital Portal Submission"

    removed = [p for p in pairs if p.matching_method == "unmatched_old"]
    assert len(removed) == 1
    assert removed[0].older_section.heading == "Paper Submissions"


def test_match_sections_heading_fuzzy_similarity():
    older_secs = [
        ExtractedSection(
            section_id="old_sec_1",
            section_number=None,
            heading="General Operational Risk Governance Norms",
            content="Maintain risk framework.",
            order=1
        )
    ]
    newer_secs = [
        ExtractedSection(
            section_id="new_sec_1",
            section_number=None,
            heading="General Operational Risk Governance",
            content="Maintain updated risk framework.",
            order=1
        )
    ]

    pairs = SectionMatcher.match_sections(older_secs, newer_secs)
    assert len(pairs) == 1
    assert pairs[0].matching_method in ("exact_heading", "heading_similarity")
    assert pairs[0].matching_confidence in ("high", "medium")
