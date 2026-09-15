"""
Unit tests for AlertEngine and Deduplication (Phase 65.5, 65.6, 65.7, 65.8, 65.10, 65.18, 65.19).
"""

import pytest
from app.compliance.alert_engine import AlertEngine, get_alert_engine, make_dedup_hash
from app.compliance.alert_models import RegulatoryDeadline, Watchlist
from app.compliance.temporal_models import RegulatoryDateEvent
from app.compliance.models import ComplianceChecklist, ChecklistItem
from app.compliance.repository import get_compliance_repository

repo = get_compliance_repository()


@pytest.fixture
def engine():
    return get_alert_engine()


def test_upcoming_effective_date_alert_generation(engine):
    # Regulatory change effective in 6 days (relative to 2026-09-15)
    ev = RegulatoryDateEvent(
        event_id="rde_a1",
        document_id="doc_new_reg",
        event_type="EFFECTIVE",
        date="2026-09-21",
        source_text="shall come into effect from 21 September 2026"
    )

    alerts = engine.evaluate_upcoming_effective_dates([ev], as_of_date="2026-09-15")
    assert len(alerts) == 1
    alt = alerts[0]
    assert alt.alert_type == "UPCOMING_EFFECTIVE_DATE"
    assert alt.severity == "MEDIUM"
    assert "in 6 days" in alt.title
    assert alt.explanation.when_effective == "2026-09-21"
    assert alt.explanation.why_am_i_seeing_this is not None


def test_approaching_deadline_alert_generation(engine):
    # Deadline due in 2 days (relative to 2026-09-15)
    ddl = RegulatoryDeadline(
        deadline_id="ddl_a1",
        obligation_id="ob_a1",
        requirement_id="req_a1",
        document_id="doc_rep",
        deadline_type="ABSOLUTE",
        deadline_expression="by 17 September 2026",
        due_date="2026-09-17",
        source_evidence="File report by 17 September 2026."
    )

    alerts = engine.evaluate_upcoming_deadlines([ddl], as_of_date="2026-09-15")
    assert len(alerts) == 1
    alt = alerts[0]
    assert alt.alert_type == "COMPLIANCE_DEADLINE"
    assert alt.severity == "HIGH"
    assert "in 2 days" in alt.title
    assert alt.explanation.action_recommended is not None


def test_alert_deduplication(engine):
    import uuid
    # Verify that saving identical alerts deduplicates them based on dedup_hash
    test_id = f"rde_dedup_{uuid.uuid4().hex[:8]}"
    ev = RegulatoryDateEvent(
        event_id=test_id,
        document_id="doc_dedup",
        event_type="EFFECTIVE",
        date="2026-09-20",
        source_text="effective 20 September 2026"
    )

    alerts_run_1 = engine.evaluate_upcoming_effective_dates([ev], as_of_date="2026-09-15")
    assert len(alerts_run_1) == 1

    # Save first batch
    saved_1 = repo.save_alerts(alerts_run_1)
    assert saved_1 >= 1

    # Run second batch with identical input
    alerts_run_2 = engine.evaluate_upcoming_effective_dates([ev], as_of_date="2026-09-15")
    saved_2 = repo.save_alerts(alerts_run_2)
    # Deduplication MUST prevent duplicate persistence!
    assert saved_2 == 0


def test_checklist_impact_alert(engine):
    chk = ComplianceChecklist(
        checklist_id="chk_imp_01",
        title="Portfolio Manager Operations Review",
        document_ids=["doc_pm_2024"],
        items=[
            ChecklistItem(
                item_id="it_imp_01",
                obligation_id="ob_imp_01",
                requirement_id="req_imp_01",
                document_id="doc_pm_2024",
                control_question="Are asset segregation norms maintained?",
                compliance_action="Maintain segregated custody accounts."
            )
        ]
    )

    alert = engine.evaluate_checklist_impact_alerts(
        checklist=chk,
        changed_document_id="doc_pm_2024",
        effective_date="2026-10-01",
        as_of_date="2026-09-15"
    )
    assert alert is not None
    assert alert.alert_type == "CHECKLIST_IMPACT"
    assert "1 Checklist Items Affected" in alert.title
    assert alert.explanation.action_recommended is not None
