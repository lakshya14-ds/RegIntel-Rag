"""
Compliance Checklist Generator (Phase 63).

Converts structured RegulatoryObligations into evidence-grounded ComplianceChecklists
with actionable control questions, applicability filtering, change propagation, and audit status.
"""

import re
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ComplianceChecklist,
    ChecklistItem,
    ChecklistStatus,
)
from app.compliance.requirement_diff_linker import RequirementChangeLink

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# =============================================================================
# CONTROL QUESTION GENERATOR (63.3, 63.4)
# =============================================================================

def generate_control_question(obligation: RegulatoryObligation) -> str:
    """
    Transforms a regulatory obligation into a faithful, actionable verification question.
    """
    party = obligation.obligated_party or "the regulated entity"
    action = (obligation.obligation_action or "comply with the provision").strip()
    obj = (obligation.obligation_object or "").strip()
    deadline = obligation.deadline
    frequency = obligation.frequency

    # Prohibitions
    if obligation.obligation_type == "PROHIBITION":
        return f"Does {party} strictly refrain from {action} {obj} as prohibited by the regulation?"

    # Deadlines / Submissions
    if deadline:
        return f"Does {party} {action} {obj} within the mandatory deadline ({deadline})?"

    # Record Keeping
    if "maintain" in action.lower() or "record" in action.lower():
        dur = next((th.raw_value for th in obligation.thresholds if th.parameter_type == "duration"), None)
        if dur:
            return f"Are all required records and documentation maintained by {party} for at least {dur}?"
        return f"Does {party} properly maintain all required {obj or 'books, registers, and records'}?"

    # Reporting / Disclosure
    if frequency:
        return f"Is {obj or 'the required regulatory reporting'} submitted/disclosed on a {frequency.lower()} basis by {party}?"

    return f"Has {party} taken all necessary measures to {action} {obj} in accordance with regulatory requirements?"


def generate_compliance_action(obligation: RegulatoryObligation) -> str:
    """Produces the expected concrete operational action."""
    action = obligation.obligation_action or "Comply"
    obj = obligation.obligation_object or "with regulatory mandates"
    deadline_str = f" {obligation.deadline}" if obligation.deadline else ""
    return f"{action.capitalize()} {obj}{deadline_str}.".strip()


# =============================================================================
# CHECKLIST GENERATION ENGINE (Phase 63)
# =============================================================================

class ChecklistGenerator:
    """
    Builds and regenerates compliance checklists from extracted obligations.
    """

    def generate_checklist(
        self,
        title: str,
        obligations: List[RegulatoryObligation],
        document_ids: Optional[List[str]] = None,
        authority: str = "SEBI",
        entity_filter: Optional[str] = None,
        change_links: Optional[List[RequirementChangeLink]] = None,
        description: Optional[str] = None
    ) -> ComplianceChecklist:
        """
        Generates a new ComplianceChecklist from a list of obligations.
        """
        checklist_id = f"chk_{hashlib.sha256(f'{title}:{datetime.utcnow().isoformat()}'.encode('utf-8')).hexdigest()[:12]}"
        items: List[ChecklistItem] = []

        # Index change links if provided
        changes_by_req: Dict[str, RequirementChangeLink] = {}
        if change_links:
            for cl in change_links:
                changes_by_req[cl.requirement_id] = cl

        for idx, ob in enumerate(obligations):
            # Entity applicability filtering (63.5)
            init_status: ChecklistStatus = "NOT_REVIEWED"
            if entity_filter and ob.obligated_party:
                if entity_filter.lower() not in ob.obligated_party.lower() and "regulated" not in ob.obligated_party.lower():
                    init_status = "NOT_APPLICABLE"

            # Check change propagation (63.8)
            is_changed = False
            change_summary = None
            cl = changes_by_req.get(ob.requirement_id)
            if cl and cl.change_status in ["MODIFIED_REQUIREMENT", "ADDED_REQUIREMENT"]:
                is_changed = True
                change_summary = cl.change_reason

            item_id = f"item_{idx + 1:03d}_{ob.obligation_id[:8]}"
            control_q = generate_control_question(ob)
            comp_action = generate_compliance_action(ob)

            items.append(ChecklistItem(
                item_id=item_id,
                obligation_id=ob.obligation_id,
                requirement_id=ob.requirement_id,
                document_id=ob.document_id,
                section_id=ob.section_id,
                control_question=control_q,
                compliance_action=comp_action,
                obligated_party=ob.obligated_party,
                frequency=ob.frequency,
                deadline=ob.deadline,
                applicability=str(ob.applicability.get("scope") or ob.obligated_party),
                evidence_required=ob.required_evidence or ["Audit documentation / compliance record"],
                source_reference={
                    "document_id": ob.document_id,
                    "section_id": ob.section_id,
                    "section_number": ob.source_locator.get("section_number"),
                    "heading": ob.source_locator.get("heading"),
                    "page_number": ob.source_locator.get("page_number"),
                    "evidence_snippet": ob.source_evidence[:250]
                },
                status=init_status,
                notes=None,
                confidence=ob.confidence,
                is_changed=is_changed,
                change_summary=change_summary
            ))

        chk = ComplianceChecklist(
            checklist_id=checklist_id,
            title=title,
            description=description or f"Operational compliance checklist for {authority} requirements.",
            authority=authority,
            document_ids=document_ids or list(set(ob.document_id for ob in obligations)),
            items=items
        )
        chk.recalculate_metrics()
        return chk

    def regenerate_checklist(
        self,
        existing_checklist: ComplianceChecklist,
        new_obligations: List[RegulatoryObligation],
        change_links: Optional[List[RequirementChangeLink]] = None
    ) -> ComplianceChecklist:
        """
        Regenerates an existing checklist with updated regulatory versions (63.12).
        Preserves user-entered review statuses and notes for unmodified items.
        """
        # Index existing user review states by obligation_id or requirement_id
        existing_states: Dict[str, Tuple[ChecklistStatus, Optional[str]]] = {}
        for item in existing_checklist.items:
            existing_states[item.obligation_id] = (item.status, item.notes)
            existing_states[item.requirement_id] = (item.status, item.notes)

        fresh_checklist = self.generate_checklist(
            title=existing_checklist.title,
            obligations=new_obligations,
            document_ids=existing_checklist.document_ids,
            authority=existing_checklist.authority,
            change_links=change_links,
            description=existing_checklist.description
        )

        # Re-attach preserved notes and statuses
        for item in fresh_checklist.items:
            if item.obligation_id in existing_states:
                prev_status, prev_notes = existing_states[item.obligation_id]
                item.status = prev_status
                item.notes = prev_notes
            elif item.requirement_id in existing_states:
                prev_status, prev_notes = existing_states[item.requirement_id]
                item.status = prev_status
                item.notes = prev_notes

        fresh_checklist.checklist_id = existing_checklist.checklist_id
        fresh_checklist.created_at = existing_checklist.created_at
        fresh_checklist.updated_at = datetime.utcnow().isoformat()
        fresh_checklist.recalculate_metrics()

        return fresh_checklist


_checklist_generator = ChecklistGenerator()


def get_checklist_generator() -> ChecklistGenerator:
    return _checklist_generator
