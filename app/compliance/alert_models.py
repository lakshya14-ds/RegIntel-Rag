"""
Domain Data Models for Regulatory Alerts & Deadline Intelligence (Phase 65).

Defines:
- 65.1: RegulatoryEvent model and controlled event types.
- 65.2 & 65.3: RegulatoryDeadline model with explicit vs calculated due dates.
- 65.4: Recurrence rule representation for recurring obligations.
- 65.5, 65.6, 65.18, 65.19: RegulatoryAlert model, conservative severity, explainability, and safety.
- 65.9: User Watchlist model.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# =============================================================================
# TAXONOMIES & ENUMS (65.1, 65.3, 65.6, 65.16)
# =============================================================================

RegulatoryEventType = Literal[
    "NEW_REGULATION",
    "REGULATION_EFFECTIVE",
    "REGULATION_AMENDED",
    "REGULATION_SUPERSEDED",
    "REGULATION_REPEALED",
    "NEW_REQUIREMENT",
    "MODIFIED_REQUIREMENT",
    "NEW_OBLIGATION",
    "OBLIGATION_CHANGED",
    "COMPLIANCE_DEADLINE",
    "UPCOMING_EFFECTIVE_DATE"
]

DeadlineType = Literal[
    "ABSOLUTE",
    "RELATIVE",
    "RECURRING",
    "EVENT_RELATIVE",
    "PERIODIC",
    "UNKNOWN"
]

DeadlineStatus = Literal[
    "UPCOMING",
    "DUE_SOON",
    "DUE_TODAY",
    "OVERDUE",
    "COMPLETED",
    "NOT_APPLICABLE",
    "UNKNOWN"
]

AlertSeverity = Literal[
    "CRITICAL",
    "HIGH",
    "MEDIUM",
    "LOW",
    "INFO"
]

AlertStatus = Literal[
    "UNREAD",
    "READ",
    "DISMISSED"
]

NotificationChannel = Literal[
    "IN_APP",
    "EMAIL",
    "WEBHOOK"
]


# =============================================================================
# CORE MODELS (65.1, 65.3, 65.5, 65.9, 65.18)
# =============================================================================

class RegulatoryEvent(BaseModel):
    """
    Normalized internal Regulatory Event (65.1).
    Bridges regulatory changes, effective dates, requirements, obligations, and checklists.
    """
    event_id: str
    event_type: RegulatoryEventType
    document_id: str
    document_version_id: Optional[str] = "1.0"

    requirement_ids: List[str] = Field(default_factory=list)
    obligation_ids: List[str] = Field(default_factory=list)
    checklist_item_ids: List[str] = Field(default_factory=list)

    event_date: Optional[str] = None      # When the event occurred / was published
    effective_date: Optional[str] = None  # When the change becomes active
    deadline: Optional[str] = None        # Compliance deadline if attached

    title: str
    summary: str
    severity: AlertSeverity = "INFO"

    source_reference: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class RegulatoryDeadline(BaseModel):
    """
    Normalized Compliance Deadline (65.2, 65.3).
    Answers: What obligation is due, by when, how was it calculated, and is it recurring?
    """
    deadline_id: str
    obligation_id: str
    requirement_id: Optional[str] = None
    document_id: str

    deadline_type: DeadlineType = "ABSOLUTE"
    trigger_event: Optional[str] = None
    deadline_expression: str

    due_date: Optional[str] = None  # Normalized YYYY-MM-DD
    due_date_derivation: Literal["EXPLICIT", "CALCULATED", "INFERRED", "UNKNOWN"] = "EXPLICIT"

    frequency: Optional[str] = None  # MONTHLY, QUARTERLY, HALF_YEARLY, ANNUALLY
    grace_period: Optional[str] = None

    source_evidence: str
    confidence: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"] = "HIGH"

    status: DeadlineStatus = "UPCOMING"
    days_remaining: Optional[int] = None
    recurrence_rule: Optional[Dict[str, Any]] = None

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AlertExplanation(BaseModel):
    """
    Structured explainability payload for alerts (65.18).
    Answers: Why am I seeing this? What changed? When does it become effective?
    """
    why_am_i_seeing_this: str
    what_changed: Optional[str] = None
    when_effective: Optional[str] = None
    affected_requirement: Optional[str] = None
    affected_obligation: Optional[str] = None
    action_recommended: Optional[str] = None
    source: Optional[str] = None


class RegulatoryAlert(BaseModel):
    """
    Persistent, deduplicated Regulatory Alert (65.5, 65.10, 65.18).
    Surfaces actionable compliance events without unsupported legal claims (65.19).
    """
    alert_id: str
    dedup_hash: str
    alert_type: str
    severity: AlertSeverity = "INFO"

    title: str
    message: str

    event_id: Optional[str] = None
    document_id: Optional[str] = None
    requirement_id: Optional[str] = None
    obligation_id: Optional[str] = None
    checklist_item_id: Optional[str] = None

    trigger_date: str
    effective_date: Optional[str] = None
    deadline: Optional[str] = None

    source_reference: Dict[str, Any] = Field(default_factory=dict)
    explanation: AlertExplanation

    status: AlertStatus = "UNREAD"
    channel: NotificationChannel = "IN_APP"

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    read_at: Optional[str] = None
    dismissed_at: Optional[str] = None


class Watchlist(BaseModel):
    """
    User Regulatory Watchlist (65.9).
    Filters alerts by authority, document, topic, requirement, or event type.
    """
    watchlist_id: str
    user_id: str = "default_user"
    name: str

    authorities: List[str] = Field(default_factory=list)      # e.g. ["SEBI", "RBI"]
    document_ids: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)            # e.g. ["Intermediary", "ESG"]
    requirement_types: List[str] = Field(default_factory=list) # e.g. ["REPORTING", "DISCLOSURE"]
    obligation_types: List[str] = Field(default_factory=list)  # e.g. ["MANDATORY", "PROHIBITION"]
    event_types: List[str] = Field(default_factory=list)       # e.g. ["REGULATION_EFFECTIVE", "COMPLIANCE_DEADLINE"]

    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
