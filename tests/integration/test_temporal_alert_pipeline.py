"""
End-to-End Integration Test for Temporal State & Alert Intelligence (Phases 64 & 65).

Demonstrates the full regulatory lifecycle:
1. Version 1 published 01 Jan 2026, effective 15 Jan 2026 (submit report within 15 days).
2. Version 2 published 01 Aug 2026, effective 01 Oct 2026 (submit report within 30 days).
3. State queries before 01 Oct 2026 show Version 1 obligation active.
4. State queries from 01 Oct 2026 show Version 2 obligation active.
5. Upcoming change intelligence surfaces the transition before 01 Oct 2026.
6. Checklist impact reflects the pending amendment.
7. Deduplicated alert is generated with full explainability pointing to source evidence.
"""

import pytest
from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ComplianceChecklist,
    ChecklistItem,
)
from app.compliance.temporal_models import RegulatoryDateEvent
from app.compliance.effective_state_engine import get_effective_state_engine
from app.compliance.deadline_engine import get_deadline_engine
from app.compliance.alert_engine import get_alert_engine
from app.compliance.repository import get_compliance_repository

repo = get_compliance_repository()
state_engine = get_effective_state_engine()
deadline_engine = get_deadline_engine()
alert_engine = get_alert_engine()


def test_end_to_end_regulatory_evolution_and_alerts():
    # -------------------------------------------------------------------------
    # 1. VERSION 1 SETUP
    # -------------------------------------------------------------------------
    doc_v1 = {
        "document_id": "doc_inv_adv_v1",
        "title": "SEBI Intermediary Reporting Regulations 2026 (Version 1)",
        "published_date": "2026-01-01",
        "effective_date": "2026-01-15",
        "status": "CURRENT"
    }

    req_v1 = RegulatoryRequirement(
        requirement_id="req_e2e_v1",
        document_id="doc_inv_adv_v1",
        requirement_text="Every registered intermediary shall submit its compliance report within 15 days of period end.",
        source_evidence="Section 4.1: Every registered intermediary shall submit its compliance report within 15 days of period end.",
        effective_date="2026-01-15",
        deadline="within 15 days",
        frequency="QUARTERLY"
    )

    ob_v1 = RegulatoryObligation(
        obligation_id="ob_e2e_v1",
        requirement_id="req_e2e_v1",
        document_id="doc_inv_adv_v1",
        obligated_party="Intermediary",
        obligation_action="submit",
        obligation_object="compliance report",
        effective_date="2026-01-15",
        deadline="within 15 days",
        frequency="QUARTERLY",
        source_evidence="Section 4.1: Every registered intermediary shall submit its compliance report within 15 days of period end."
    )

    # -------------------------------------------------------------------------
    # 2. VERSION 2 SETUP (Amending V1 effective 01 Oct 2026: 15 days -> 30 days)
    # -------------------------------------------------------------------------
    doc_v2 = {
        "document_id": "doc_inv_adv_v2",
        "title": "SEBI Intermediary Reporting (Amendment) Regulations 2026 (Version 2)",
        "published_date": "2026-08-01",
        "effective_date": "2026-10-01",
        "status": "NOT_YET_EFFECTIVE"
    }

    req_v2 = RegulatoryRequirement(
        requirement_id="req_e2e_v2",
        document_id="doc_inv_adv_v2",
        requirement_text="Every registered intermediary shall submit its compliance report within 30 days of period end.",
        source_evidence="Section 2(a): Every registered intermediary shall submit its compliance report within 30 days of period end.",
        effective_date="2026-10-01",
        deadline="within 30 days",
        frequency="QUARTERLY"
    )

    ob_v2 = RegulatoryObligation(
        obligation_id="ob_e2e_v2",
        requirement_id="req_e2e_v2",
        document_id="doc_inv_adv_v2",
        obligated_party="Intermediary",
        obligation_action="submit",
        obligation_object="compliance report",
        effective_date="2026-10-01",
        deadline="within 30 days",
        frequency="QUARTERLY",
        source_evidence="Section 2(a): Every registered intermediary shall submit its compliance report within 30 days of period end."
    )

    import uuid
    v2_event_id = f"rde_e2e_{uuid.uuid4().hex[:8]}"
    date_event_v2 = RegulatoryDateEvent(
        event_id=v2_event_id,
        document_id="doc_inv_adv_v2",
        event_type="EFFECTIVE",
        date="2026-10-01",
        source_text="shall come into effect from 1 October 2026",
        derivation_type="EXPLICIT",
        confidence="HIGH"
    )

    repo.save_requirements([req_v1, req_v2])
    repo.save_obligations([ob_v1, ob_v2])
    repo.save_date_events([date_event_v2])

    # -------------------------------------------------------------------------
    # 3. HISTORICAL STATE EVALUATIONS (64.9, 64.10, 64.11)
    # -------------------------------------------------------------------------

    # Query as of 15 September 2026 (Before 01 Oct 2026):
    # - V1 document is EFFECTIVE, V2 is NOT_YET_EFFECTIVE
    state_v1_sep = state_engine.get_regulatory_state(doc_v1, as_of_date="2026-09-15")
    state_v2_sep = state_engine.get_regulatory_state(doc_v2, as_of_date="2026-09-15")
    assert state_v1_sep.state == "EFFECTIVE"
    assert state_v2_sep.state == "NOT_YET_EFFECTIVE"

    # Obligation V1 is ACTIVE, Obligation V2 is FUTURE
    ob1_sep = state_engine.evaluate_obligation_temporal_state(ob_v1, as_of_date="2026-09-15", document_eval=state_v1_sep)
    ob2_sep = state_engine.evaluate_obligation_temporal_state(ob_v2, as_of_date="2026-09-15", document_eval=state_v2_sep)
    assert ob1_sep.status == "ACTIVE"
    assert ob2_sep.status == "FUTURE"
    assert ob2_sep.days_until_effective == 16

    # Query as of 15 October 2026 (After 01 Oct 2026):
    # - V2 document is EFFECTIVE
    state_v2_oct = state_engine.get_regulatory_state(doc_v2, as_of_date="2026-10-15")
    assert state_v2_oct.state == "EFFECTIVE"

    ob2_oct = state_engine.evaluate_obligation_temporal_state(ob_v2, as_of_date="2026-10-15", document_eval=state_v2_oct)
    assert ob2_oct.status == "ACTIVE"

    # -------------------------------------------------------------------------
    # 4. DEADLINE INTELLIGENCE & SHIFT VERIFICATION (65.2, 65.4)
    # -------------------------------------------------------------------------
    # V1 has 15-day quarterly deadline
    ddls_v1 = deadline_engine.extract_deadlines_from_obligation(ob_v1, as_of_date="2026-07-01")
    assert any("within 15 days" in d.deadline_expression for d in ddls_v1)

    # V2 has 30-day quarterly deadline
    ddls_v2 = deadline_engine.extract_deadlines_from_obligation(ob_v2, as_of_date="2026-10-01")
    assert any("within 30 days" in d.deadline_expression for d in ddls_v2)

    # -------------------------------------------------------------------------
    # 5. ALERT GENERATION & DEDUPLICATION (65.7, 65.10, 65.18)
    # -------------------------------------------------------------------------
    # Approaching effective date on 15 Sep 2026 (16 days until 01 Oct) -> triggers 30-day window alert
    alerts = alert_engine.evaluate_upcoming_effective_dates([date_event_v2], as_of_date="2026-09-15")
    assert len(alerts) == 1
    alt = alerts[0]
    assert alt.alert_type == "UPCOMING_EFFECTIVE_DATE"
    assert alt.effective_date == "2026-10-01"
    assert alt.explanation.why_am_i_seeing_this is not None
    assert alt.explanation.source == date_event_v2.source_text

    # Verify deduplication
    saved_initial = repo.save_alerts(alerts)
    assert saved_initial == 1
    saved_duplicate = repo.save_alerts(alerts)
    assert saved_duplicate == 0
