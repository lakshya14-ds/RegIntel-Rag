"""
Requirement Diff Linker (Phase 61.10).

Integrates SectionDiff results from Phase 60 and ChangeIntelligence results from Phase 59
with RegulatoryRequirement models to track how requirements evolve across document versions:
- ADDED_REQUIREMENT
- REMOVED_REQUIREMENT
- MODIFIED_REQUIREMENT
- UNCHANGED_REQUIREMENT
"""

import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.compliance.models import (
    RegulatoryRequirement,
    RequirementDiffStatus,
)
from app.change_detection.diff_engine import SectionDiff, DiffReport

logger = logging.getLogger(__name__)


class RequirementChangeLink(BaseModel):
    """Links an extracted requirement to its version change status."""
    requirement_id: str
    change_status: RequirementDiffStatus
    section_number: Optional[str] = None
    heading: Optional[str] = None
    change_reason: str
    previous_requirement_text: Optional[str] = None
    current_requirement_text: Optional[str] = None
    numerical_shifts: List[Dict[str, str]] = Field(default_factory=list)


def link_requirements_to_section_diffs(
    requirements_old: List[RegulatoryRequirement],
    requirements_new: List[RegulatoryRequirement],
    diff_report: DiffReport
) -> List[RequirementChangeLink]:
    """
    Correlates old and new requirements against section-level diffs.
    """
    links: List[RequirementChangeLink] = []

    # Map section diffs by section_number and heading
    sec_diff_by_num: Dict[str, SectionDiff] = {}
    sec_diff_by_heading: Dict[str, SectionDiff] = {}
    for sd in diff_report.sections:
        if sd.section_number:
            sec_diff_by_num[sd.section_number.strip().lower()] = sd
        sec_diff_by_heading[sd.heading.strip().lower()] = sd

    # 1. Process New Requirements
    for req in requirements_new:
        sec_num = (req.source_locator.get("section_number") or "").strip().lower()
        heading = (req.source_locator.get("heading") or "").strip().lower()

        sd = sec_diff_by_num.get(sec_num) or sec_diff_by_heading.get(heading)

        if not sd:
            # Not matched in diff, treat as unchanged if no signals
            links.append(RequirementChangeLink(
                requirement_id=req.requirement_id,
                change_status="UNCHANGED_REQUIREMENT",
                section_number=req.source_locator.get("section_number"),
                heading=req.source_locator.get("heading"),
                change_reason="Section retains unchanged requirements.",
                current_requirement_text=req.requirement_text
            ))
            continue

        if sd.change_type == "ADDED":
            links.append(RequirementChangeLink(
                requirement_id=req.requirement_id,
                change_status="ADDED_REQUIREMENT",
                section_number=sd.section_number,
                heading=sd.heading,
                change_reason=f"Requirement introduced in new section '{sd.heading}'.",
                current_requirement_text=req.requirement_text
            ))
        elif sd.change_type == "MODIFIED":
            num_shifts = [
                {"parameter": n.parameter, "old": n.previous_value, "new": n.new_value}
                for n in sd.numerical_changes
            ]
            if num_shifts:
                shift_desc = ", ".join(f"{s['parameter']}: {s['old']} -> {s['new']}" for s in num_shifts)
                reason = f"Numeric/parameter shift: {shift_desc}"
            else:
                reason = f"Requirement updated in modified section '{sd.heading}'."

            links.append(RequirementChangeLink(
                requirement_id=req.requirement_id,
                change_status="MODIFIED_REQUIREMENT",
                section_number=sd.section_number,
                heading=sd.heading,
                change_reason=reason,
                previous_requirement_text=sd.previous_text,
                current_requirement_text=req.requirement_text,
                numerical_shifts=num_shifts
            ))
        elif sd.change_type == "UNCHANGED":
            links.append(RequirementChangeLink(
                requirement_id=req.requirement_id,
                change_status="UNCHANGED_REQUIREMENT",
                section_number=sd.section_number,
                heading=sd.heading,
                change_reason="Section preserved without substantive alteration.",
                current_requirement_text=req.requirement_text
            ))

    # 2. Identify REMOVED Requirements (existed in old but section removed)
    for req in requirements_old:
        sec_num = (req.source_locator.get("section_number") or "").strip().lower()
        heading = (req.source_locator.get("heading") or "").strip().lower()

        sd = sec_diff_by_num.get(sec_num) or sec_diff_by_heading.get(heading)
        if sd and sd.change_type == "REMOVED":
            links.append(RequirementChangeLink(
                requirement_id=req.requirement_id,
                change_status="REMOVED_REQUIREMENT",
                section_number=sd.section_number,
                heading=sd.heading,
                change_reason=f"Prior requirement omitted with repealed section '{sd.heading}'.",
                previous_requirement_text=req.requirement_text
            ))

    return links
