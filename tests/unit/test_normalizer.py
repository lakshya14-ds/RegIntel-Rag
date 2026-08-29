"""
Unit tests for Regulatory Text and Heading Normalization Module.
"""

import pytest
from app.change_detection.normalizer import (
    normalize_whitespace,
    normalize_punctuation_and_quotes,
    normalize_regulatory_text,
    normalize_heading,
    extract_section_number,
    are_texts_substantively_equal
)


def test_normalize_whitespace():
    raw = "Section 4.2 \t\t  Eligibility   \n\n\n\n  Requirements   and   Criteria. \r\n"
    norm = normalize_whitespace(raw)
    assert norm == "Section 4.2 Eligibility\n\nRequirements and Criteria."


def test_normalize_punctuation_and_quotes():
    raw = "The “Investment Adviser” shall ‘maintain’ records for – 8 years • strictly."
    norm = normalize_punctuation_and_quotes(raw)
    assert norm == 'The "Investment Adviser" shall \'maintain\' records for - 8 years - strictly.'


def test_normalize_heading():
    assert normalize_heading("## 1.2 Eligibility Requirements") == "eligibility requirements"
    assert normalize_heading("Section 4: Client Agreement & Fees") == "section 4 client agreement fees"
    assert normalize_heading("### 5. Maintenance of Records.") == "maintenance of records"
    assert normalize_heading("") == ""


def test_extract_section_number():
    num1, title1 = extract_section_number("## 1.2 Eligibility Requirements")
    assert num1 == "1.2"
    assert title1 == "Eligibility Requirements"

    num2, title2 = extract_section_number("Section 4: Audit Norms")
    assert num2 == "4"
    assert title2 == "Audit Norms"

    num3, title3 = extract_section_number("## General Governance")
    assert num3 == ""
    assert title3 == "General Governance"


def test_are_texts_substantively_equal_identical():
    text_a = "Net worth requirement is INR 50 Lakhs for corporate IAs."
    text_b = "Net worth requirement is INR 50 Lakhs for corporate IAs."
    assert are_texts_substantively_equal(text_a, text_b) is True


def test_are_texts_substantively_equal_whitespace_formatting_only():
    text_a = "Net worth requirement is INR 50 Lakhs.\n\nAnnual audit within 6 months."
    text_b = "  Net worth requirement is INR 50 Lakhs.   \nAnnual audit within 6 months.  "
    assert are_texts_substantively_equal(text_a, text_b) is True


def test_are_texts_substantively_equal_different():
    text_a = "Net worth requirement is INR 25 Lakhs."
    text_b = "Net worth requirement is INR 50 Lakhs."
    assert are_texts_substantively_equal(text_a, text_b) is False
