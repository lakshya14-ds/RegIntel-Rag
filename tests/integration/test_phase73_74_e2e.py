"""
End-to-End Integration Test for Phases 73–74: Cross-Regulator Overlap & Conflict Intelligence.

Demonstrates complete multi-regulator compliance lifecycle:
1. Multi-Regulator Requirement Ingestion (SEBI, RBI, IRDAI, IFSCA)
2. Phase 73 Overlap Candidate Generation & Deterministic Verification
3. Provenance & Snippet Tracking (Left vs Right)
4. Phase 74 Conflict & Inconsistency Detection (Parameter & Deadline Mismatches)
5. Human Review Workflow & Audit Trail Recording
6. Query & Inspection through REST APIs
"""

import uuid
import pytest
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
    ConflictResolutionStatus,
)
from app.compliance.overlap_engine import OverlapEngine
from app.compliance.conflict_engine import ConflictEngine
from app.compliance.repository import ComplianceRepository


@pytest.fixture
def client():
    return TestClient(app)


def test_cross_regulator_overlap_and_conflict_lifecycle(client):
    """Executes full end-to-end multi-regulator overlap and conflict pipeline."""
    repo = ComplianceRepository()
    overlap_engine = OverlapEngine()
    conflict_engine = ConflictEngine()

    run_id = uuid.uuid4().hex[:6]

    # Step 1: Create requirements across 4 different regulatory authorities
    req_sebi_records = RegulatoryRequirement(
        requirement_id=f"req_sebi_rec_{run_id}",
        document_id=f"sebi_doc_{run_id}",
        authority="SEBI",
        section_id="sec_6_records",
        requirement_text="All registered intermediaries shall maintain and preserve books of accounts and client records for a minimum duration of 8 years.",
        source_evidence="Intermediaries shall maintain books of accounts for 8 years.",
        requirement_type="RECORD_KEEPING",
        action="preserve",
        object="records",
        subject="regulated financial entities",
        thresholds=[RequirementThreshold(parameter_type="duration", raw_value="8 years", normalized_value=8.0, unit="years")]
    )

    req_rbi_records = RegulatoryRequirement(
        requirement_id=f"req_rbi_rec_{run_id}",
        document_id=f"rbi_doc_{run_id}",
        authority="RBI",
        section_id="sec_18_records",
        requirement_text="Regulated entities and scheduled commercial banks shall preserve customer account books and records for at least 5 years.",
        source_evidence="Banks shall preserve customer account books for 5 years.",
        requirement_type="RECORD_KEEPING",
        action="preserve",
        object="records",
        subject="regulated financial entities",
        thresholds=[RequirementThreshold(parameter_type="duration", raw_value="5 years", normalized_value=5.0, unit="years")]
    )

    req_irdai_cyber = RegulatoryRequirement(
        requirement_id=f"req_irdai_cyber_{run_id}",
        document_id=f"irdai_doc_{run_id}",
        authority="IRDAI",
        section_id="sec_4_cyber",
        requirement_text="Insurers must report all critical cybersecurity incidents to CERT-In and IRDAI within 6 hours.",
        source_evidence="Report cybersecurity incidents within 6 hours.",
        requirement_type="REPORTING",
        action="report",
        object="cybersecurity incidents",
        subject="regulated tech entities",
        deadline="6 hours",
        thresholds=[RequirementThreshold(parameter_type="duration", raw_value="6 hours", normalized_value=6.0, unit="hours")]
    )

    req_ifsca_cyber = RegulatoryRequirement(
        requirement_id=f"req_ifsca_cyber_{run_id}",
        document_id=f"ifsca_doc_{run_id}",
        authority="IFSCA",
        section_id="sec_11_cyber",
        requirement_text="Finance companies operating in IFSC shall report security breaches and incidents to CSIRT-IFSC within 2 hours.",
        source_evidence="Report security breaches to CSIRT-IFSC within 2 hours.",
        requirement_type="REPORTING",
        action="report",
        object="cybersecurity incidents",
        subject="regulated tech entities",
        deadline="2 hours",
        thresholds=[RequirementThreshold(parameter_type="duration", raw_value="2 hours", normalized_value=2.0, unit="hours")]
    )

    all_reqs = [req_sebi_records, req_rbi_records, req_irdai_cyber, req_ifsca_cyber]

    # Step 2: Overlap Candidate Generation & Analysis for SEBI records
    candidates = overlap_engine.generate_candidates_for_requirement(
        req_sebi_records,
        all_reqs,
        min_deterministic_score=0.20
    )

    assert len(candidates) >= 1
    matched_candidate, sim_score, matched_topic = candidates[0]
    assert matched_candidate.authority == "RBI"
    assert matched_topic == "RECORD_KEEPING"

    # Analyze pair
    overlap_records = overlap_engine.analyze_pair(req_sebi_records, matched_candidate, use_llm=False)
    assert overlap_records is not None
    assert overlap_records.left_authority == "SEBI"
    assert overlap_records.right_authority == "RBI"
    assert overlap_records.status == "ACTIVE"
    assert overlap_records.parameter_comparison["values_differ"] is True

    # Also analyze IRDAI vs IFSCA cyber reporting
    overlap_cyber = overlap_engine.analyze_pair(req_irdai_cyber, req_ifsca_cyber, use_llm=False)
    assert overlap_cyber is not None
    assert overlap_cyber.shared_topic == "CYBERSECURITY"
    assert overlap_cyber.left_authority == "IRDAI"
    assert overlap_cyber.right_authority == "IFSCA"

    # Persist overlaps
    repo.save_overlaps([overlap_records, overlap_cyber])

    # Step 3: Conflict & Inconsistency Detection
    rec_conflict = conflict_engine.detect_conflicts_from_overlap(
        overlap_records, req_sebi_records, req_rbi_records, use_llm=False
    )
    assert rec_conflict is not None
    assert rec_conflict.conflict_type == "PARAMETER_CONFLICT"
    assert rec_conflict.left_authority == "SEBI"
    assert rec_conflict.right_authority == "RBI"
    assert rec_conflict.resolution_status == "OPEN"
    assert "8 years" in rec_conflict.explanation and "5 years" in rec_conflict.explanation

    cyber_conflict = conflict_engine.detect_conflicts_from_overlap(
        overlap_cyber, req_irdai_cyber, req_ifsca_cyber, use_llm=False
    )
    assert cyber_conflict is not None
    assert cyber_conflict.conflict_type in ["PARAMETER_CONFLICT", "DEADLINE_CONFLICT"]

    # Persist conflicts
    repo.save_conflicts([rec_conflict, cyber_conflict])

    # Step 4: Human Review Workflow Execution
    # Update status to UNDER_REVIEW
    reviewed = repo.update_conflict_status(
        conflict_id=rec_conflict.conflict_id,
        new_status="UNDER_REVIEW",
        reviewer_id="ComplianceDirector",
        notes="Reconciling record retention timeline across dual-regulated NBFC-broker entities."
    )
    assert reviewed.resolution_status == "UNDER_REVIEW"
    assert len(reviewed.review_history) == 1

    # Update status to RESOLVED
    resolved = repo.update_conflict_status(
        conflict_id=rec_conflict.conflict_id,
        new_status="RESOLVED",
        reviewer_id="GeneralCounsel",
        notes="Adopted highest-standard rule: maintain all records for 8 years."
    )
    assert resolved.resolution_status == "RESOLVED"
    assert len(resolved.review_history) == 2

    # Step 5: Verify REST API Exposure
    # 1. Overlaps API
    resp_ovl = client.get("/api/regulatory-overlaps?topic=RECORD_KEEPING")
    assert resp_ovl.status_code == 200
    ovl_data = resp_ovl.json()
    assert isinstance(ovl_data, list)
    assert any(o["overlap_id"] == overlap_records.overlap_id for o in ovl_data)

    # 2. Detail Overlap API
    resp_ovl_detail = client.get(f"/api/regulatory-overlaps/{overlap_records.overlap_id}")
    assert resp_ovl_detail.status_code == 200
    assert resp_ovl_detail.json()["shared_topic"] == "RECORD_KEEPING"

    # 3. Conflicts API
    resp_cnf = client.get("/api/regulatory-conflicts?conflict_type=PARAMETER_CONFLICT")
    assert resp_cnf.status_code == 200
    cnf_data = resp_cnf.json()
    assert isinstance(cnf_data, list)
    assert any(c["conflict_id"] == rec_conflict.conflict_id for c in cnf_data)

    # 4. Patch Conflict Status API
    resp_patch = client.patch(
        f"/api/regulatory-conflicts/{cyber_conflict.conflict_id}/status",
        json={
            "new_status": "FALSE_POSITIVE",
            "reviewer_id": "GIFT_Compliance_Lead",
            "notes": "Entity operates strictly under IFSC jurisdiction; IRDAI notification not triggered."
        }
    )
    assert resp_patch.status_code == 200
    patched = resp_patch.json()
    assert patched["resolution_status"] == "FALSE_POSITIVE"
    assert len(patched["review_history"]) == 1
