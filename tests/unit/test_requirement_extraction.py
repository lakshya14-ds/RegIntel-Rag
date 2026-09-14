"""
Unit tests for Requirement Extraction, Normalization & Atomic Splitting (Phase 61).
"""

import pytest
from app.compliance.requirement_extractor import (
    split_compound_requirement,
    extract_thresholds_and_numerics,
    extract_frequency_deterministic,
    extract_deadline_deterministic,
    extract_requirement_deterministic,
    get_requirement_extractor,
)
from app.compliance.candidate_detector import RequirementCandidate


def test_split_compound_requirement():
    compound = "The intermediary shall maintain client records and submit quarterly returns to the Board."
    split = split_compound_requirement(compound)
    assert len(split) == 2
    assert "maintain client records" in split[0]
    assert "submit quarterly returns" in split[1]


def test_extract_thresholds_and_numerics():
    text = "The net worth must be at least ₹50 Lakhs and records maintained for 8 years with 10% allocation."
    thresholds = extract_thresholds_and_numerics(text)
    assert len(thresholds) >= 3
    types = [t.parameter_type for t in thresholds]
    assert "currency" in types
    assert "duration" in types
    assert "percentage" in types


def test_extract_frequency():
    assert extract_frequency_deterministic("Reports submitted each quarter.") == "QUARTERLY"
    assert extract_frequency_deterministic("Audits conducted annually.") == "ANNUALLY"
    assert extract_frequency_deterministic("Statements filed monthly.") == "MONTHLY"


def test_extract_deadline():
    text = "The compliance certificate shall be filed within 15 days of the close of the financial year."
    dl = extract_deadline_deterministic(text)
    assert dl is not None
    assert "within 15 days" in dl.lower()


def test_deterministic_requirement_pipeline():
    cand = RequirementCandidate(
        candidate_text="The investment adviser shall submit quarterly audit reports within 15 days.",
        cleaned_text="The investment adviser shall submit quarterly audit reports within 15 days.",
        trigger_cues=["shall submit", "within 15 days"],
        cue_categories=["MANDATORY_SUBMIT", "TEMPORAL_DEADLINE"],
        section_id="sec_001",
        section_number="3.1",
        heading="Audit Requirements",
        page_number=4
    )

    reqs = extract_requirement_deterministic(
        candidate=cand,
        document_id="doc_sebi_ia",
        authority="SEBI",
        document_title="SEBI (IA) Regulations"
    )

    assert len(reqs) >= 1
    req = reqs[0]
    assert req.requirement_type in ["REPORTING", "SUBMISSION", "AUDIT"]
    assert req.authority == "SEBI"
    assert req.source_locator.get("section_number") == "3.1"
    assert req.source_locator.get("page_number") == 4
    assert req.deadline is not None and "15 days" in req.deadline
    assert req.frequency == "QUARTERLY"


def test_requirement_deduplication():
    extractor = get_requirement_extractor()
    text = "The investment adviser shall maintain records for 8 years. The investment adviser shall maintain records for 8 years."
    reqs = extractor.extract_requirements_from_text(
        text=text,
        document_id="doc_test_dedup",
        use_llm=False
    )
    # Even though sentence repeated twice, deduplication ensures unique requirement
    assert len(reqs) == 1
