"""
Domain Data Models for Cross-Regulator Conflicts & Inconsistencies (Phase 74).

Defines:
- 74.1: Controlled Conflict Types (PARAMETER_CONFLICT, DEADLINE_CONFLICT, ACTION_CONFLICT, etc.)
- 74.2: RegulatoryConflict model with bidirectional traceability to requirements and overlaps.
- 74.16, 74.18: Conflict resolution status and human audit trail.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

# =============================================================================
# 74.1 CONFLICT TAXONOMY & ENUMS
# =============================================================================

RegulatoryConflictType = Literal[
    "PARAMETER_CONFLICT",
    "DEADLINE_CONFLICT",
    "FREQUENCY_CONFLICT",
    "ACTION_CONFLICT",
    "PROHIBITION_CONFLICT",
    "APPLICABILITY_CONFLICT",
    "DEFINITION_CONFLICT",
    "SEQUENCING_CONFLICT",
    "POTENTIAL_INCONSISTENCY",
    "NO_CONFLICT",
    "UNKNOWN"
]

ConflictSeverity = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
    "UNKNOWN"
]

ConflictConfidence = Literal[
    "HIGH",
    "MEDIUM",
    "LOW",
    "UNKNOWN"
]

ConflictResolutionStatus = Literal[
    "OPEN",
    "UNDER_REVIEW",
    "RESOLVED",
    "DISMISSED",
    "FALSE_POSITIVE",
    "UNKNOWN"
]


class ConflictReviewEvent(BaseModel):
    """Immutable record of human compliance officer review action (74.18)."""
    reviewer_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    previous_status: str
    new_status: str
    notes: Optional[str] = None


class RegulatoryConflict(BaseModel):
    """
    Structured, evidence-grounded Potential Regulatory Inconsistency record (Phase 74).
    Derived strictly from verified regulatory overlaps, never raw semantic similarity.
    """
    conflict_id: str

    # Reference to parent overlap (74.2, 74.3)
    overlap_id: Optional[str] = None

    # Left requirement & obligation provenance
    left_requirement_id: str
    left_obligation_id: Optional[str] = None
    left_authority: str
    left_document_id: Optional[str] = None
    left_section_id: Optional[str] = None

    # Right requirement & obligation provenance
    right_requirement_id: str
    right_obligation_id: Optional[str] = None
    right_authority: str
    right_document_id: Optional[str] = None
    right_section_id: Optional[str] = None

    # Conflict Classification & Grading (74.1, 74.11, 74.12)
    conflict_type: RegulatoryConflictType = "POTENTIAL_INCONSISTENCY"
    severity: ConflictSeverity = "MEDIUM"
    confidence: ConflictConfidence = "MEDIUM"

    # Specific divergent dimensions
    conflicting_fields: List[str] = Field(default_factory=list)  # e.g., ["deadline", "threshold", "action"]
    left_value: Dict[str, Any] = Field(default_factory=dict)
    right_value: Dict[str, Any] = Field(default_factory=dict)

    # Scopes & Context
    applicability_scope: Optional[str] = None  # e.g., "SAME_ENTITIES", "DIFFERENT_ENTITIES"
    temporal_scope: Optional[str] = None       # e.g., "CONCURRENT", "HISTORICAL"
    explanation: str = ""

    # Immutable source evidence (74.15)
    evidence_left: str
    evidence_right: str

    # Review workflow and audit trail (74.16, 74.18)
    resolution_status: ConflictResolutionStatus = "OPEN"
    review_history: List[ConflictReviewEvent] = Field(default_factory=list)

    # Metadata & Schema Versioning
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    conflict_schema_version: str = "1.0.0"
