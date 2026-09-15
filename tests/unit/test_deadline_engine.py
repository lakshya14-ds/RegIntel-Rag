"""
Unit tests for DeadlineIntelligenceEngine (Phase 65.2, 65.3, 65.4).
"""

import pytest
from datetime import datetime
from app.compliance.deadline_engine import DeadlineIntelligenceEngine, get_deadline_engine
from app.compliance.models import RegulatoryObligation


@pytest.fixture
def engine():
    return get_deadline_engine()


def test_extract_absolute_deadline(engine):
    ob = RegulatoryObligation(
        obligation_id="ob_d1",
        requirement_id="req_d1",
        document_id="doc_d1",
        obligated_party="Custodian",
        deadline="by 30 June 2026",
        source_evidence="The custodian shall submit audit certificates by 30 June 2026."
    )

    ddls = engine.extract_deadlines_from_obligation(ob, as_of_date="2026-06-15")
    assert len(ddls) == 1
    d = ddls[0]
    assert d.deadline_type == "ABSOLUTE"
    assert d.due_date == "2026-06-30"
    assert d.due_date_derivation == "EXPLICIT"
    assert d.days_remaining == 15
    assert d.status == "UPCOMING"


def test_extract_relative_deadline_with_effective_date(engine):
    ob = RegulatoryObligation(
        obligation_id="ob_d2",
        requirement_id="req_d2",
        document_id="doc_d2",
        obligated_party="Merchant Banker",
        deadline="within 15 days",
        effective_date="2026-10-01",
        source_evidence="Submit compliance report within 15 days."
    )

    ddls = engine.extract_deadlines_from_obligation(ob, as_of_date="2026-10-05")
    assert len(ddls) == 1
    d = ddls[0]
    assert d.deadline_type == "RELATIVE"
    assert d.due_date == "2026-10-16"
    assert d.due_date_derivation == "CALCULATED"
    assert d.days_remaining == 11
    assert d.status == "UPCOMING"


def test_recurring_quarterly_deadline_bounded_window(engine):
    ob = RegulatoryObligation(
        obligation_id="ob_d3",
        requirement_id="req_d3",
        document_id="doc_d3",
        obligated_party="Investment Adviser",
        deadline="within 15 days of the end of each quarter",
        frequency="QUARTERLY",
        source_evidence="The investment adviser shall submit quarterly reports within 15 days of each quarter."
    )

    # Reference date is middle of year: 2026-07-01
    # 180-day window covers Q1 FY 2027 (end 30 June + 15 days = 15 July 2026) and Q2 FY 2027 (end 30 Sept + 15 days = 15 Oct 2026)
    ddls = engine.extract_deadlines_from_obligation(ob, as_of_date="2026-07-01", planning_window_days=180)
    assert len(ddls) >= 1
    assert all(d.deadline_type == "RECURRING" for d in ddls)
    assert all(d.frequency == "QUARTERLY" for d in ddls)
    assert all(d.due_date_derivation == "CALCULATED" for d in ddls)

    # Verify first upcoming due date is July 15, 2026
    first = ddls[0]
    assert first.due_date == "2026-07-15"
    assert first.days_remaining == 14
    assert first.status == "UPCOMING"


def test_deadline_status_overdue_and_due_soon(engine):
    ob_overdue = RegulatoryObligation(
        obligation_id="ob_d4",
        requirement_id="req_d4",
        document_id="doc_d4",
        deadline="by 10 September 2026",
        source_evidence="Submit by 10 September 2026."
    )
    # Query date is 2026-09-15 -> 5 days past due!
    ddls = engine.extract_deadlines_from_obligation(ob_overdue, as_of_date="2026-09-15")
    assert len(ddls) == 1
    assert ddls[0].days_remaining == -5
    assert ddls[0].status == "OVERDUE"

    ob_soon = RegulatoryObligation(
        obligation_id="ob_d5",
        requirement_id="req_d5",
        document_id="doc_d5",
        deadline="by 18 September 2026",
        source_evidence="Submit by 18 September 2026."
    )
    # Query date is 2026-09-15 -> 3 days remaining!
    ddls_soon = engine.extract_deadlines_from_obligation(ob_soon, as_of_date="2026-09-15")
    assert len(ddls_soon) == 1
    assert ddls_soon[0].days_remaining == 3
    assert ddls_soon[0].status == "DUE_SOON"
