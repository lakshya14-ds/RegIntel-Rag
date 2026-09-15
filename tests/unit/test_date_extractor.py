"""
Unit tests for RegulatoryDateExtractor (Phase 64.3, 64.4, 64.5, 64.6, 64.7).
"""

import pytest
from app.compliance.date_extractor import (
    RegulatoryDateExtractor,
    parse_calendar_date,
    get_regulatory_date_extractor,
)


def test_parse_calendar_date():
    # ISO formats
    assert parse_calendar_date("2026-10-01") == "2026-10-01"
    # DD Month YYYY
    assert parse_calendar_date("01 April 2027") == "2027-04-01"
    assert parse_calendar_date("1st April, 2027") == "2027-04-01"
    assert parse_calendar_date("15 March 2026") == "2026-03-15"
    # Month DD, YYYY
    assert parse_calendar_date("October 01, 2026") == "2026-10-01"
    # DD/MM/YYYY
    assert parse_calendar_date("15/01/2026") == "2026-01-15"
    # Invalid
    assert parse_calendar_date("invalid-text") is None
    assert parse_calendar_date("") is None


def test_extract_explicit_effective_dates():
    extractor = get_regulatory_date_extractor()
    text = "The provisions of these regulations shall come into force with effect from 1 April 2027."
    events = extractor.extract_dates(text=text, document_id="doc_test_01")

    assert len(events) >= 1
    eff_event = next((e for e in events if e.event_type == "EFFECTIVE"), None)
    assert eff_event is not None
    assert eff_event.date == "2027-04-01"
    assert eff_event.derivation_type == "EXPLICIT"
    assert eff_event.extraction_method == "DETERMINISTIC"
    assert eff_event.confidence == "HIGH"
    assert "shall come into force with effect from 1 April 2027" in eff_event.source_text


def test_extract_wef_effective_date():
    extractor = get_regulatory_date_extractor()
    text = "This reporting framework shall be applicable w.e.f. 01/10/2026 for all registered entities."
    events = extractor.extract_dates(text=text, document_id="doc_test_02")

    eff_event = next((e for e in events if e.event_type == "EFFECTIVE"), None)
    assert eff_event is not None
    assert eff_event.date == "2026-10-01"
    assert eff_event.derivation_type == "EXPLICIT"


def test_extract_immediate_effect_with_known_publication_date():
    extractor = get_regulatory_date_extractor()
    text = "The amendments specified herein shall come into force with immediate effect."
    events = extractor.extract_dates(
        text=text,
        document_id="doc_test_03",
        known_publication_date="2026-08-15"
    )

    eff_event = next((e for e in events if e.event_type == "EFFECTIVE"), None)
    assert eff_event is not None
    assert eff_event.date == "2026-08-15"
    assert eff_event.derivation_type == "DERIVED"
    assert eff_event.offset_days == 0
    assert "Immediate effect" in (eff_event.derivation_rule or "")


def test_extract_relative_effective_date_with_offset():
    extractor = get_regulatory_date_extractor()
    text = "Entities shall comply with the new norms within 30 days from the date of publication."
    events = extractor.extract_dates(
        text=text,
        document_id="doc_test_04",
        known_publication_date="2026-08-01"
    )

    eff_event = next((e for e in events if e.event_type == "EFFECTIVE"), None)
    assert eff_event is not None
    assert eff_event.date == "2026-08-31"
    assert eff_event.derivation_type == "DERIVED"
    assert eff_event.offset_days == 30
    assert eff_event.base_event_type == "PUBLISHED"
    assert "Relative: PUBLISHED + 30 days" in (eff_event.derivation_rule or "")


def test_extract_relative_effective_date_without_known_publication_date():
    extractor = get_regulatory_date_extractor()
    text = "These instructions shall take effect within 15 days from publication."
    events = extractor.extract_dates(
        text=text,
        document_id="doc_test_05",
        known_publication_date=None
    )

    eff_event = next((e for e in events if e.event_type == "EFFECTIVE"), None)
    assert eff_event is not None
    assert eff_event.date is None  # Base date unknown, so date remains None
    assert eff_event.derivation_type == "DERIVED"
    assert eff_event.offset_days == 15
    assert eff_event.confidence == "MEDIUM"


def test_extract_expiry_date():
    extractor = get_regulatory_date_extractor()
    text = "This temporary relaxation shall remain in force until 31 December 2026."
    events = extractor.extract_dates(text=text, document_id="doc_test_06")

    exp_event = next((e for e in events if e.event_type == "EXPIRES"), None)
    assert exp_event is not None
    assert exp_event.date == "2026-12-31"
    assert exp_event.derivation_type == "EXPLICIT"


def test_no_date_present_returns_empty():
    extractor = get_regulatory_date_extractor()
    text = "The Board may from time to time specify conditions as deemed fit."
    events = extractor.extract_dates(text=text, document_id="doc_test_07")
    assert events == []
