"""
Unit tests for Compliance Checklist Generation and Management (Phase 63).
"""

import pytest
from app.compliance.models import (
    RegulatoryObligation,
    RequirementThreshold,
    ComplianceChecklist,
    ChecklistItem,
)
from app.compliance.checklist_generator import (
    generate_control_question,
    generate_compliance_action,
    get_checklist_generator,
)
from app.compliance.export import (
    export_checklist_to_markdown,
    export_checklist_to_json,
)


def test_generate_control_question():
    ob = RegulatoryObligation(
        obligation_id="ob_001",
        requirement_id="req_001",
        document_id="doc_001",
        obligated_party="Investment Adviser",
        obligation_action="maintain",
        obligation_object="client agreements",
        obligation_type="MANDATORY",
        thresholds=[RequirementThreshold(parameter_type="duration", raw_value="8 years")],
        source_evidence="The Investment Adviser shall maintain client agreements for 8 years."
    )

    q = generate_control_question(ob)
    assert "Investment Adviser" in q
    assert "8 years" in q
    assert "?" in q


def test_generate_compliance_action():
    ob = RegulatoryObligation(
        obligation_id="ob_002",
        requirement_id="req_002",
        document_id="doc_001",
        obligation_action="submit",
        obligation_object="quarterly audit report",
        deadline="within 15 days",
        source_evidence="Submit quarterly audit report within 15 days."
    )

    act = generate_compliance_action(ob)
    assert "Submit quarterly audit report within 15 days." == act


def test_checklist_generation_and_metrics():
    obs = [
        RegulatoryObligation(
            obligation_id=f"ob_{i}",
            requirement_id=f"req_{i}",
            document_id="doc_test",
            obligated_party="Broker",
            obligation_action="file",
            obligation_object="return",
            source_evidence="Broker shall file return."
        )
        for i in range(4)
    ]

    generator = get_checklist_generator()
    chk = generator.generate_checklist(
        title="Broker Compliance Review",
        obligations=obs,
        authority="SEBI"
    )

    assert len(chk.items) == 4
    assert chk.summary_counts["TOTAL"] == 4
    assert chk.summary_counts["NOT_REVIEWED"] == 4
    assert chk.completion_rate == 0.0

    # Review 2 items
    chk.items[0].status = "COMPLIANT"
    chk.items[1].status = "NON_COMPLIANT"
    chk.recalculate_metrics()

    assert chk.completion_rate == 50.0
    assert chk.summary_counts["COMPLIANT"] == 1
    assert chk.summary_counts["NON_COMPLIANT"] == 1


def test_checklist_regeneration_preserves_notes():
    generator = get_checklist_generator()
    ob1 = RegulatoryObligation(
        obligation_id="ob_101",
        requirement_id="req_101",
        document_id="doc_v1",
        obligated_party="AMC",
        obligation_action="conduct",
        obligation_object="internal audit",
        source_evidence="AMC shall conduct internal audit."
    )

    chk_v1 = generator.generate_checklist("AMC Checklist", [ob1])
    chk_v1.items[0].status = "COMPLIANT"
    chk_v1.items[0].notes = "Verified in Audit Committee meeting."

    # Regenerate with new version
    chk_v2 = generator.regenerate_checklist(chk_v1, [ob1])

    assert chk_v2.items[0].status == "COMPLIANT"
    assert chk_v2.items[0].notes == "Verified in Audit Committee meeting."


def test_checklist_exports():
    chk = ComplianceChecklist(
        checklist_id="chk_test_exp",
        title="Test Export Checklist",
        items=[
            ChecklistItem(
                item_id="item_01",
                obligation_id="ob_01",
                requirement_id="req_01",
                document_id="doc_01",
                control_question="Are client funds segregated?",
                compliance_action="Segregate client funds.",
                status="COMPLIANT"
            )
        ]
    )

    md = export_checklist_to_markdown(chk)
    assert "# Regulatory Compliance Checklist: Test Export Checklist" in md
    assert "Are client funds segregated?" in md
    assert "COMPLIANT" in md

    js = export_checklist_to_json(chk)
    assert "chk_test_exp" in js
    assert "item_01" in js
