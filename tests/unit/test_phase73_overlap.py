"""
Phase 73 Unit Test Suite: Cross-Regulator Overlap Detection Engine.

Validates:
- 73.1: Regulatory overlap data models, types, confidences, statuses
- 73.2: Controlled regulatory topic normalizer and taxonomy
- 73.3: Overlap candidate generation (cross-regulator filtering, authority_a != authority_b)
- 73.4: Deterministic similarity, numeric parameter comparison, applicability comparison
- 73.5: Overlap pair analysis and provenance verification
- 73.6: REST API endpoints for regulatory overlap query and inspection
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.connectors.authority import RegulatoryAuthority
from app.compliance.models import RegulatoryRequirement, RequirementThreshold
from app.compliance.overlap_models import (
    RegulatoryOverlap,
    OverlapType,
    OverlapConfidence,
    OverlapStatus,
    CONTROLLED_REGULATORY_TOPICS,
)
from app.compliance.topic_normalizer import normalize_regulatory_topic
from app.compliance.overlap_engine import OverlapEngine
from app.compliance.repository import ComplianceRepository


@pytest.fixture
def test_client():
    return TestClient(app)


def test_controlled_topics_taxonomy():
    """Validates that all required controlled regulatory topics exist."""
    expected_topics = [
        "KYC", "AML", "RECORD_KEEPING", "REPORTING", "DISCLOSURE",
        "CYBERSECURITY", "OUTSOURCING", "GOVERNANCE", "CAPITAL",
        "CUSTOMER_PROTECTION", "AUDIT"
    ]
    for topic in expected_topics:
        assert topic in CONTROLLED_REGULATORY_TOPICS


def test_topic_normalizer():
    """Validates deterministic mapping of free-text into controlled topics."""
    assert normalize_regulatory_topic(text="customer identification and kyc verification") == "KYC"
    assert normalize_regulatory_topic(text="prevention of money laundering regulations and suspicious transaction reporting") == "AML"
    assert normalize_regulatory_topic(text="books of accounts preservation for a period of eight years") == "RECORD_KEEPING"
    assert normalize_regulatory_topic(text="cyber security policy and information technology audit") == "CYBERSECURITY"
    assert normalize_regulatory_topic(text="internal audit requirement and statutory auditor inspection") == "AUDIT"
    assert normalize_regulatory_topic(text="submission of quarterly return and compliance report") == "REPORTING"
    assert normalize_regulatory_topic(text="random unrelated text with no financial terms") == "OTHER"


def test_regulatory_overlap_model():
    """Verifies RegulatoryOverlap model creation, fields, and serialization."""
    overlap = RegulatoryOverlap(
        overlap_id="ovl_sebi_rbi_kyc_01",
        shared_topic="KYC",
        left_requirement_id="req_sebi_01",
        left_authority=RegulatoryAuthority.SEBI,
        left_document_id="sebi_cir_2025_01",
        left_section_id="sec_4",
        evidence_left="Entities must verify client identity using official valid documents.",
        right_requirement_id="req_rbi_01",
        right_authority=RegulatoryAuthority.RBI,
        right_document_id="rbi_md_kyc_2025",
        right_section_id="sec_12",
        evidence_right="Regulated entities shall perform customer due diligence using OVDs.",
        relationship_type="NEAR_DUPLICATE",
        confidence="HIGH",
        status="ACTIVE",
        similarity_score=0.88,
        applicability_match="SAME_ENTITIES",
        reasoning="Both authorities mandate customer identification via official valid documents."
    )

    assert overlap.shared_topic == "KYC"
    assert overlap.left_authority == RegulatoryAuthority.SEBI
    assert overlap.right_authority == RegulatoryAuthority.RBI
    assert overlap.relationship_type == "NEAR_DUPLICATE"
    assert overlap.status == "ACTIVE"
    assert overlap.created_at is not None


def test_candidate_generation_cross_regulator_filtering():
    """Validates that candidate generator strictly enforces cross-regulator pairs."""
    engine = OverlapEngine()

    req_target = RegulatoryRequirement(
        requirement_id="req_target_sebi",
        document_id="doc_sebi_01",
        authority="SEBI",
        section_id="sec_1",
        requirement_text="Regulated entities must preserve records for a minimum duration of 8 years.",
        source_evidence="Intermediaries shall maintain books of accounts for 8 years.",
        requirement_type="RECORD_KEEPING",
        action="preserve",
        object="records",
        subject="regulated entities",
    )

    # Same authority requirement (SEBI) - should be IGNORED
    req_same_auth = RegulatoryRequirement(
        requirement_id="req_sebi_internal",
        document_id="doc_sebi_02",
        authority="SEBI",
        section_id="sec_5",
        requirement_text="Records must be preserved for 8 years in digital or physical format.",
        source_evidence="Maintain all records for 8 years.",
        requirement_type="RECORD_KEEPING",
        action="preserve",
        object="records",
        subject="regulated entities",
    )

    # Cross authority requirement with matching topic and action (RBI) - should be INCLUDED
    req_rbi_match = RegulatoryRequirement(
        requirement_id="req_rbi_books",
        document_id="doc_rbi_01",
        authority="RBI",
        section_id="sec_9",
        requirement_text="Banks must preserve books of accounts and records for at least 8 years.",
        source_evidence="Banks must preserve books for 8 years.",
        requirement_type="RECORD_KEEPING",
        action="preserve",
        object="records",
        subject="regulated entities",
    )

    # Cross authority requirement with different topic (IRDAI) - should be filtered out
    req_irdai_diff = RegulatoryRequirement(
        requirement_id="req_irdai_claims",
        document_id="doc_irdai_01",
        authority="IRDAI",
        section_id="sec_3",
        requirement_text="Insurers must settle insurance claims within 30 days of receipt of documents.",
        source_evidence="Settle claims in 30 days.",
        requirement_type="REPORTING",
        action="settle",
        object="claims",
        subject="insurers",
    )

    candidates = engine.generate_candidates_for_requirement(
        req_target,
        [req_target, req_same_auth, req_rbi_match, req_irdai_diff],
        min_deterministic_score=0.20
    )

    assert len(candidates) == 1
    cand, score, topic = candidates[0]
    assert cand.requirement_id == "req_rbi_books"
    assert cand.authority == "RBI"


def test_compare_numeric_parameters():
    """Tests parameter extraction and comparison across requirements."""
    engine = OverlapEngine()

    th_a = [RequirementThreshold(parameter_type="duration", raw_value="8 years", normalized_value=8.0, unit="years")]
    th_b = [RequirementThreshold(parameter_type="duration", raw_value="8 years", normalized_value=8.0, unit="years")]
    comp_matching = engine.compare_numeric_parameters(th_a, th_b)
    assert comp_matching["has_shared_parameters"] is True
    assert comp_matching["values_differ"] is False

    th_c = [RequirementThreshold(parameter_type="duration", raw_value="5 years", normalized_value=5.0, unit="years")]
    comp_conflicting = engine.compare_numeric_parameters(th_a, th_c)
    assert comp_conflicting["has_shared_parameters"] is True
    assert comp_conflicting["values_differ"] is True


def test_analyze_pair_overlap():
    """Tests pair analysis creating a verified RegulatoryOverlap."""
    engine = OverlapEngine()

    req_sebi = RegulatoryRequirement(
        requirement_id="sebi_req_aml",
        document_id="sebi_cir_aml",
        authority="SEBI",
        section_id="sec_10",
        requirement_text="Intermediaries shall report suspicious transactions to FIU-IND within 7 days.",
        source_evidence="File suspicious transaction report to FIU-IND.",
        requirement_type="REPORTING",
        action="report",
        object="suspicious transactions",
        subject="regulated entities",
        thresholds=[RequirementThreshold(parameter_type="duration", raw_value="7 days", normalized_value=7.0, unit="days")]
    )

    req_rbi = RegulatoryRequirement(
        requirement_id="rbi_req_aml",
        document_id="rbi_md_aml",
        authority="RBI",
        section_id="sec_14",
        requirement_text="Banks must report suspicious transactions to FIU-IND within 7 days.",
        source_evidence="Banks must report suspicious transactions to FIU-IND within 7 days.",
        requirement_type="REPORTING",
        action="report",
        object="suspicious transactions",
        subject="regulated entities",
        thresholds=[RequirementThreshold(parameter_type="duration", raw_value="7 days", normalized_value=7.0, unit="days")]
    )

    overlap = engine.analyze_pair(req_sebi, req_rbi, use_llm=False)
    assert overlap is not None
    assert overlap.shared_topic == "AML"
    assert overlap.left_authority == RegulatoryAuthority.SEBI
    assert overlap.right_authority == RegulatoryAuthority.RBI
    assert overlap.relationship_type in ["NEAR_DUPLICATE", "OVERLAPPING", "COMPLEMENTARY", "RELATED"]
    assert overlap.status == "ACTIVE"


def test_overlap_api_endpoints(test_client):
    """Tests REST endpoints for regulatory overlap discovery and inspection."""
    repo = ComplianceRepository()
    test_overlap = RegulatoryOverlap(
        overlap_id="ovl_test_route_01",
        shared_topic="RECORD_KEEPING",
        left_requirement_id="req_sebi_rec",
        left_authority=RegulatoryAuthority.SEBI,
        left_document_id="sebi_doc",
        left_section_id="s1",
        evidence_left="Keep records 8 years",
        right_requirement_id="req_rbi_rec",
        right_authority=RegulatoryAuthority.RBI,
        right_document_id="rbi_doc",
        right_section_id="s2",
        evidence_right="Maintain accounts 8 years",
        relationship_type="NEAR_DUPLICATE",
        confidence="HIGH",
        status="ACTIVE",
        reasoning="Both require maintaining records for 8 years.",
    )
    repo.save_overlaps([test_overlap])

    # 1. GET list
    resp = test_client.get("/api/regulatory-overlaps?authority=SEBI&topic=RECORD_KEEPING")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(o["overlap_id"] == "ovl_test_route_01" for o in data)

    # 2. GET detail
    resp_detail = test_client.get("/api/regulatory-overlaps/ovl_test_route_01")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["overlap_id"] == "ovl_test_route_01"
    assert detail["shared_topic"] == "RECORD_KEEPING"

    # 3. GET 404 for non-existent
    resp_404 = test_client.get("/api/regulatory-overlaps/ovl_non_existent")
    assert resp_404.status_code == 404
