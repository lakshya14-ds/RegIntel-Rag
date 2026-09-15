"""
Domain Data Models for Regulatory Requirements, Obligations, and Compliance Checklists (Phases 61, 62, 63).

Defines:
- Phase 61: RegulatoryRequirement, RequirementType, RequirementThreshold
- Phase 62: RegulatoryObligation, ObligationType, ObligationStatus
- Phase 63: ComplianceChecklist, ChecklistItem, ChecklistStatus
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# =============================================================================
# PHASE 61: REGULATORY REQUIREMENTS ONTOLOGY (61.1, 61.2)
# =============================================================================

RequirementType = Literal[
    "REPORTING",
    "DISCLOSURE",
    "RECORD_KEEPING",
    "APPROVAL",
    "NOTIFICATION",
    "PROHIBITION",
    "PERMISSION",
    "CALCULATION",
    "COMPLIANCE",
    "GOVERNANCE",
    "DOCUMENTATION",
    "MONITORING",
    "AUDIT",
    "SUBMISSION",
    "MAINTENANCE",
    "PROCEDURAL",
    "OTHER"
]

RequirementConfidence = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]

RequirementDiffStatus = Literal[
    "ADDED_REQUIREMENT",
    "REMOVED_REQUIREMENT",
    "MODIFIED_REQUIREMENT",
    "UNCHANGED_REQUIREMENT"
]


class RequirementThreshold(BaseModel):
    """Structured numeric, financial, percentage, or duration parameters."""
    parameter_type: str  # duration, percentage, currency, ratio, date, limit
    raw_value: str       # e.g. "15 days", "₹50 Lakhs", "10%"
    normalized_value: Optional[float] = None
    unit: Optional[str] = None  # days, months, years, INR, percent
    operator: Optional[str] = None  # >=, <=, ==, minimum, maximum


class RegulatoryRequirement(BaseModel):
    """
    Structured, evidence-grounded Regulatory Requirement (Phase 61).
    Represents an atomic, normalized requirement extracted from a regulatory instrument.
    """
    requirement_id: str
    document_id: str
    document_version_id: Optional[str] = "1.0"
    section_id: Optional[str] = None
    chunk_id: Optional[str] = None

    # Context & Authority
    authority: str = "SEBI"
    document_type: Optional[str] = None
    document_title: Optional[str] = None

    # Exact Text & Normalized Semantic Form
    requirement_text: str
    normalized_requirement: Optional[str] = None

    # Controlled Classification & Syntax
    requirement_type: RequirementType = "COMPLIANCE"
    subject: Optional[str] = None     # e.g. "intermediary", "investment adviser"
    action: Optional[str] = None      # e.g. "submit", "maintain", "disclose"
    object: Optional[str] = None      # e.g. "quarterly report", "records"

    # Applicability & Qualification
    applicability: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)

    # Temporal & Numeric Rules
    effective_date: Optional[str] = None
    deadline: Optional[str] = None
    frequency: Optional[str] = None

    thresholds: List[RequirementThreshold] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)

    # Provenance & Evidence Traceability
    source_evidence: str
    source_locator: Dict[str, Any] = Field(default_factory=dict)  # page, section_num, heading

    # Metadata & Quality
    confidence: RequirementConfidence = "HIGH"
    extraction_method: Literal["DETERMINISTIC", "LLM", "HYBRID"] = "HYBRID"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    # Extraction Versioning
    requirement_schema_version: str = "1.0.0"
    extraction_prompt_version: str = "1.0.0"
    content_hash: Optional[str] = None


# =============================================================================
# PHASE 62: REGULATORY OBLIGATIONS (62.1, 62.2, 62.3)
# =============================================================================

ObligationType = Literal[
    "MANDATORY",
    "CONDITIONAL_MANDATORY",
    "PROHIBITION",
    "PERMITTED",
    "RECOMMENDED",
    "INFORMATIONAL",
    "UNKNOWN"
]

ObligationStatus = Literal[
    "ACTIVE",
    "PROPOSED",
    "NOT_YET_EFFECTIVE",
    "SUPERSEDED",
    "REPEALED",
    "UNKNOWN"
]


class RegulatoryObligation(BaseModel):
    """
    Operationally Meaningful Regulatory Obligation (Phase 62).
    Answers: Who must do what, under what conditions, by when, and what evidence proves compliance?
    """
    obligation_id: str
    requirement_id: str

    document_id: str
    document_version_id: Optional[str] = "1.0"
    section_id: Optional[str] = None
    authority: str = "SEBI"

    # Operational Who / What / Object
    obligated_party: Optional[str] = None
    obligation_action: Optional[str] = None
    obligation_object: Optional[str] = None

    # Deontic Nature & Lifecycle
    obligation_type: ObligationType = "MANDATORY"
    status: ObligationStatus = "ACTIVE"

    # Conditions & Triggers
    conditions: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    trigger: Optional[str] = None

    # Temporal & Thresholds
    deadline: Optional[str] = None
    frequency: Optional[str] = None
    thresholds: List[RequirementThreshold] = Field(default_factory=list)

    # Compliance Evidence Requirements
    required_evidence: List[str] = Field(default_factory=list)
    required_record: Optional[str] = None
    required_submission: Optional[str] = None

    # Scope & Applicability
    applicability: Dict[str, Any] = Field(default_factory=dict)
    effective_date: Optional[str] = None

    # Confidence & Provenance
    confidence: RequirementConfidence = "HIGH"
    source_evidence: str
    source_locator: Dict[str, Any] = Field(default_factory=dict)

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    obligation_schema_version: str = "1.0.0"


# =============================================================================
# PHASE 63: COMPLIANCE CHECKLISTS (63.1, 63.2)
# =============================================================================

ChecklistStatus = Literal[
    "NOT_REVIEWED",
    "COMPLIANT",
    "NON_COMPLIANT",
    "PARTIALLY_COMPLIANT",
    "NOT_APPLICABLE",
    "NEEDS_REVIEW",
    "UNKNOWN"
]


class ChecklistItem(BaseModel):
    """An individual actionable item inside a compliance checklist (Phase 63)."""
    item_id: str
    obligation_id: str
    requirement_id: str

    document_id: str
    section_id: Optional[str] = None
    authority: str = "SEBI"

    # Actionable Control Question & Target
    control_question: str
    compliance_action: str

    # Execution Parameters
    obligated_party: Optional[str] = None
    frequency: Optional[str] = None
    deadline: Optional[str] = None
    applicability: Optional[str] = None

    # Evidentiary Requirements
    evidence_required: List[str] = Field(default_factory=list)

    # Source Provenance
    source_reference: Dict[str, Any] = Field(default_factory=dict)

    # Review State
    status: ChecklistStatus = "NOT_REVIEWED"
    notes: Optional[str] = None
    confidence: RequirementConfidence = "HIGH"

    # Change Propagation (Cross-Phase 59/60 Integration)
    is_changed: bool = False
    change_summary: Optional[str] = None

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ComplianceChecklist(BaseModel):
    """
    Evidence-grounded Regulatory Compliance Checklist (Phase 63).
    """
    checklist_id: str
    title: str
    description: Optional[str] = None

    # Regulatory Context
    regulatory_scope: str = "SEBI Regulations"
    authority: str = "SEBI"
    document_ids: List[str] = Field(default_factory=list)
    document_versions: Dict[str, str] = Field(default_factory=dict)

    # Items
    items: List[ChecklistItem] = Field(default_factory=list)

    # Audit & Progress
    completion_rate: float = 0.0  # Percentage 0.0 - 100.0
    summary_counts: Dict[str, int] = Field(default_factory=dict)

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    checklist_schema_version: str = "1.0.0"

    def recalculate_metrics(self) -> None:
        """Calculates item counts and checklist completion rate accurately."""
        counts = {
            "NOT_REVIEWED": 0,
            "COMPLIANT": 0,
            "NON_COMPLIANT": 0,
            "PARTIALLY_COMPLIANT": 0,
            "NOT_APPLICABLE": 0,
            "NEEDS_REVIEW": 0,
            "UNKNOWN": 0,
            "TOTAL": len(self.items)
        }
        for item in self.items:
            counts[item.status] = counts.get(item.status, 0) + 1

        total = len(self.items)
        reviewed = total - counts["NOT_REVIEWED"]
        self.completion_rate = round((reviewed / total * 100.0), 1) if total > 0 else 0.0
        self.summary_counts = counts
