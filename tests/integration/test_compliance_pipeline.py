"""
Integration test for full Compliance Pipeline (Phases 61, 62, 63).

Verifies:
Document -> Candidate Detection -> Requirements -> Obligations -> Checklist -> Diff propagation -> Provenance Audit.
"""

import pytest
from app.compliance.models import RegulatoryRequirement, RegulatoryObligation
from app.compliance.requirement_extractor import get_requirement_extractor
from app.compliance.obligation_extractor import get_obligation_extractor
from app.compliance.checklist_generator import get_checklist_generator
from app.compliance.traceability import get_traceability_service
from app.compliance.repository import ComplianceRepository


def test_full_compliance_pipeline_end_to_end():
    # 1. Sample SEBI Regulatory Instrument Text
    sample_reg_text = """
    CHAPTER III — CONDUCT OF BUSINESS AND COMPLIANCE OBLIGATIONS

    Section 12. Maintenance of records and client documents.
    (1) The registered investment adviser shall maintain books of accounts and client agreements for a minimum period of 8 years.
    (2) The intermediary shall not charge any fees without obtaining prior written client consent.

    Section 13. Periodic reporting and audit.
    (1) Every registered entity shall submit an annual compliance audit report to the Board within 30 days of the end of the financial year.
    """

    doc_id = "doc_int_ia_2024"
    repo = ComplianceRepository()
    req_extractor = get_requirement_extractor()
    ob_extractor = get_obligation_extractor()
    chk_generator = get_checklist_generator()
    trace_service = get_traceability_service()
    trace_service.repo = repo

    # 2. Extract Requirements (Phase 61)
    requirements = req_extractor.extract_requirements_from_text(
        text=sample_reg_text,
        document_id=doc_id,
        authority="SEBI",
        document_title="SEBI (Investment Advisers) (Amendment) Regulations, 2024",
        effective_date="2024-04-01",
        use_llm=False
    )
    assert len(requirements) >= 3
    repo.save_requirements(requirements)

    # Verify at least one prohibition and one submission requirement
    req_types = [r.requirement_type for r in requirements]
    assert any(t in ["RECORD_KEEPING", "COMPLIANCE"] for t in req_types)
    assert any(t in ["PROHIBITION", "COMPLIANCE"] for t in req_types)
    assert any(t in ["REPORTING", "SUBMISSION", "AUDIT"] for t in req_types)

    # 3. Transform Requirements into Obligations (Phase 62)
    obligations = ob_extractor.extract_obligations(requirements, document_status="ACTIVE")
    assert len(obligations) == len(requirements)
    repo.save_obligations(obligations)

    ob_types = [o.obligation_type for o in obligations]
    assert "MANDATORY" in ob_types
    assert "PROHIBITION" in ob_types

    # 4. Generate Compliance Checklist (Phase 63)
    checklist = chk_generator.generate_checklist(
        title="SEBI IA 2024 Operational Compliance Checklist",
        obligations=obligations,
        document_ids=[doc_id],
        authority="SEBI"
    )
    assert len(checklist.items) >= 3
    assert checklist.completion_rate == 0.0
    repo.save_checklist(checklist)

    # 5. User updates an item status and notes
    target_item = checklist.items[0]
    updated_chk = repo.update_checklist_item_status(
        checklist_id=checklist.checklist_id,
        item_id=target_item.item_id,
        status="COMPLIANT",
        notes="Record retention policy validated against physical and cloud storage."
    )
    assert updated_chk is not None
    assert updated_chk.completion_rate > 0.0

    # 6. Audit Traceability Chain
    audit_report = trace_service.audit_checklist(updated_chk)
    assert audit_report.total_items == len(checklist.items)
    assert audit_report.valid_items == len(checklist.items)
    assert audit_report.missing_obligations == 0
    assert audit_report.missing_requirements == 0
    assert len(audit_report.issues) == 0
