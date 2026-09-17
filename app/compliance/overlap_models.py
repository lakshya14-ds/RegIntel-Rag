"""
Domain Data Models for Regulatory Overlap Detection (Phase 73).

Defines:
- 73.1: Controlled Overlap Ontology (IDENTICAL, NEAR_DUPLICATE, OVERLAPPING, COMPLEMENTARY, RELATED, DISTINCT, UNKNOWN).
- 73.2: RegulatoryOverlap model with complete bidirectional regulatory provenance.
- 73.5: Controlled Regulatory Topic Taxonomy.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

# =============================================================================
# 73.1 OVERLAP ONTOLOGY & 73.5 TOPIC TAXONOMY
# =============================================================================

OverlapType = Literal[
    "IDENTICAL",
    "NEAR_DUPLICATE",
    "OVERLAPPING",
    "COMPLEMENTARY",
    "RELATED",
    "DISTINCT",
    "UNKNOWN"
]

OverlapConfidence = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]

OverlapStatus = Literal[
    "ACTIVE",
    "HISTORICAL",
    "FUTURE",
    "UNKNOWN",
    "SUPERSEDED"
]

# Controlled, extensible taxonomy of financial regulatory topics (73.5)
CONTROLLED_REGULATORY_TOPICS = [
    "REPORTING",
    "DISCLOSURE",
    "KYC",
    "AML",
    "RISK_MANAGEMENT",
    "GOVERNANCE",
    "RECORD_KEEPING",
    "AUDIT",
    "CYBERSECURITY",
    "DATA_PROTECTION",
    "CUSTOMER_PROTECTION",
    "CAPITAL",
    "LIQUIDITY",
    "INVESTMENT",
    "TRANSACTION_MONITORING",
    "LICENSING",
    "REGISTRATION",
    "OUTSOURCING",
    "INCIDENT_REPORTING",
    "OTHER"
]


class RegulatoryOverlap(BaseModel):
    """
    Structured, evidence-grounded Regulatory Overlap record (Phase 73).
    Captures substantive cross-regulator relationship between two requirements/obligations.
    """
    overlap_id: str

    # Left requirement provenance (73.2, 73.3)
    left_authority: str
    left_document_id: str
    left_document_version_id: Optional[str] = "1.0"
    left_section_id: Optional[str] = None
    left_requirement_id: str
    left_obligation_id: Optional[str] = None

    # Right requirement provenance (73.2, 73.3)
    right_authority: str
    right_document_id: str
    right_document_version_id: Optional[str] = "1.0"
    right_section_id: Optional[str] = None
    right_requirement_id: str
    right_obligation_id: Optional[str] = None

    # Classification & Ontological Semantics (73.1, 73.5)
    relationship_type: OverlapType = "RELATED"
    shared_topic: Optional[str] = None
    shared_activity: Optional[str] = None

    # Scores & Reasoning (73.6, 73.7, 73.15)
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: OverlapConfidence = "MEDIUM"
    reasoning: str = ""

    # Immutable source evidence (73.2, 73.15)
    evidence_left: str
    evidence_right: str

    # Temporal Scope (73.13, 73.14)
    effective_date_left: Optional[str] = None
    effective_date_right: Optional[str] = None
    status: OverlapStatus = "ACTIVE"

    # Numeric & Applicability Attributes (73.11, 73.12)
    applicability_match: Optional[str] = None  # e.g., "SAME_ENTITIES", "DIFFERENT_ENTITIES", "UNKNOWN"
    parameter_comparison: Dict[str, Any] = Field(default_factory=dict)

    # Schema & Pipeline Versioning
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    overlap_schema_version: str = "1.0.0"
    analysis_method: Literal["DETERMINISTIC", "HYBRID", "LLM"] = "HYBRID"
    analysis_model: Optional[str] = "gemini-embedding-001+gemini"

    @property
    def id(self) -> str:
        return self.overlap_id

    @property
    def left_evidence(self) -> str:
        return self.evidence_left

    @property
    def right_evidence(self) -> str:
        return self.evidence_right

    @property
    def topic(self) -> Optional[str]:
        return self.shared_topic

    @property
    def explanation(self) -> str:
        return self.reasoning
