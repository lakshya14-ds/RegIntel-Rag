"""
Unit tests for EffectiveStateEngine and Temporal State Queries (Phases 64.8, 64.9, 64.10, 64.11, 64.12, 64.16, 64.17).
"""

import pytest
from app.compliance.effective_state_engine import EffectiveStateEngine, get_effective_state_engine
from app.compliance.temporal_models import RegulatoryDateEvent
from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ChecklistItem,
)


@pytest.fixture
def engine():
    return get_effective_state_engine()


def test_effective_state_future_date(engine):
    # If effective date is 2027-04-01 and query date is 2026-09-15
    doc_data = {
        "document_id": "doc_future",
        "published_date": "2026-09-01",
        "effective_date": "2027-04-01"
    }
    state = engine.get_regulatory_state(doc_data, as_of_date="2026-09-15")
    assert state.state == "NOT_YET_EFFECTIVE"
    assert state.effective_date == "2027-04-01"
    assert "becomes effective on 2027-04-01" in state.reason


def test_effective_state_past_date(engine):
    # If effective date is 2026-01-15 and query date is 2026-09-15
    doc_data = {
        "document_id": "doc_past",
        "published_date": "2026-01-01",
        "effective_date": "2026-01-15"
    }
    state = engine.get_regulatory_state(doc_data, as_of_date="2026-09-15")
    assert state.state == "EFFECTIVE"
    assert state.effective_date == "2026-01-15"


def test_historical_state_query_across_transition_boundary(engine):
    # Document published 2026-01-01, effective 2026-06-01
    doc_data = {
        "document_id": "doc_transition",
        "published_date": "2026-01-01",
        "effective_date": "2026-06-01"
    }

    # Query 1: Before effective date (2026-05-01) -> NOT_YET_EFFECTIVE
    state_before = engine.get_regulatory_state(doc_data, as_of_date="2026-05-01")
    assert state_before.state == "NOT_YET_EFFECTIVE"

    # Query 2: On effective date (2026-06-01) -> EFFECTIVE
    state_on = engine.get_regulatory_state(doc_data, as_of_date="2026-06-01")
    assert state_on.state == "EFFECTIVE"

    # Query 3: After effective date (2026-07-01) -> EFFECTIVE
    state_after = engine.get_regulatory_state(doc_data, as_of_date="2026-07-01")
    assert state_after.state == "EFFECTIVE"


def test_never_silently_convert_published_date_to_effective_date(engine):
    # Document has published_date but no effective_date
    doc_data = {
        "document_id": "doc_no_eff",
        "published_date": "2026-01-01",
        "effective_date": None
    }
    state = engine.get_regulatory_state(doc_data, as_of_date="2026-09-15")
    # Must NOT assume EFFECTIVE or convert published to effective!
    assert state.state == "UNKNOWN"
    assert state.effective_date is None
    assert "effective date is not explicitly stated" in state.reason


def test_superseded_document_state(engine):
    doc_data = {
        "document_id": "doc_old_version",
        "effective_date": "2024-01-01",
        "superseded_by": "doc_new_version",
        "metadata": {
            "superseded_date": "2026-06-01"
        }
    }

    # Before supersession on 2025-01-01 -> was still EFFECTIVE
    state_2025 = engine.get_regulatory_state(doc_data, as_of_date="2025-01-01")
    assert state_2025.state == "EFFECTIVE"

    # After supersession on 2026-07-01 -> SUPERSEDED
    state_2026 = engine.get_regulatory_state(doc_data, as_of_date="2026-07-01")
    assert state_2026.state == "SUPERSEDED"


def test_expired_document_state(engine):
    doc_data = {
        "document_id": "doc_sunset",
        "effective_date": "2025-01-01",
        "expiry_date": "2025-12-31"
    }

    state_active = engine.get_regulatory_state(doc_data, as_of_date="2025-06-01")
    assert state_active.state == "EFFECTIVE"

    state_expired = engine.get_regulatory_state(doc_data, as_of_date="2026-01-15")
    assert state_expired.state == "EXPIRED"


def test_date_conflict_detection_effective_before_publication(engine):
    doc_data = {
        "document_id": "doc_conflict",
        "published_date": "2026-08-01",
        "effective_date": "2026-01-01"  # Earlier than publication date!
    }
    state = engine.get_regulatory_state(doc_data, as_of_date="2026-09-15")
    assert len(state.conflicts) >= 1
    conflict = state.conflicts[0]
    assert conflict.event_type == "EFFECTIVE_BEFORE_PUBLICATION"
    assert conflict.severity == "WARNING"


def test_requirement_temporal_state_evaluation(engine):
    req_active = RegulatoryRequirement(
        requirement_id="req_01",
        document_id="doc_t1",
        requirement_text="Submit quarterly report.",
        source_evidence="Submit quarterly report.",
        effective_date="2026-01-01"
    )
    req_future = RegulatoryRequirement(
        requirement_id="req_02",
        document_id="doc_t1",
        requirement_text="New mandatory disclosure.",
        source_evidence="New mandatory disclosure.",
        effective_date="2027-04-01"
    )

    eval_active = engine.evaluate_requirement_temporal_state(req_active, as_of_date="2026-09-15")
    assert eval_active.is_active is True
    assert eval_active.state == "ACTIVE"

    eval_future = engine.evaluate_requirement_temporal_state(req_future, as_of_date="2026-09-15")
    assert eval_future.is_active is False
    assert eval_future.state == "NOT_YET_EFFECTIVE"


def test_obligation_temporal_state_evaluation(engine):
    ob_future = RegulatoryObligation(
        obligation_id="ob_01",
        requirement_id="req_02",
        document_id="doc_t1",
        obligated_party="Merchant Banker",
        effective_date="2027-04-01",
        source_evidence="Source text."
    )

    eval_ob = engine.evaluate_obligation_temporal_state(ob_future, as_of_date="2026-09-15")
    assert eval_ob.status == "FUTURE"
    assert eval_ob.days_until_effective is not None
    assert eval_ob.days_until_effective > 0


def test_checklist_item_temporal_state_evaluation(engine):
    item = ChecklistItem(
        item_id="it_01",
        obligation_id="ob_01",
        requirement_id="req_02",
        document_id="doc_t1",
        control_question="Is the new disclosure prepared?",
        compliance_action="Prepare disclosure."
    )

    ob_future = RegulatoryObligation(
        obligation_id="ob_01",
        requirement_id="req_02",
        document_id="doc_t1",
        obligated_party="Merchant Banker",
        effective_date="2027-04-01",
        source_evidence="Source text."
    )
    ob_state = engine.evaluate_obligation_temporal_state(ob_future, as_of_date="2026-09-15")

    item_state = engine.evaluate_checklist_item_temporal_state(item, as_of_date="2026-09-15", obligation_state=ob_state)
    assert item_state.temporal_status == "UPCOMING"
    assert item_state.is_actionable_now is False
    assert item_state.days_until_effective == ob_state.days_until_effective
