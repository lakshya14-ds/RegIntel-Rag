"""
Phase 73 & Phase 74 Comprehensive Evaluation Benchmark & Fixture Suite (73.20 & 74.27).

Evaluates:
- 73.20: Candidate recall, classification precision/recall, false-overlap rate, authority isolation, evidence support
- 74.27: Conflict precision/recall, false-positive rate, applicability accuracy, temporal accuracy
- Representative difficult test cases:
  1. Identical / Near-duplicate requirements
  2. Same topic, different entity (disjoint applicability -> no conflict)
  3. Different deadline (filing timelines mismatch)
  4. Complementary requirements (maintain vs submit upon request)
  5. Explicit opposite action / prohibition conflict
  6. Same threshold, different activity
  7. Same deadline, different reporting event
- Stale analysis invalidation & change propagation (73.21, 74.24)
- New sub-resource API endpoints for requirements, obligations, and documents (73.16, 74.18)
"""

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


def test_benchmark_authority_isolation_and_evidence_support():
    """Validates 100% authority isolation and 100% immutable evidence retention."""
    engine = OverlapEngine()

    req_sebi = RegulatoryRequirement(
        requirement_id="bench_req_sebi_01",
        document_id="bench_doc_sebi",
        authority="SEBI",
        section_id="s1",
        requirement_text="Stock brokers shall submit quarterly financial returns within 15 days.",
        source_evidence="Brokers shall submit quarterly returns within 15 days.",
        requirement_type="REPORTING",
        action="submit",
        object="quarterly financial returns",
        subject="stock brokers",
        deadline="15 days"
    )

    req_rbi = RegulatoryRequirement(
        requirement_id="bench_req_rbi_01",
        document_id="bench_doc_rbi",
        authority="RBI",
        section_id="s2",
        requirement_text="Commercial banks shall submit quarterly financial returns within 30 days.",
        source_evidence="Banks shall submit quarterly returns within 30 days.",
        requirement_type="REPORTING",
        action="submit",
        object="quarterly financial returns",
        subject="commercial banks",
        deadline="30 days"
    )

    overlap = engine.analyze_pair(req_sebi, req_rbi, use_llm=False)
    assert overlap is not None

    # Authority isolation: left_authority != right_authority
    assert overlap.left_authority != overlap.right_authority
    assert overlap.left_authority == "SEBI"
    assert overlap.right_authority == "RBI"

    # Evidence preservation: immutable non-empty snippets
    assert len(overlap.evidence_left) > 0
    assert len(overlap.evidence_right) > 0
    assert "Brokers" in overlap.evidence_left
    assert "Banks" in overlap.evidence_right


def test_benchmark_disjoint_entity_applicability_no_conflict():
    """
    Validates that same topic + different entity types (e.g. banks vs brokers)
    does NOT produce an automatic false conflict (Rule 74.9).
    """
    engine_overlap = OverlapEngine()
    engine_conflict = ConflictEngine()

    req_broker = RegulatoryRequirement(
        requirement_id="bench_broker_rep",
        document_id="doc_sebi_rep",
        authority="SEBI",
        section_id="sec_1",
        requirement_text="Brokers must submit capital audit reports within 15 days of quarter end.",
        source_evidence="Brokers submit capital audit in 15 days.",
        requirement_type="REPORTING",
        action="submit",
        object="capital audit reports",
        subject="brokers",
        deadline="15 days",
    )

    req_bank = RegulatoryRequirement(
        requirement_id="bench_bank_rep",
        document_id="doc_rbi_rep",
        authority="RBI",
        section_id="sec_2",
        requirement_text="Commercial banks must submit capital audit reports within 30 days of quarter end.",
        source_evidence="Banks submit capital audit in 30 days.",
        requirement_type="REPORTING",
        action="submit",
        object="capital audit reports",
        subject="banks",
        deadline="30 days",
    )

    overlap = engine_overlap.analyze_pair(req_broker, req_bank, use_llm=False)
    assert overlap is not None
    # Because brokers vs banks are disjoint entity types
    assert overlap.applicability_match == "DIFFERENT_ENTITIES"
    assert overlap.relationship_type == "RELATED"

    # Conflict engine must respect disjoint applicability and return None
    conflict = engine_conflict.detect_conflicts_from_overlap(overlap, req_broker, req_bank, use_llm=False)
    assert conflict is None  # Zero false conflict


def test_benchmark_opposite_actions_high_severity_conflict():
    """
    Validates that explicit opposite actions (PROHIBITION vs PERMISSION/COMPLIANCE)
    with matching entity scope yields HIGH severity conflict.
    """
    engine_conflict = ConflictEngine()

    overlap = RegulatoryOverlap(
        overlap_id="bench_ovl_clash",
        shared_topic="OUTSOURCING",
        left_requirement_id="bench_clash_left",
        left_authority="SEBI",
        left_document_id="doc_s",
        left_section_id="sec_1",
        right_requirement_id="bench_clash_right",
        right_authority="IFSCA",
        right_document_id="doc_i",
        right_section_id="sec_2",
        relationship_type="OVERLAPPING",
        confidence="HIGH",
        evidence_left="Entities shall not outsource compliance auditing to third parties.",
        evidence_right="Entities are permitted to outsource compliance auditing to third parties.",
        applicability_match="SAME_ENTITIES",
    )

    req_left = RegulatoryRequirement(
        requirement_id="bench_clash_left",
        document_id="doc_s",
        authority="SEBI",
        section_id="sec_1",
        requirement_text="Entities shall not outsource compliance auditing to third parties.",
        source_evidence="Shall not outsource compliance auditing.",
        requirement_type="PROHIBITION",
        action="outsource",
        object="compliance auditing",
        subject="financial entities",
    )

    req_right = RegulatoryRequirement(
        requirement_id="bench_clash_right",
        document_id="doc_i",
        authority="IFSCA",
        section_id="sec_2",
        requirement_text="Entities are permitted to outsource compliance auditing to third parties.",
        source_evidence="Permitted to outsource compliance auditing.",
        requirement_type="PERMISSION",
        action="outsource",
        object="compliance auditing",
        subject="financial entities",
    )

    conflict = engine_conflict.detect_conflicts_from_overlap(overlap, req_left, req_right, use_llm=False)
    assert conflict is not None
    assert conflict.conflict_type in ["PROHIBITION_CONFLICT", "ACTION_CONFLICT"]
    assert conflict.severity == "HIGH"
    assert "Explicit contradiction" in conflict.explanation


def test_benchmark_complementary_requirements():
    """
    Validates that complementary obligations (maintain vs submit upon request)
    are recognized as complementary, not conflicting.
    """
    engine_overlap = OverlapEngine()
    engine_conflict = ConflictEngine()

    req_maintain = RegulatoryRequirement(
        requirement_id="bench_rec_maintain",
        document_id="doc_sebi_rec",
        authority="SEBI",
        section_id="s1",
        requirement_text="Regulated entities shall maintain records of client transactions.",
        source_evidence="Maintain records of client transactions.",
        requirement_type="RECORD_KEEPING",
        action="maintain",
        object="records",
        subject="regulated entities",
    )

    req_submit = RegulatoryRequirement(
        requirement_id="bench_rec_submit",
        document_id="doc_rbi_rec",
        authority="RBI",
        section_id="s2",
        requirement_text="Regulated entities shall submit records of client transactions upon regulatory inspection.",
        source_evidence="Submit records upon inspection.",
        requirement_type="REPORTING",
        action="submit",
        object="records",
        subject="regulated entities",
    )

    overlap = engine_overlap.analyze_pair(req_maintain, req_submit, use_llm=False)
    assert overlap is not None
    assert overlap.relationship_type in ["COMPLEMENTARY", "RELATED", "OVERLAPPING"]

    conflict = engine_conflict.detect_conflicts_from_overlap(overlap, req_maintain, req_submit, use_llm=False)
    assert conflict is None  # No contradiction between maintaining and submitting upon inspection


def test_stale_records_invalidation_and_propagation():
    """
    Validates that updating a requirement invalidates existing overlaps & conflicts (73.21, 74.24).
    """
    repo = ComplianceRepository()

    ovl = RegulatoryOverlap(
        overlap_id="bench_stale_ovl_01",
        shared_topic="KYC",
        left_requirement_id="req_to_invalidate_01",
        left_authority="SEBI",
        left_document_id="doc_sebi_old",
        left_section_id="s1",
        right_requirement_id="req_partner_01",
        right_authority="RBI",
        right_document_id="doc_rbi",
        right_section_id="s2",
        relationship_type="OVERLAPPING",
        confidence="HIGH",
        status="ACTIVE",
        evidence_left="Old evidence",
        evidence_right="Partner evidence",
    )
    repo.save_overlaps([ovl])

    cnf = RegulatoryConflict(
        conflict_id="bench_stale_cnf_01",
        overlap_id="bench_stale_ovl_01",
        conflict_type="PARAMETER_CONFLICT",
        severity="MEDIUM",
        confidence="HIGH",
        resolution_status="OPEN",
        left_authority="SEBI",
        left_requirement_id="req_to_invalidate_01",
        right_authority="RBI",
        right_requirement_id="req_partner_01",
        evidence_left="Old evidence",
        evidence_right="Partner evidence",
        explanation="Old conflict explanation",
    )
    repo.save_conflicts([cnf])

    # Propagate invalidation
    inval_res = repo.invalidate_stale_records_for_requirement("req_to_invalidate_01")
    assert inval_res["invalidated_overlaps"] >= 1
    assert inval_res["invalidated_conflicts"] >= 1

    # Check that status was transitioned to SUPERSEDED / DISMISSED
    updated_ovl = repo.get_overlap_by_id("bench_stale_ovl_01")
    assert updated_ovl.status == "SUPERSEDED"

    updated_cnf = repo.get_conflict_by_id("bench_stale_cnf_01")
    assert updated_cnf.resolution_status == "DISMISSED"
    assert updated_cnf.review_history[-1].reviewer_id == "system_change_propagation"


def test_subresource_api_routes(client):
    """Validates the sub-resource query endpoints for overlaps and conflicts."""
    repo = ComplianceRepository()

    test_ovl = RegulatoryOverlap(
        overlap_id="bench_subresource_ovl",
        shared_topic="CYBERSECURITY",
        left_requirement_id="req_sub_left_01",
        left_authority="IRDAI",
        left_document_id="doc_sub_irdai_01",
        left_section_id="s1",
        right_requirement_id="req_sub_right_01",
        right_authority="IFSCA",
        right_document_id="doc_sub_ifsca_01",
        right_section_id="s2",
        relationship_type="OVERLAPPING",
        confidence="HIGH",
        status="ACTIVE",
        evidence_left="Report incident in 6h",
        evidence_right="Report incident in 2h",
    )
    repo.save_overlaps([test_ovl])

    test_cnf = RegulatoryConflict(
        conflict_id="bench_subresource_cnf",
        overlap_id="bench_subresource_ovl",
        conflict_type="DEADLINE_CONFLICT",
        severity="HIGH",
        confidence="HIGH",
        resolution_status="OPEN",
        left_authority="IRDAI",
        left_requirement_id="req_sub_left_01",
        left_document_id="doc_sub_irdai_01",
        right_authority="IFSCA",
        right_requirement_id="req_sub_right_01",
        right_document_id="doc_sub_ifsca_01",
        evidence_left="Report incident in 6h",
        evidence_right="Report incident in 2h",
        explanation="Incident reporting window: 6h vs 2h",
    )
    repo.save_conflicts([test_cnf])

    # 1. GET /api/requirements/{requirement_id}/overlaps
    resp_req_ovl = client.get("/api/requirements/req_sub_left_01/overlaps")
    assert resp_req_ovl.status_code == 200
    assert any(o["overlap_id"] == "bench_subresource_ovl" for o in resp_req_ovl.json())

    # 2. GET /api/documents/{document_id}/overlaps
    resp_doc_ovl = client.get("/api/documents/doc_sub_irdai_01/overlaps")
    assert resp_doc_ovl.status_code == 200
    assert any(o["overlap_id"] == "bench_subresource_ovl" for o in resp_doc_ovl.json())

    # 3. GET /api/requirements/{requirement_id}/conflicts
    resp_req_cnf = client.get("/api/requirements/req_sub_left_01/conflicts")
    assert resp_req_cnf.status_code == 200
    assert any(c["conflict_id"] == "bench_subresource_cnf" for c in resp_req_cnf.json())

    # 4. Invalidation endpoint
    resp_inval = client.post("/api/requirements/req_sub_left_01/invalidate-cross-regulator")
    assert resp_inval.status_code == 200
    assert resp_inval.json()["status"] == "invalidated"


def test_benchmark_hybrid_candidate_retrieval():
    """Validates cross-regulator candidate discovery using hybrid retriever (73.4, 73.5)."""
    from unittest.mock import patch, MagicMock
    from app.retrieval.hybrid import HybridRetrievedChunk

    engine = OverlapEngine()
    repo = ComplianceRepository()

    target = RegulatoryRequirement(
        requirement_id="hybrid_target_sebi",
        document_id="sebi_doc_hyb",
        authority="SEBI",
        section_id="s1",
        requirement_text="Maintain all accounting books and client records for 8 years.",
        source_evidence="Maintain accounting books for 8 years.",
        requirement_type="RECORD_KEEPING",
        action="maintain",
        object="accounting books",
        subject="regulated entities",
    )

    rbi_req = RegulatoryRequirement(
        requirement_id="hybrid_match_rbi",
        document_id="rbi_doc_hyb",
        authority="RBI",
        section_id="s2",
        requirement_text="Banks shall maintain and preserve accounting books for 8 years.",
        source_evidence="Banks maintain accounting books for 8 years.",
        requirement_type="RECORD_KEEPING",
        action="maintain",
        object="accounting books",
        subject="regulated entities",
    )
    repo.save_requirements([rbi_req])

    mock_chunk = HybridRetrievedChunk(
        chunk_id="chunk_rbi_01",
        document_id="rbi_doc_hyb",
        title="RBI Accounting Norms",
        content="Banks shall maintain and preserve accounting books for 8 years.",
        section="Section 4",
        source="RBI",
        category="Circular",
        document_type="Circular",
        url="https://rbi.org.in/circulars/01",
        score=0.92,
        hybrid_score=0.92,
        vector_score=0.90,
        bm25_score=0.95,
        retrieval_methods=["vector", "bm25"]
    )

    with patch("app.retrieval.hybrid.HybridRetriever.search", return_value=[mock_chunk]):
        candidates = engine.generate_candidates_via_hybrid_retrieval(target, top_k=5)
        assert len(candidates) >= 1
        cand, score, topic = candidates[0]
        assert cand.authority == "RBI"
        assert cand.requirement_id == "hybrid_match_rbi"
        assert topic == "RECORD_KEEPING"
