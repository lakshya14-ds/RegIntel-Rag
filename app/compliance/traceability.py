"""
Traceability Graph and Validation Engine (Phases 61, 62, 63).

Builds and validates bidirectional links:
Checklist Item <-> Obligation <-> Requirement <-> Section <-> Document
Detects orphan items, broken linkages, missing evidence, and ungrounded claims.
"""

import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ChecklistItem,
    ComplianceChecklist,
)
from app.compliance.repository import ComplianceRepository, get_compliance_repository

logger = logging.getLogger(__name__)


class TraceabilityNode(BaseModel):
    """Represents a node in the regulatory intelligence traceability graph."""
    item_id: str
    control_question: str
    status: str

    obligation_id: str
    obligated_party: Optional[str] = None
    obligation_action: Optional[str] = None
    obligation_type: str

    requirement_id: str
    requirement_type: str
    requirement_text: str

    document_id: str
    section_id: Optional[str] = None
    section_heading: Optional[str] = None
    source_evidence: str
    page_number: Optional[int] = None

    is_valid: bool = True
    issues: List[str] = Field(default_factory=list)


class ChecklistAuditReport(BaseModel):
    """Audit report for an entire compliance checklist verifying data integrity."""
    checklist_id: str
    total_items: int = 0
    valid_items: int = 0
    orphan_items: int = 0
    missing_obligations: int = 0
    missing_requirements: int = 0
    missing_evidence: int = 0
    issues: List[str] = Field(default_factory=list)
    nodes: List[TraceabilityNode] = Field(default_factory=list)


class TraceabilityService:
    """
    Validates and navigates regulatory compliance traceability graphs.
    """

    def __init__(self, repository: Optional[ComplianceRepository] = None):
        self.repo = repository or get_compliance_repository()

    def get_item_traceability(
        self,
        checklist_item: ChecklistItem
    ) -> TraceabilityNode:
        """Traces a single checklist item back to its obligation, requirement, and source evidence."""
        issues: List[str] = []

        # 1. Fetch Obligation
        obligation = self.repo.get_obligation_by_id(checklist_item.obligation_id)
        if not obligation:
            issues.append(f"Missing upstream obligation: '{checklist_item.obligation_id}' not found.")

        # 2. Fetch Requirement
        requirement = self.repo.get_requirement_by_id(checklist_item.requirement_id)
        if not requirement:
            issues.append(f"Missing upstream requirement: '{checklist_item.requirement_id}' not found.")

        evidence_text = ""
        heading = None
        page = None
        if requirement:
            evidence_text = requirement.source_evidence
            heading = requirement.source_locator.get("heading")
            page = requirement.source_locator.get("page_number")
        elif checklist_item.source_reference:
            evidence_text = checklist_item.source_reference.get("evidence_snippet", "")
            heading = checklist_item.source_reference.get("heading")
            page = checklist_item.source_reference.get("page_number")

        if not evidence_text:
            issues.append("Missing source evidence: no textual citation attached.")

        return TraceabilityNode(
            item_id=checklist_item.item_id,
            control_question=checklist_item.control_question,
            status=checklist_item.status,
            obligation_id=checklist_item.obligation_id,
            obligated_party=obligation.obligated_party if obligation else checklist_item.obligated_party,
            obligation_action=obligation.obligation_action if obligation else checklist_item.compliance_action,
            obligation_type=obligation.obligation_type if obligation else "UNKNOWN",
            requirement_id=checklist_item.requirement_id,
            requirement_type=requirement.requirement_type if requirement else "OTHER",
            requirement_text=requirement.requirement_text if requirement else "",
            document_id=checklist_item.document_id,
            section_id=checklist_item.section_id,
            section_heading=heading,
            source_evidence=evidence_text,
            page_number=page,
            is_valid=len(issues) == 0,
            issues=issues
        )

    def audit_checklist(self, checklist: ComplianceChecklist) -> ChecklistAuditReport:
        """Audits all items in a checklist for complete, unbroken traceability."""
        report = ChecklistAuditReport(
            checklist_id=checklist.checklist_id,
            total_items=len(checklist.items)
        )

        for item in checklist.items:
            node = self.get_item_traceability(item)
            report.nodes.append(node)
            if node.is_valid:
                report.valid_items += 1
            else:
                for iss in node.issues:
                    if "Missing upstream obligation" in iss:
                        report.missing_obligations += 1
                    if "Missing upstream requirement" in iss:
                        report.missing_requirements += 1
                    if "Missing source evidence" in iss:
                        report.missing_evidence += 1
                    report.issues.append(f"Item {item.item_id}: {iss}")

        return report


_traceability_service = TraceabilityService()


def get_traceability_service() -> TraceabilityService:
    return _traceability_service
