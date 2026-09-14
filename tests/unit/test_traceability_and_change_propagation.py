"""
Unit tests for Traceability Graph and Cross-Phase Change Propagation (Phases 61, 62, 63).
"""

import pytest
from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ComplianceChecklist,
    ChecklistItem,
)
from app.compliance.requirement_diff_linker import link_requirements_to_section_diffs
from app.compliance.traceability import get_traceability_service
from app.compliance.repository import ComplianceRepository
from app.change_detection.diff_engine import SectionDiff, DiffReport, NumericalChangeItem


def test_requirement_diff_linkage():
    req_old = RegulatoryRequirement(
        requirement_id="req_old_1",
        document_id="doc_v1",
        requirement_text="Submit return within 30 days.",
        source_evidence="Submit return within 30 days.",
        source_locator={"section_number": "4.1", "heading": "Reporting"}
    )
    req_new = RegulatoryRequirement(
        requirement_id="req_new_1",
        document_id="doc_v2",
        requirement_text="Submit return within 15 days.",
        source_evidence="Submit return within 15 days.",
        source_locator={"section_number": "4.1", "heading": "Reporting"}
    )

    diff_rep = DiffReport(
        older_document_id="doc_v1",
        newer_document_id="doc_v2",
        sections=[
            SectionDiff(
                section_number="4.1",
                heading="Reporting",
                change_type="MODIFIED",
                substantive_change=True,
                numerical_changes=[
                    NumericalChangeItem(parameter="Duration", previous_value="30 days", new_value="15 days")
                ]
            )
        ]
    )

    links = link_requirements_to_section_diffs([req_old], [req_new], diff_rep)
    assert len(links) >= 1
    mod_link = next(l for l in links if l.requirement_id == "req_new_1")
    assert mod_link.change_status == "MODIFIED_REQUIREMENT"
    assert "30 days -> 15 days" in mod_link.change_reason


def test_traceability_resolution_and_audit():
    # Setup mock repository with one requirement and one obligation
    repo = ComplianceRepository()
    req = RegulatoryRequirement(
        requirement_id="req_trace_01",
        document_id="doc_t1",
        requirement_text="Broker shall report trade data.",
        source_evidence="Broker shall report trade data.",
        source_locator={"heading": "Trade Reporting", "page_number": 12}
    )
    ob = RegulatoryObligation(
        obligation_id="ob_trace_01",
        requirement_id="req_trace_01",
        document_id="doc_t1",
        obligated_party="Broker",
        obligation_action="report",
        obligation_object="trade data",
        source_evidence="Broker shall report trade data.",
        source_locator={"heading": "Trade Reporting", "page_number": 12}
    )

    repo.save_requirements([req])
    repo.save_obligations([ob])

    item = ChecklistItem(
        item_id="item_trace_01",
        obligation_id="ob_trace_01",
        requirement_id="req_trace_01",
        document_id="doc_t1",
        control_question="Does the broker report trade data?",
        compliance_action="Report trade data."
    )
    chk = ComplianceChecklist(
        checklist_id="chk_trace_test",
        title="Traceability Test Checklist",
        items=[item]
    )

    service = get_traceability_service()
    service.repo = repo

    node = service.get_item_traceability(item)
    assert node.is_valid is True
    assert node.requirement_text == "Broker shall report trade data."
    assert node.page_number == 12

    audit = service.audit_checklist(chk)
    assert audit.valid_items == 1
    assert audit.missing_requirements == 0
    assert audit.missing_obligations == 0


def test_audit_detects_orphan_and_missing():
    repo = ComplianceRepository()
    service = get_traceability_service()
    service.repo = repo

    orphan_item = ChecklistItem(
        item_id="item_orphan",
        obligation_id="ob_nonexistent",
        requirement_id="req_nonexistent",
        document_id="doc_fake",
        control_question="Orphan question?",
        compliance_action="Take action."
    )
    chk = ComplianceChecklist(
        checklist_id="chk_orphan_test",
        title="Orphan Test",
        items=[orphan_item]
    )

    audit = service.audit_checklist(chk)
    assert audit.valid_items == 0
    assert audit.missing_obligations == 1
    assert audit.missing_requirements == 1
    assert len(audit.issues) >= 2
