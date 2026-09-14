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
