"""
Domain Data Models for Regulatory Effective-Date Intelligence (Phase 64).

Defines formal models for regulatory dates, date events, temporal derivations,
effective states, historical evaluations, and temporal conflicts.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# =============================================================================
# TAXONOMIES & ENUMS (64.1, 64.2, 64.7, 64.8, 64.17)
# =============================================================================

RegulatoryDateType = Literal[
    "PUBLISHED",
    "NOTIFIED",
    "ISSUED",
    "EFFECTIVE",
    "COMMENCEMENT",
    "EXPIRES",
    "SUPERSEDES",
    "REPEALED",
    "WITHDRAWN",
    "APPLICABLE_FROM",
    "APPLICABLE_UNTIL",
    "DEADLINE",
    "REFERENCE",
    "UNKNOWN"
]

DatePrecision = Literal[
    "DAY",
    "MONTH",
    "YEAR",
    "PERIOD"
]

TemporalDerivationType = Literal[
    "EXPLICIT",   # Directly stated in source text
    "DERIVED",    # Mathematically derived from an explicit rule (e.g. 30 days from publication)
    "INFERRED",   # Inferred from contextual/weak evidence
    "UNKNOWN"     # Cannot be safely determined
]

TemporalConfidence = Literal[
    "HIGH",
    "MEDIUM",
    "LOW",
    "UNKNOWN"
]

ExtractionMethod = Literal[
    "DETERMINISTIC",
    "LLM",
    "DERIVED",
    "HYBRID"
]

RegulatoryEffectiveState = Literal[
    "NOT_YET_EFFECTIVE",
    "EFFECTIVE",
    "EXPIRED",
    "SUPERSEDED",
    "REPEALED",
    "WITHDRAWN",
    "UNKNOWN"
]

DateConflictSeverity = Literal[
    "WARNING",
    "ERROR",
    "UNKNOWN"
]


# =============================================================================
# CORE TEMPORAL MODELS (64.2, 64.6, 64.16)
# =============================================================================

class RegulatoryDateEvent(BaseModel):
    """
    Structured internal model representing an atomic regulatory date event (64.2).
    Captures exact provenance, semantic event type, derivation rules, and confidence.
    """
    event_id: str
    document_id: str
    document_version_id: Optional[str] = "1.0"
    section_id: Optional[str] = None

    event_type: RegulatoryDateType = "EFFECTIVE"
    date: Optional[str] = None  # Normalized ISO format: YYYY-MM-DD
    date_precision: DatePrecision = "DAY"

    # Provenance & Evidence (64.6)
    source_text: str
    source_locator: Dict[str, Any] = Field(default_factory=dict)  # page, section_num, heading

    confidence: TemporalConfidence = "HIGH"
    extraction_method: ExtractionMethod = "DETERMINISTIC"
    extraction_version: str = "1.0.0"

    # Explicit vs Derived vs Inferred (64.7)
    derivation_type: TemporalDerivationType = "EXPLICIT"
    derivation_rule: Optional[str] = None  # e.g., "publication_date + 30 days"
    base_event_type: Optional[str] = None   # e.g., "PUBLISHED"
    offset_days: Optional[int] = None       # e.g., 30

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class DateConflict(BaseModel):
    """
    Represents a detected contradiction or anomaly in regulatory dates (64.16, 64.17).
    """
    document_id: str
    document_version_id: Optional[str] = "1.0"
    event_type: str
    conflicting_values: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: str
    severity: DateConflictSeverity = "WARNING"
    resolution_status: str = "UNRESOLVED"  # UNRESOLVED, RESOLVED, MANUAL_OVERRIDE
    notes: Optional[str] = None


class TemporalStateEvaluation(BaseModel):
    """
    Result of evaluating the effective regulatory state for a document as of a specific date (64.8, 64.9).
    """
    document_id: str
    document_version_id: Optional[str] = "1.0"
    as_of_date: str  # YYYY-MM-DD
    state: RegulatoryEffectiveState = "UNKNOWN"

    effective_date: Optional[str] = None
    published_date: Optional[str] = None
    expiry_date: Optional[str] = None
    superseded_date: Optional[str] = None

    derivation_type: TemporalDerivationType = "UNKNOWN"
    reason: str
    conflicts: List[DateConflict] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class RequirementTemporalState(BaseModel):
    """
    Effective-date-aware status evaluation for an individual requirement (64.10).
    """
    requirement_id: str
    document_id: str
    as_of_date: str
    is_active: bool
    state: str  # e.g. ACTIVE, NOT_YET_EFFECTIVE, SUPERSEDED, EXPIRED, UNKNOWN
    effective_date: Optional[str] = None
    superseded_date: Optional[str] = None
    reason: str


class ObligationTemporalState(BaseModel):
    """
    Effective-date-aware status evaluation for an individual obligation (64.11).
    """
    obligation_id: str
    requirement_id: str
    document_id: str
    as_of_date: str
    status: str  # FUTURE, ACTIVE, HISTORICAL, SUPERSEDED, EXPIRED, UNKNOWN
    effective_date: Optional[str] = None
    days_until_effective: Optional[int] = None
    reason: str


class ChecklistItemTemporalState(BaseModel):
    """
    Effective-date-aware status evaluation for a checklist item (64.12).
    """
    item_id: str
    obligation_id: str
    as_of_date: str
    temporal_status: str  # ACTIVE, UPCOMING, HISTORICAL, NOT_YET_APPLICABLE, SUPERSEDED, UNKNOWN
    effective_date: Optional[str] = None
    days_until_effective: Optional[int] = None
    is_actionable_now: bool
