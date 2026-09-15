"""
Unit tests for Compliance Intelligence REST APIs (Phases 61, 62, 63).
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ComplianceChecklist,
    ChecklistItem,
)
from app.compliance.repository import get_compliance_repository

client = TestClient(app)
repo = get_compliance_repository()


@pytest.fixture(autouse=True)
def setup_compliance_data():
    req = RegulatoryRequirement(
        requirement_id="req_api_01",
        document_id="doc_api_test",
        requirement_text="The investment adviser shall submit quarterly audit reports within 15 days.",
        source_evidence="The investment adviser shall submit quarterly audit reports within 15 days.",
        subject="Investment Adviser",
        action="submit",
        object="quarterly audit reports",
        deadline="within 15 days",
        frequency="QUARTERLY"
    )
    ob = RegulatoryObligation(
        obligation_id="ob_api_01",
        requirement_id="req_api_01",
        document_id="doc_api_test",
        obligated_party="Investment Adviser",
        obligation_action="submit",
        obligation_object="quarterly audit reports",
        deadline="within 15 days",
        frequency="QUARTERLY",
        source_evidence="The investment adviser shall submit quarterly audit reports within 15 days."
    )
    chk = ComplianceChecklist(
        checklist_id="chk_api_01",
        title="IA Audit Checklist",
        document_ids=["doc_api_test"],
        items=[
            ChecklistItem(
                item_id="item_api_01",
                obligation_id="ob_api_01",
                requirement_id="req_api_01",
                document_id="doc_api_test",
                control_question="Does the IA submit quarterly reports within 15 days?",
                compliance_action="Submit reports within 15 days."
            )
        ]
    )
    repo.save_requirements([req])
    repo.save_obligations([ob])
    repo.save_checklist(chk)


def test_get_requirements_api():
    resp = client.get("/requirements?document_id=doc_api_test")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["requirement_id"] == "req_api_01"


def test_get_requirement_by_id_api():
    resp = client.get("/requirements/req_api_01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject"] == "Investment Adviser"
    assert data["frequency"] == "QUARTERLY"


def test_get_obligations_api():
    resp = client.get("/obligations?document_id=doc_api_test")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["obligation_id"] == "ob_api_01"


def test_get_obligation_by_id_api():
    resp = client.get("/obligations/ob_api_01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["obligated_party"] == "Investment Adviser"


def test_get_checklists_api():
    resp = client.get("/compliance/checklists")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(c["checklist_id"] == "chk_api_01" for c in data)


def test_patch_checklist_item_status_api():
    resp = client.patch(
        "/compliance/checklists/chk_api_01/items/item_api_01",
        json={"status": "COMPLIANT", "notes": "Audited and verified."}
    )
    assert resp.status_code == 200
    data = resp.json()
    item = next(it for it in data["items"] if it["item_id"] == "item_api_01")
    assert item["status"] == "COMPLIANT"
    assert item["notes"] == "Audited and verified."
    assert data["completion_rate"] == 100.0


def test_export_checklist_api():
    resp_md = client.get("/compliance/checklists/chk_api_01/export?format=markdown")
    assert resp_md.status_code == 200
    assert "text/markdown" in resp_md.headers["content-type"]
    assert "# Regulatory Compliance Checklist" in resp_md.text

    resp_json = client.get("/compliance/checklists/chk_api_01/export?format=json")
    assert resp_json.status_code == 200
    assert "application/json" in resp_json.headers["content-type"]
    assert "chk_api_01" in resp_json.json()["checklist_id"]


def test_checklist_traceability_api():
    resp = client.get("/compliance/checklists/chk_api_01/traceability/item_api_01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["obligation_id"] == "ob_api_01"
    assert data["requirement_id"] == "req_api_01"


def test_requirement_temporal_state_api():
    resp = client.get("/requirements/req_api_01/state?as_of=2026-09-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requirement_id"] == "req_api_01"
    assert "is_active" in data
    assert "state" in data


def test_obligation_temporal_state_api():
    resp = client.get("/obligations/ob_api_01/state?as_of=2026-09-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["obligation_id"] == "ob_api_01"
    assert "status" in data


def test_checklist_temporal_state_api():
    resp = client.get("/compliance/checklists/chk_api_01/temporal-state?as_of=2026-09-15")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["item_id"] == "item_api_01"


def test_regulatory_calendar_and_upcoming_api():
    from app.compliance.temporal_models import RegulatoryDateEvent
    ev = RegulatoryDateEvent(
        event_id="rde_cal_01",
        document_id="doc_cal_test",
        event_type="EFFECTIVE",
        date="2026-09-20",
        source_text="effective 20 September 2026",
        derivation_type="EXPLICIT"
    )
    repo.save_date_events([ev])

    # Test upcoming
    resp_up = client.get("/regulatory-events/upcoming?days=30&as_of=2026-09-15")
    assert resp_up.status_code == 200
    data_up = resp_up.json()
    assert any(e["event_id"] == "rde_cal_01" for e in data_up)

    # Test calendar
    resp_cal = client.get("/regulatory-events/calendar?start_date=2026-09-01&end_date=2026-09-30")
    assert resp_cal.status_code == 200
    data_cal = resp_cal.json()
    assert any(e["event_id"] == "rde_cal_01" for e in data_cal)


def test_alerts_api():
    import uuid
    from app.compliance.alert_models import RegulatoryAlert, AlertExplanation
    alt_id = f"alt_api_{uuid.uuid4().hex[:8]}"
    dedup_val = f"hash_api_{uuid.uuid4().hex[:8]}"
    alt = RegulatoryAlert(
        alert_id=alt_id,
        dedup_hash=dedup_val,
        alert_type="UPCOMING_EFFECTIVE_DATE",
        severity="HIGH",
        title="Upcoming Regulatory Change",
        message="Document doc_api_test becomes effective on 2026-10-01.",
        trigger_date="2026-09-15",
        effective_date="2026-10-01",
        explanation=AlertExplanation(
            why_am_i_seeing_this="Regulation becomes effective in 16 days.",
            when_effective="2026-10-01"
        )
    )
    repo.save_alerts([alt])

    # List
    resp_list = client.get("/alerts")
    assert resp_list.status_code == 200
    alerts = resp_list.json()
    assert any(a["alert_id"] == alt_id for a in alerts)

    # Get by ID
    resp_get = client.get(f"/alerts/{alt_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["alert_id"] == alt_id
    assert resp_get.json()["explanation"]["why_am_i_seeing_this"] is not None

    # Mark read
    resp_read = client.post(f"/alerts/{alt_id}/read")
    assert resp_read.status_code == 200
    assert resp_read.json()["status"] == "READ"

    # Dismiss
    resp_dismiss = client.post(f"/alerts/{alt_id}/dismiss")
    assert resp_dismiss.status_code == 200
    assert resp_dismiss.json()["status"] == "DISMISSED"


def test_deadlines_api():
    from app.compliance.alert_models import RegulatoryDeadline
    ddl = RegulatoryDeadline(
        deadline_id="ddl_api_01",
        obligation_id="ob_api_01",
        document_id="doc_api_test",
        deadline_expression="within 15 days",
        due_date="2026-09-25",
        source_evidence="File report within 15 days."
    )
    repo.save_deadlines([ddl])

    resp = client.get("/deadlines?document_id=doc_api_test")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(d["deadline_id"] == "ddl_api_01" for d in data)


def test_watchlists_api():
    payload = {
        "name": "Custody Watchlist",
        "authorities": ["SEBI"],
        "document_ids": ["doc_api_test"]
    }
    resp_post = client.post("/watchlists", json=payload)
    assert resp_post.status_code == 200
    created = resp_post.json()
    assert created["name"] == "Custody Watchlist"
    w_id = created["watchlist_id"]

    resp_list = client.get("/watchlists")
    assert resp_list.status_code == 200
    assert any(w["watchlist_id"] == w_id for w in resp_list.json())

    resp_get = client.get(f"/watchlists/{w_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["watchlist_id"] == w_id


def test_run_alert_evaluation_job_api():
    resp = client.post("/jobs/run-alert-evaluation?as_of=2026-09-15")
    assert resp.status_code == 200
    res = resp.json()
    assert "date_events_evaluated" in res
    assert "alert_candidates_generated" in res


