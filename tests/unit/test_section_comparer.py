import pytest
from app.change_detection.section_comparer import (
    SectionComparer,
    RegulatorySection,
    AlignedSectionPair,
    normalize_heading
)


def test_normalize_heading():
    assert normalize_heading("### 2. Registration and Qualification Norms") == "registration and qualification norms"
    assert normalize_heading("4.2 Eligibility Criteria!") == "eligibility criteria"


def test_extract_sections():
    text = """# Circular Header
Some introductory text.

## 1. Eligibility Norms
Must have net worth of INR 50 Lakhs.

## 2. Fee Mechanism
Fees are capped under Regulation 15A.
"""
    sections = SectionComparer.extract_sections(text, document_id="doc_test")
    assert len(sections) == 3
    assert sections[1].heading == "Eligibility Norms"
    assert "50 Lakhs" in sections[1].content
    assert sections[2].heading == "Fee Mechanism"


def test_align_and_classify_sections():
    prev_sections = [
        RegulatorySection(
            section_id="prev_1",
            section_number="1",
            heading="Eligibility Norms",
            content="Must have net worth of INR 25 Lakhs."
        ),
        RegulatorySection(
            section_id="prev_2",
            section_number="2",
            heading="Fee Schedule",
            content="Fees capped at 2.5 percent."
        ),
        RegulatorySection(
            section_id="prev_3",
            section_number="3",
            heading="Old Provision",
            content="This rule will be removed."
        )
    ]

    curr_sections = [
        RegulatorySection(
            section_id="curr_1",
            section_number="1",
            heading="Eligibility Norms",
            content="Must have net worth of INR 50 Lakhs."  # Modified
        ),
        RegulatorySection(
            section_id="curr_2",
            section_number="2",
            heading="Fee Schedule",
            content="Fees capped at 2.5 percent."  # Unchanged
        ),
        RegulatorySection(
            section_id="curr_4",
            section_number="4",
            heading="Digital Audit",
            content="Annual digital forensic audit required."  # Added
        )
    ]

    aligned_pairs = SectionComparer.align_sections(prev_sections, curr_sections)
    assert len(aligned_pairs) == 4

    classifications = {pair.section_key: SectionComparer.classify_change(pair) for pair in aligned_pairs}

    # Section 1: Modified
    assert classifications["sec_1"][0] == "MODIFIED"
    assert classifications["sec_1"][1] in {"eligibility", "fees", "other"}

    # Section 2: Unchanged
    assert classifications["sec_2"][0] == "UNCHANGED"

    # Section 3 (Removed)
    assert classifications["prev_3"][0] == "REMOVED"

    # Section 4 (Added)
    assert classifications["curr_4"][0] == "ADDED"
    assert classifications["curr_4"][1] in {"compliance", "documentation", "timelines", "other"}
