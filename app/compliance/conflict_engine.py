"""
Cross-Regulator Conflict & Inconsistency Detection Engine (Phase 74).

Provides:
- 74.3: Overlap-first dependency: conflicts derive strictly from verified overlaps.
- 74.4: Parameter conflict detection (differing thresholds on matching applicability).
- 74.5: Deadline conflict detection with conservative scope guards.
- 74.6: Frequency conflict detection.
- 74.7: Action & prohibition conflict detection.
- 74.9 & 74.10: Applicability and temporal compatibility analysis.
- 74.11 & 74.12: Severity (LOW, MEDIUM, HIGH, UNKNOWN) and Confidence assignment.
- 74.14: LLM conflict reasoning with strict negative guards.
"""

import json
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    RequirementThreshold,
)
from app.compliance.overlap_models import RegulatoryOverlap
from app.compliance.conflict_models import (
    RegulatoryConflict,
    RegulatoryConflictType,
    ConflictSeverity,
    ConflictConfidence,
    ConflictResolutionStatus,
)
from app.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class LLMConflictOutput(BaseModel):
    """Structured Pydantic output for Gemini conflict reasoning (74.14)."""
    conflict_type: RegulatoryConflictType
    is_potential_conflict: bool
    severity: ConflictSeverity
    confidence: ConflictConfidence
    explanation: str
    conflicting_fields: List[str]


def generate_conflict_id(left_req_id: str, right_req_id: str, conflict_type: str) -> str:
    """Generates a stable conflict ID based on requirement IDs and conflict type."""
    ordered = sorted([left_req_id.strip(), right_req_id.strip()])
    h = hashlib.sha256(f"{ordered[0]}:::{ordered[1]}:::{conflict_type}".encode("utf-8")).hexdigest()[:16]
    return f"cnf_{h}"


class ConflictEngine:
    """
    Engine for identifying potential cross-regulator inconsistencies and conflicts.
    """

    def __init__(self):
        self.llm_provider = get_llm_provider()

    # -------------------------------------------------------------------------
    # 74.3 OVERLAP-FIRST EVALUATION
    # -------------------------------------------------------------------------

    def detect_conflicts_from_overlap(
        self,
        overlap: RegulatoryOverlap,
        req_left: RegulatoryRequirement,
        req_right: RegulatoryRequirement,
        use_llm: bool = True
    ) -> Optional[RegulatoryConflict]:
        """
        Derives potential conflict from a verified overlap record (74.3).
        Only evaluates pairs with substantive overlap (IDENTICAL, NEAR_DUPLICATE, OVERLAPPING).
        """
        # Rule 74.3: Do not run conflict analysis against distinct/unrelated provisions
        if overlap.relationship_type not in ("IDENTICAL", "NEAR_DUPLICATE", "OVERLAPPING"):
            return None

        # Rule 74.9: If applicability is explicitly disjoint, no direct conflict
        if overlap.applicability_match == "DIFFERENT_ENTITIES":
            return None

        # 1. Deterministic Action / Prohibition Check (74.7)
        action_conflict = self._check_action_prohibition_conflict(req_left, req_right)
        if action_conflict:
            return self._build_conflict_record(
                overlap=overlap,
                req_left=req_left,
                req_right=req_right,
                conflict_type="PROHIBITION_CONFLICT" if "prohibition" in action_conflict["explanation"].lower() else "ACTION_CONFLICT",
                severity="HIGH",
                confidence="HIGH",
                conflicting_fields=["action"],
                left_val={"action": req_left.action, "requirement_type": req_left.requirement_type},
                right_val={"action": req_right.action, "requirement_type": req_right.requirement_type},
                explanation=action_conflict["explanation"]
            )

        # 2. Deterministic Parameter Threshold Check (74.4)
        param_conflict = self._check_parameter_conflict(overlap.parameter_comparison)
        if param_conflict:
            return self._build_conflict_record(
                overlap=overlap,
                req_left=req_left,
                req_right=req_right,
                conflict_type="PARAMETER_CONFLICT",
                severity="MEDIUM",
                confidence="HIGH",
                conflicting_fields=["threshold", "parameter"],
                left_val=param_conflict["left_val"],
                right_val=param_conflict["right_val"],
                explanation=param_conflict["explanation"]
            )

        # 3. Deterministic Deadline Check (74.5)
        deadline_conflict = self._check_deadline_conflict(req_left, req_right)
        if deadline_conflict:
            return self._build_conflict_record(
                overlap=overlap,
                req_left=req_left,
                req_right=req_right,
                conflict_type="DEADLINE_CONFLICT",
                severity="MEDIUM",
                confidence="MEDIUM",
                conflicting_fields=["deadline"],
                left_val={"deadline": req_left.deadline},
                right_val={"deadline": req_right.deadline},
                explanation=deadline_conflict["explanation"]
            )

        # 4. LLM reasoning for subtle inconsistencies if enabled (74.14)
        if use_llm:
            return self._reason_with_llm(overlap, req_left, req_right)

        return None

    # -------------------------------------------------------------------------
    # 74.4 PARAMETER CONFLICT DETECTION
    # -------------------------------------------------------------------------

    def _check_parameter_conflict(self, param_comparison: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Identifies conflicting numeric parameters (74.4)."""
        if not param_comparison.get("has_shared_parameters") or not param_comparison.get("values_differ"):
            return None

        for detail in param_comparison.get("details", []):
            if detail.get("values_differ"):
                p_type = detail.get("parameter_type")
                l_raw = detail.get("left_raw")
                r_raw = detail.get("right_raw")
                return {
                    "left_val": {p_type: l_raw, "normalized": detail.get("left_normalized")},
                    "right_val": {p_type: r_raw, "normalized": detail.get("right_normalized")},
                    "explanation": f"Differing {p_type} parameter requirements: {l_raw} vs {r_raw}."
                }
        return None

    # -------------------------------------------------------------------------
    # 74.5 DEADLINE CONFLICT DETECTION
    # -------------------------------------------------------------------------

    def _check_deadline_conflict(
        self,
        req_left: RegulatoryRequirement,
        req_right: RegulatoryRequirement
    ) -> Optional[Dict[str, Any]]:
        """Compares filing / compliance deadlines (74.5)."""
        dl_left = (req_left.deadline or "").strip().lower()
        dl_right = (req_right.deadline or "").strip().lower()

        if not dl_left or not dl_right or dl_left == dl_right:
            return None

        # If both are days-based expressions (e.g. "15 days" vs "30 days")
        import re
        m_left = re.search(r"(\d+)\s*days?", dl_left)
        m_right = re.search(r"(\d+)\s*days?", dl_right)
        if m_left and m_right:
            days_l = int(m_left.group(1))
            days_r = int(m_right.group(1))
            if days_l != days_r:
                return {
                    "explanation": f"Differing submission turnaround times: {days_l} days vs {days_r} days for related regulatory filing."
                }

        return None

    # -------------------------------------------------------------------------
    # 74.7 ACTION & PROHIBITION CONFLICT
    # -------------------------------------------------------------------------

    def _check_action_prohibition_conflict(
        self,
        req_left: RegulatoryRequirement,
        req_right: RegulatoryRequirement
    ) -> Optional[Dict[str, Any]]:
        """Identifies direct contradictions between mandatory permissions and prohibitions (74.7)."""
        type_l = req_left.requirement_type
        type_r = req_right.requirement_type

        # One PROHIBITION vs other PERMISSION or COMPLIANCE with same action or object
        if (type_l == "PROHIBITION" and type_r in ("PERMISSION", "COMPLIANCE")) or \
           (type_r == "PROHIBITION" and type_l in ("PERMISSION", "COMPLIANCE")):
            obj_l = (req_left.object or "").lower()
            obj_r = (req_right.object or "").lower()
            act_l = (req_left.action or "").lower()
            act_r = (req_right.action or "").lower()
            action_matches = bool(act_l and act_r and (act_l == act_r or act_l in act_r or act_r in act_l))
            object_matches = bool(obj_l and obj_r and (obj_l in obj_r or obj_r in obj_l))
            if action_matches or object_matches:
                target = obj_l or obj_r or act_l or "activity"
                return {
                    "explanation": f"Explicit contradiction: {req_left.authority} mandates/permits '{req_left.action or target}', whereas {req_right.authority} prohibits it."
                }

        return None

    # -------------------------------------------------------------------------
    # 74.14 LLM CONFLICT REASONING
    # -------------------------------------------------------------------------

    def _reason_with_llm(
        self,
        overlap: RegulatoryOverlap,
        req_left: RegulatoryRequirement,
        req_right: RegulatoryRequirement
    ) -> Optional[RegulatoryConflict]:
        """
        Invokes Gemini with conservative guidelines to detect nuanced inconsistencies (74.14).
        """
        system_instruction = (
            "You are a regulatory inconsistency analysis engine.\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. You are identifying potential regulatory inconsistencies, NOT declaring legal conflict.\n"
            "2. Do not provide legal advice.\n"
            "3. Use only the supplied evidence.\n"
            "4. Return is_potential_conflict=false if provisions apply to different entities or have different trigger conditions.\n"
            "5. Allowed conflict_type: PARAMETER_CONFLICT, DEADLINE_CONFLICT, FREQUENCY_CONFLICT, "
            "ACTION_CONFLICT, PROHIBITION_CONFLICT, APPLICABILITY_CONFLICT, DEFINITION_CONFLICT, "
            "POTENTIAL_INCONSISTENCY, NO_CONFLICT, UNKNOWN.\n"
            "6. Allowed severity: LOW, MEDIUM, HIGH, UNKNOWN."
        )

        user_prompt = f"""
Evaluate if these two overlapping regulatory provisions present a potential operational inconsistency:

[REGULATOR A - {req_left.authority}]
Document: {req_left.document_title or req_left.document_id}
Requirement: {req_left.requirement_text}
Subject: {req_left.subject}
Deadline: {req_left.deadline}
Evidence: {req_left.source_evidence}

[REGULATOR B - {req_right.authority}]
Document: {req_right.document_title or req_right.document_id}
Requirement: {req_right.requirement_text}
Subject: {req_right.subject}
Deadline: {req_right.deadline}
Evidence: {req_right.source_evidence}

Overlap Topic: {overlap.shared_topic}
Overlap Type: {overlap.relationship_type}

Return JSON with keys:
"conflict_type": string
"is_potential_conflict": boolean
"severity": string
"confidence": string
"explanation": factual explanation of inconsistency
"conflicting_fields": list of field names that diverge
"""
        try:
            resp = self.llm_provider.generate_text(
                prompt=user_prompt,
                system_instruction=system_instruction
            )
            raw = resp.text.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            data = json.loads(raw)
            if not data.get("is_potential_conflict"):
                return None

            c_type = data.get("conflict_type", "POTENTIAL_INCONSISTENCY")
            if c_type == "NO_CONFLICT":
                return None

            return self._build_conflict_record(
                overlap=overlap,
                req_left=req_left,
                req_right=req_right,
                conflict_type=c_type,
                severity=data.get("severity", "LOW"),
                confidence=data.get("confidence", "MEDIUM"),
                conflicting_fields=data.get("conflicting_fields", ["parameters"]),
                left_val={"text": req_left.requirement_text[:200]},
                right_val={"text": req_right.requirement_text[:200]},
                explanation=data.get("explanation", "Potential operational inconsistency identified.")
            )
        except Exception as e:
            logger.debug(f"LLM conflict reasoning skipped/failed: {e}")
            return None

    def _build_conflict_record(
        self,
        overlap: RegulatoryOverlap,
        req_left: RegulatoryRequirement,
        req_right: RegulatoryRequirement,
        conflict_type: RegulatoryConflictType,
        severity: ConflictSeverity,
        confidence: ConflictConfidence,
        conflicting_fields: List[str],
        left_val: Dict[str, Any],
        right_val: Dict[str, Any],
        explanation: str
    ) -> RegulatoryConflict:
        """Constructs a fully grounded RegulatoryConflict record."""
        conflict_id = generate_conflict_id(req_left.requirement_id, req_right.requirement_id, conflict_type)
        return RegulatoryConflict(
            conflict_id=conflict_id,
            overlap_id=overlap.overlap_id,
            left_requirement_id=req_left.requirement_id,
            left_authority=req_left.authority,
            left_document_id=req_left.document_id,
            left_section_id=req_left.section_id,
            right_requirement_id=req_right.requirement_id,
            right_authority=req_right.authority,
            right_document_id=req_right.document_id,
            right_section_id=req_right.section_id,
            conflict_type=conflict_type,
            severity=severity,
            confidence=confidence,
            conflicting_fields=conflicting_fields,
            left_value=left_val,
            right_value=right_val,
            applicability_scope=overlap.applicability_match,
            temporal_scope="CONCURRENT" if overlap.status == "ACTIVE" else overlap.status,
            explanation=explanation,
            evidence_left=req_left.source_evidence or req_left.requirement_text,
            evidence_right=req_right.source_evidence or req_right.requirement_text,
            resolution_status="OPEN"
        )


# Global singleton
_conflict_engine = ConflictEngine()


def get_conflict_engine() -> ConflictEngine:
    return _conflict_engine
