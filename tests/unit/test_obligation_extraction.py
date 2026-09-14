"""
Unit tests for Regulatory Obligation Extraction & Deontic Grounding (Phase 62).
"""

import pytest
from app.compliance.models import RegulatoryRequirement
from app.compliance.obligation_extractor import (
    classify_deontic_type,
    extract_compliance_evidence,
    validate_obligation_grounding,
    get_obligation_extractor,
)


def test_classify_deontic_types():
    assert classify_deontic_type("The entity shall submit the report.") == "MANDATORY"
    assert classify_deontic_type("The entity shall not engage in front running.") == "PROHIBITION"
    assert classify_deontic_type("If turnover exceeds ₹50 Lakhs, the entity shall appoint a compliance officer.") == "CONDITIONAL_MANDATORY"
    assert classify_deontic_type("The intermediary should consider adopting two-factor authentication.") == "RECOMMENDED"
    assert classify_deontic_type("The adviser may charge fees via online payment gateways.") == "PERMITTED"


def test_compliance_evidence_extraction():
    text = "The entity shall maintain register of complaints and obtain board resolution for material transactions."
    evidence, req_record, _ = extract_compliance_evidence(text)
    assert len(evidence) >= 2
    assert any("Board Resolution" in ev for ev in evidence)
    assert any("Internal Register" in ev for ev in evidence)


def test_obligation_grounding_validation():
    req = RegulatoryRequirement(
        requirement_id="req_test_01",
        document_id="doc_test",
        requirement_text="The broker shall maintain client ledger records for 5 years.",
        source_evidence="The broker shall maintain client ledger records for 5 years."
    )

    extractor = get_obligation_extractor()
    ob = extractor.extract_obligation_from_requirement(req)

    assert ob.obligation_type == "MANDATORY"
    assert ob.confidence == "HIGH"
    assert ob.status == "ACTIVE"
    assert "doc_test" in ob.document_id


def test_obligation_lifecycle_superseded():
    req = RegulatoryRequirement(
        requirement_id="req_test_02",
        document_id="doc_old",
        requirement_text="The adviser shall submit reports within 30 days.",
        source_evidence="The adviser shall submit reports within 30 days."
    )

    extractor = get_obligation_extractor()
    ob = extractor.extract_obligation_from_requirement(req, document_status="SUPERSEDED")
    assert ob.status == "SUPERSEDED"
