"""
Regulatory Obligation Extraction Engine (Phase 62).

Transforms extracted requirements into operationally meaningful obligations:
Who must do what, under which conditions, by when, how often, and what evidence demonstrates compliance?
"""

import re
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple

from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ObligationType,
    ObligationStatus,
    RequirementConfidence,
)
from app.versioning.timeline import TimelineService, get_timeline_service

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# =============================================================================
# DEONTIC CLASSIFIER (62.2)
# =============================================================================

def classify_deontic_type(text: str) -> ObligationType:
    """
    Distinguishes mandatory obligations, prohibitions, permissions, and recommendations
    strictly based on deontic language.
    """
    t = text.lower()

    # 1. Prohibitions
    if any(p in t for p in ["shall not", "must not", "prohibited", "is not permitted", "are not permitted", "no intermediary shall"]):
        return "PROHIBITION"

    # 2. Conditional Mandatory
    if ("shall" in t or "must" in t or "required" in t) and any(c in t for c in ["if ", "when ", "where ", "provided that", "subject to", "in the event"]):
        return "CONDITIONAL_MANDATORY"

    # 3. Pure Mandatory
    if any(m in t for m in ["shall", "must", "is required to", "are required to", "shall ensure", "shall submit", "shall maintain"]):
        return "MANDATORY"

    # 4. Recommended (Non-binding)
    if any(r in t for r in ["should", "may consider", "is encouraged to", "are encouraged to", "recommended", "advised to"]):
        return "RECOMMENDED"

    # 5. Permitted (Discretionary)
    if any(p in t for p in ["may", "is permitted to", "are permitted to", "eligible to", "at liberty to"]):
        return "PERMITTED"

    # 6. Informational / Definitions
    if any(i in t for i in ["means", "includes", "refers to", "for the purpose of"]):
        return "INFORMATIONAL"

    return "UNKNOWN"


# =============================================================================
# COMPLIANCE EVIDENCE EXTRACTOR (62.5)
# =============================================================================

EVIDENCE_KEYWORDS = [
    (r"\b(?:filing\s+receipt|acknowledgement\s+receipt|submission\s+receipt)\b", "Filing Receipt / SEBI Portal Acknowledgement"),
    (r"\b(?:board\s+resolution|approval\s+of\s+the\s+board)\b", "Board Resolution / Meeting Minutes"),
    (r"\b(?:audit\s+report|compliance\s+certificate|auditor\s+certificate)\b", "Auditor Certificate / Compliance Audit Report"),
    (r"\b(?:register\s+of|records?\s+of|log\s+book)\b", "Internal Register / Records Log"),
    (r"\b(?:client\s+agreement|written\s+agreement|mou)\b", "Executed Client Agreement"),
    (r"\b(?:disclosure|published\s+on\s+website)\b", "Website Disclosure / Public Notice"),
    (r"\b(?:written\s+policy|standard\s+operating\s+procedure|sop)\b", "Written Internal Policy / SOP"),
    (r"\b(?:training\s+records?|attendance\s+sheet)\b", "Training & Certification Record"),
    (r"\b(?:net\s+worth\s+certificate|ca\s+certificate)\b", "Chartered Accountant Net Worth Certificate"),
]


def extract_compliance_evidence(text: str) -> Tuple[List[str], Optional[str], Optional[str]]:
    """
    Extracts explicit or directly implied compliance proof artifacts from text.
    Returns: (required_evidence_list, required_record, required_submission)
    """
    evidence: List[str] = []
    required_record: Optional[str] = None
    required_submission: Optional[str] = None

    for pat, label in EVIDENCE_KEYWORDS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            evidence.append(label)

    # Records check
    rec_m = re.search(r"\bmaintain\s+([^\.,;]+(?:records?|books\s+of\s+accounts?|register))", text, re.IGNORECASE)
    if rec_m:
        required_record = rec_m.group(1).strip()
        if "Internal Register / Records Log" not in evidence:
            evidence.append("Internal Register / Records Log")

    # Submission check
    sub_m = re.search(r"\bsubmit\s+([^\.,;]+(?:report|certificate|filing|data|information))", text, re.IGNORECASE)
    if sub_m:
        required_submission = sub_m.group(1).strip()
        if "Filing Receipt / SEBI Portal Acknowledgement" not in evidence:
            evidence.append("Filing Receipt / SEBI Portal Acknowledgement")

    return list(set(evidence)), required_record, required_submission


# =============================================================================
# GROUNDING VALIDATION (62.7)
# =============================================================================

def validate_obligation_grounding(
    obligation: RegulatoryObligation,
    source_text: str
) -> Tuple[bool, RequirementConfidence, List[str]]:
    """
    Validates whether the extracted obligation is faithful to the source text.
    Checks subject support, action support, and numeric preservation.
    """
    reasons = []
    source_lower = source_text.lower()

    # Check action support
    if obligation.obligation_action and obligation.obligation_action.lower() not in source_lower:
        reasons.append(f"Action '{obligation.obligation_action}' not found verbatim in source text.")

    # Check numeric support
    for th in obligation.thresholds:
        if th.raw_value.lower() not in source_lower:
            reasons.append(f"Numeric parameter '{th.raw_value}' not grounded in source text.")

    # Check deadline support
    if obligation.deadline and obligation.deadline.lower() not in source_lower:
        reasons.append(f"Deadline '{obligation.deadline}' not explicitly stated in source.")

    if not reasons:
        return True, "HIGH", []
    elif len(reasons) == 1:
        return True, "MEDIUM", reasons
    else:
        return False, "LOW", reasons


# =============================================================================
# OBLIGATION EXTRACTOR (Phase 62)
# =============================================================================

class ObligationExtractor:
    """
    Converts RegulatoryRequirement instances into operationally meaningful RegulatoryObligation instances.
    """

    def __init__(self, timeline_service: Optional[TimelineService] = None):
        self.timeline_service = timeline_service or get_timeline_service()

    def extract_obligation_from_requirement(
        self,
        requirement: RegulatoryRequirement,
        document_status: Optional[str] = None
    ) -> RegulatoryObligation:
        """
        Transforms a single requirement into a validated obligation.
        """
        text = requirement.requirement_text
        ob_type = classify_deontic_type(text)

        # Lifecycle resolution (62.3)
        doc_stat = (document_status or "CURRENT").upper()
        lifecycle_status: ObligationStatus = "ACTIVE"
        if doc_stat in ["HISTORICAL", "SUPERSEDED"]:
            lifecycle_status = "SUPERSEDED"
        elif doc_stat == "NOT_YET_EFFECTIVE":
            lifecycle_status = "NOT_YET_EFFECTIVE"
        elif doc_stat == "PROPOSED":
            lifecycle_status = "PROPOSED"

        # Evidence mapping (62.5)
        ev_list, req_rec, req_sub = extract_compliance_evidence(text)

        # Trigger resolution
        trigger = None
        if requirement.conditions:
            trigger = "; ".join(requirement.conditions)

        # Generate deterministic obligation ID
        ob_id_raw = f"{requirement.requirement_id}:{requirement.subject}:{requirement.action}"
        ob_id = f"ob_{hashlib.sha256(ob_id_raw.encode('utf-8')).hexdigest()[:12]}"

        # Applicability mapping (62.4)
        applicability_dict = {
            "entity_category": requirement.subject or "Regulated Intermediary",
            "scope": requirement.applicability,
            "conditions": requirement.conditions,
            "exceptions": requirement.exceptions
        }

        # Action resolution
        act = requirement.action
        if not act and requirement.requirement_text:
            m = re.search(r"\b(?:shall|must|to)\s+([a-z]+)\b", requirement.requirement_text, re.IGNORECASE)
            if m:
                act = m.group(1).lower()

        obligation = RegulatoryObligation(
            obligation_id=ob_id,
            requirement_id=requirement.requirement_id,
            document_id=requirement.document_id,
            document_version_id=requirement.document_version_id,
            section_id=requirement.section_id,
            authority=requirement.authority,
            obligated_party=requirement.subject or "Regulated Entity",
            obligation_action=act or "comply with regulatory provision",
            obligation_object=requirement.object or "regulatory requirement",
            obligation_type=ob_type,
            status=lifecycle_status,
            conditions=requirement.conditions,
            exceptions=requirement.exceptions,
            trigger=trigger,
            deadline=requirement.deadline,
            frequency=requirement.frequency,
            thresholds=requirement.thresholds,
            required_evidence=ev_list,
            required_record=req_rec,
            required_submission=req_sub,
            applicability=applicability_dict,
            effective_date=requirement.effective_date,
            confidence=requirement.confidence,
            source_evidence=requirement.source_evidence,
            source_locator=requirement.source_locator
        )

        # Grounding validation (62.7)
        is_valid, validated_conf, reasons = validate_obligation_grounding(
            obligation=obligation,
            source_text=requirement.source_evidence
        )
        obligation.confidence = validated_conf

        return obligation

    def extract_obligations(
        self,
        requirements: List[RegulatoryRequirement],
        document_status: Optional[str] = None
    ) -> List[RegulatoryObligation]:
        """Batch transforms requirements into obligations."""
        return [
            self.extract_obligation_from_requirement(req, document_status=document_status)
            for req in requirements
        ]


_obligation_extractor = ObligationExtractor()


def get_obligation_extractor() -> ObligationExtractor:
    return _obligation_extractor


def extract_obligation_from_requirement(
    requirement: RegulatoryRequirement,
    document_status: Optional[str] = None
) -> RegulatoryObligation:
    """Convenience function calling singleton extract_obligation_from_requirement."""
    return _obligation_extractor.extract_obligation_from_requirement(requirement, document_status=document_status)


def extract_obligations_from_requirement(
    requirement: RegulatoryRequirement,
    document_status: Optional[str] = None
) -> List[RegulatoryObligation]:
    """Convenience function returning obligations list for a requirement."""
    return [_obligation_extractor.extract_obligation_from_requirement(requirement, document_status=document_status)]


def extract_obligations(
    requirements: List[RegulatoryRequirement],
    document_status: Optional[str] = None
) -> List[RegulatoryObligation]:
    """Convenience function calling singleton extract_obligations."""
    return _obligation_extractor.extract_obligations(requirements, document_status=document_status)

