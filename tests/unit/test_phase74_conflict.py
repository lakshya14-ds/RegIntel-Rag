"""
Phase 74 Unit Test Suite: Cross-Regulator Conflict & Consistency Detection Engine.

Validates:
- 74.1: RegulatoryConflict models, severity levels, types, and resolution workflows
- 74.2: Parameter conflicts (e.g. 5-year vs 8-year record retention)
- 74.3: Action/Prohibition conflicts (mandate vs prohibition)
- 74.4: Deadline & frequency conflicts (30 days vs 7 days; quarterly vs monthly)
- 74.5: Human review status updates and audit trail logging
- 74.6: REST API endpoints for conflict discovery, inspection, and review status patching
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.connectors.authority import RegulatoryAuthority
from app.compliance.models import RegulatoryRequirement, RequirementThreshold
from app.compliance.overlap_models import (
    RegulatoryOverlap,
    OverlapType,
    OverlapConfidence,
    OverlapStatus,
)
from app.compliance.conflict_models import (
    RegulatoryConflict,
    RegulatoryConflictType,
    ConflictSeverity,
    ConflictConfidence,
    ConflictResolutionStatus,
)
from app.compliance.conflict_engine import ConflictEngine
from app.compliance.repository import ComplianceRepository


@pytest.fixture
def test_client():
    return TestClient(app)


def test_regulatory_conflict_model():
    """Verifies RegulatoryConflict creation, fields, and audit history."""
    conflict = RegulatoryConflict(
        conflict_id="cnf_test_01",
        overlap_id="ovl_test_01",
        conflict_type="PARAMETER_CONFLICT",
        severity="MEDIUM",
        confidence="HIGH",
        resolution_status="OPEN",
        left_authority="SEBI",
        left_requirement_id="req_sebi_rec",
        left_document_id="sebi_doc",
        left_section_id="sec_1",
        right_authority="RBI",
        right_requirement_id="req_rbi_rec",
        right_document_id="rbi_doc",
        right_section_id="sec_2",
        conflicting_fields=["threshold", "parameter"],
        left_value={"duration": "8 years"},
        right_value={"duration": "5 years"},
        evidence_left="Maintain customer records for 8 years.",
        evidence_right="Maintain customer records for 5 years.",
        explanation="Parameter mismatch: 8 years vs 5 years.",
    )

    assert conflict.conflict_id == "cnf_test_01"
    assert conflict.severity == "MEDIUM"
    assert conflict.conflict_type == "PARAMETER_CONFLICT"
    assert conflict.resolution_status == "OPEN"
    assert len(conflict.review_history) == 0


def test_parameter_conflict_detection():
    """Tests automatic detection of numeric parameter discrepancies in overlapping requirements."""
    engine = ConflictEngine()

    overlap = RegulatoryOverlap(
        overlap_id="ovl_param_mismatch",
        shared_topic="RECORD_KEEPING",
        left_requirement_id="req_sebi_01",
        left_authority="SEBI",
        left_document_id="sebi_doc",
        left_section_id="s1",
        right_requirement_id="req_irdai_01",
        right_authority="IRDAI",
        right_document_id="irdai_doc",
        right_section_id="s5",
        relationship_type="OVERLAPPING",
        confidence="HIGH",
        evidence_left="Maintain customer records for 8 years.",
        evidence_right="Keep customer files for 5 years.",
        parameter_comparison={
            "has_shared_parameters": True,
            "values_differ": True,
            "shared_parameter_types": ["duration"],
            "details": [{
                "parameter_type": "duration",
                "left_raw": "8 years",
                "left_normalized": 8.0,
                "right_raw": "5 years",
                "right_normalized": 5.0,
                "unit": "years",
                "values_differ": True
            }]
        },
        applicability_match="SAME_ENTITIES"
    )

    req_left = RegulatoryRequirement(
        requirement_id="req_sebi_01",
        document_id="sebi_doc",
        authority="SEBI",
        section_id="s1",
        requirement_text="Maintain customer records for 8 years.",
        source_evidence="Maintain customer records for 8 years.",
        requirement_type="RECORD_KEEPING",
        thresholds=[RequirementThreshold(parameter_type="duration", raw_value="8 years", normalized_value=8.0, unit="years")]
    )

    req_right = RegulatoryRequirement(
        requirement_id="req_irdai_01",
        document_id="irdai_doc",
        authority="IRDAI",
        section_id="s5",
        requirement_text="Keep customer files for 5 years.",
        source_evidence="Keep customer files for 5 years.",
        requirement_type="RECORD_KEEPING",
        thresholds=[RequirementThreshold(parameter_type="duration", raw_value="5 years", normalized_value=5.0, unit="years")]
    )

    conflict = engine.detect_conflicts_from_overlap(overlap, req_left, req_right, use_llm=False)
    assert conflict is not None
    assert conflict.conflict_type == "PARAMETER_CONFLICT"
    assert conflict.severity in ["MEDIUM", "LOW"]
    assert "8 years" in conflict.explanation
    assert "5 years" in conflict.explanation


def test_action_prohibition_conflict_detection():
    """Tests detection of high-severity mandate vs prohibition conflicts."""
    engine = ConflictEngine()

    overlap = RegulatoryOverlap(
        overlap_id="ovl_prohibition_clash",
        shared_topic="OUTSOURCING",
        left_requirement_id="req_sebi_cloud",
        left_authority="SEBI",
        left_document_id="sebi_cloud_framework",
        left_section_id="sec_8",
        right_requirement_id="req_ifsca_cloud",
        right_authority="IFSCA",
        right_document_id="ifsca_tech_reg",
        right_section_id="sec_15",
        relationship_type="OVERLAPPING",
        confidence="HIGH",
        evidence_left="Entities must not outsource core risk assessment functions.",
        evidence_right="Entities are permitted to outsource risk assessment.",
        applicability_match="SAME_ENTITIES"
    )

    req_left = RegulatoryRequirement(
        requirement_id="req_sebi_cloud",
        document_id="sebi_cloud_framework",
        authority="SEBI",
        section_id="sec_8",
        requirement_text="Entities must not outsource core risk assessment functions to foreign service providers.",
        source_evidence="Must not outsource core risk assessment.",
        requirement_type="PROHIBITION",
        action="outsource",
        object="core risk assessment functions",
        subject="entities",
    )

    req_right = RegulatoryRequirement(
        requirement_id="req_ifsca_cloud",
        document_id="ifsca_tech_reg",
        authority="IFSCA",
        section_id="sec_15",
        requirement_text="Entities are permitted to outsource core risk assessment functions to foreign service providers.",
        source_evidence="Entities may outsource risk assessment.",
        requirement_type="PERMISSION",
        action="outsource",
        object="core risk assessment functions",
        subject="entities",
    )

    conflict = engine.detect_conflicts_from_overlap(overlap, req_left, req_right, use_llm=False)
    assert conflict is not None
    assert conflict.conflict_type in ["PROHIBITION_CONFLICT", "ACTION_CONFLICT"]
    assert conflict.severity == "HIGH"


def test_deadline_conflict_detection():
    """Tests detection of deadline or filing frequency conflicts."""
    engine = ConflictEngine()

    overlap = RegulatoryOverlap(
        overlap_id="ovl_deadline_clash",
        shared_topic="REPORTING",
        left_requirement_id="req_pfrda_rep",
        left_authority="PFRDA",
        left_document_id="pfrda_cir_01",
        left_section_id="sec_3",
        right_requirement_id="req_sebi_rep",
        right_authority="SEBI",
        right_document_id="sebi_cir_02",
        right_section_id="sec_7",
        relationship_type="OVERLAPPING",
        confidence="HIGH",
        evidence_left="Submit compliance report within 15 days.",
        evidence_right="Submit compliance report within 30 days.",
        applicability_match="SAME_ENTITIES"
    )

    req_left = RegulatoryRequirement(
        requirement_id="req_pfrda_rep",
        document_id="pfrda_cir_01",
        authority="PFRDA",
        section_id="sec_3",
        requirement_text="Submit compliance report within 15 days.",
        source_evidence="Submit compliance report within 15 days.",
        requirement_type="REPORTING",
        action="submit",
        deadline="15 days",
    )

    req_right = RegulatoryRequirement(
        requirement_id="req_sebi_rep",
        document_id="sebi_cir_02",
        authority="SEBI",
        section_id="sec_7",
        requirement_text="Submit compliance report within 30 days.",
        source_evidence="Submit compliance report within 30 days.",
        requirement_type="REPORTING",
        action="submit",
        deadline="30 days",
    )

    conflict = engine.detect_conflicts_from_overlap(overlap, req_left, req_right, use_llm=False)
    assert conflict is not None
    assert conflict.conflict_type == "DEADLINE_CONFLICT"
    assert "15 days" in conflict.explanation and "30 days" in conflict.explanation


def test_human_review_status_lifecycle():
    """Validates status transition and audit history recording in repository."""
    repo = ComplianceRepository()

    conflict = RegulatoryConflict(
        conflict_id="cnf_review_test",
        overlap_id="ovl_review_01",
        conflict_type="FREQUENCY_CONFLICT",
        severity="MEDIUM",
        confidence="HIGH",
        resolution_status="OPEN",
        left_authority="SEBI",
        left_requirement_id="req_s1",
        left_document_id="doc_s",
        left_section_id="s1",
        right_authority="RBI",
        right_requirement_id="req_r1",
        right_document_id="doc_r",
        right_section_id="s2",
        evidence_left="Annual audit required",
        evidence_right="Semi-annual audit required",
        explanation="Frequency discrepancy",
    )
    repo.save_conflicts([conflict])

    # 1. Update status to UNDER_REVIEW
    updated = repo.update_conflict_status(
        conflict_id="cnf_review_test",
        new_status="UNDER_REVIEW",
        reviewer_id="ChiefComplianceOfficer",
        notes="Legal counsel reviewing applicability"
    )
    assert updated is not None
    assert updated.resolution_status == "UNDER_REVIEW"
    assert len(updated.review_history) == 1
    assert updated.review_history[0].reviewer_id == "ChiefComplianceOfficer"
    assert updated.review_history[0].new_status == "UNDER_REVIEW"

    # 2. Update status to RESOLVED
    resolved = repo.update_conflict_status(
        conflict_id="cnf_review_test",
        new_status="RESOLVED",
        reviewer_id="LegalLead",
        notes="Resolution strategy adopted: follow higher frequency semi-annual audit"
    )
    assert resolved.resolution_status == "RESOLVED"
    assert len(resolved.review_history) == 2


def test_conflict_api_endpoints(test_client):
    """Tests REST endpoints for conflict query, detail, and PATCH status workflow."""
    repo = ComplianceRepository()
    test_conflict = RegulatoryConflict(
        conflict_id="cnf_api_route_test",
        overlap_id="ovl_api_01",
        conflict_type="PARAMETER_CONFLICT",
        severity="HIGH",
        confidence="HIGH",
        resolution_status="OPEN",
        left_authority="SEBI",
        left_requirement_id="req_sebi_cyber",
        left_document_id="sebi_cyber_doc",
        left_section_id="sec_1",
        right_authority="RBI",
        right_requirement_id="req_rbi_cyber",
        right_document_id="rbi_cyber_doc",
        right_section_id="sec_2",
        evidence_left="Report cyber incident within 6 hours of detection.",
        evidence_right="Report security incident within 2 hours of detection.",
        explanation="Incident reporting window discrepancy: 6h vs 2h.",
    )
    repo.save_conflicts([test_conflict])

    # 1. GET list with severity filter
    resp = test_client.get("/api/regulatory-conflicts?severity=HIGH")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(c["conflict_id"] == "cnf_api_route_test" for c in data)

    # 2. GET detail
    resp_detail = test_client.get("/api/regulatory-conflicts/cnf_api_route_test")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["conflict_id"] == "cnf_api_route_test"
    assert detail["severity"] == "HIGH"

    # 3. PATCH status
    patch_payload = {
        "new_status": "UNDER_REVIEW",
        "reviewer_id": "ComplianceOfficer01",
        "notes": "Escalated to CISO and Legal team for reconciliation"
    }
    resp_patch = test_client.patch("/api/regulatory-conflicts/cnf_api_route_test/status", json=patch_payload)
    assert resp_patch.status_code == 200
    patched_data = resp_patch.json()
    assert patched_data["resolution_status"] == "UNDER_REVIEW"
    assert len(patched_data["review_history"]) >= 1
