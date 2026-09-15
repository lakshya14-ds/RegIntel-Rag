"""
Regulatory Effective-State Intelligence Engine (Phase 64).

Provides:
- 64.8: get_regulatory_state(document_data, as_of_date) evaluating multi-state temporal conditions.
- 64.9: Historical state query evaluation across arbitrary reference dates.
- 64.10: Requirement temporal state evaluation.
- 64.11: Obligation temporal state evaluation (ACTIVE, FUTURE, HISTORICAL, SUPERSEDED, EXPIRED).
- 64.12: Compliance checklist temporal state evaluation (ACTIVE, UPCOMING, HISTORICAL, SUPERSEDED).
- 64.16 & 64.17: Date conflict detection and cross-version temporal consistency validation.
"""

import re
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel

from app.compliance.temporal_models import (
    RegulatoryDateEvent,
    TemporalStateEvaluation,
    RequirementTemporalState,
    ObligationTemporalState,
    ChecklistItemTemporalState,
    DateConflict,
    DateConflictSeverity,
    RegulatoryEffectiveState,
)
from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ComplianceChecklist,
    ChecklistItem,
)
from app.versioning.timeline import TimelineService, determine_document_status

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _is_valid_iso_date(d: Optional[str]) -> bool:
    if not d or not isinstance(d, str):
        return False
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", d.strip()))


def calculate_days_delta(target_date: Optional[str], as_of_date: str) -> Optional[int]:
    """Returns (target_date - as_of_date) in days."""
    if not _is_valid_iso_date(target_date) or not _is_valid_iso_date(as_of_date):
        return None
    try:
        t_dt = datetime.strptime(target_date.strip(), "%Y-%m-%d")
        ref_dt = datetime.strptime(as_of_date.strip(), "%Y-%m-%d")
        return (t_dt - ref_dt).days
    except Exception:
        return None


class EffectiveStateEngine:
    """
    Evaluates historical and current regulatory effective states across
    documents, versions, requirements, obligations, and checklists.
    """

    def __init__(self, timeline_service: Optional[TimelineService] = None):
        self.timeline_service = timeline_service or TimelineService()

    def get_regulatory_state(
        self,
        doc_data: Dict[str, Any],
        as_of_date: Optional[str] = None,
        date_events: Optional[List[RegulatoryDateEvent]] = None
    ) -> TemporalStateEvaluation:
        """
        Evaluates the regulatory state of a document as of a specific date (64.8, 64.9).
        Incorporates publication, effective, expiry, and supersession timeline relationships.
        """
        ref_date = as_of_date or datetime.utcnow().strftime("%Y-%m-%d")
        doc_id = doc_data.get("document_id") or doc_data.get("id") or "UNKNOWN_DOC"
        version_id = doc_data.get("version_id") or doc_data.get("version") or "1.0"
        meta = doc_data.get("metadata", {}) if isinstance(doc_data.get("metadata"), dict) else {}

        # 1. Resolve key regulatory dates from doc_data or date_events
        pub_date = doc_data.get("published_date") or meta.get("published_date")
        eff_date = doc_data.get("effective_date") or meta.get("effective_date")
        exp_date = doc_data.get("expiry_date") or meta.get("expiry_date")
        sup_date = doc_data.get("superseded_date") or meta.get("superseded_date")

        derivation_type = "EXPLICIT" if eff_date else "UNKNOWN"

        if date_events:
            for ev in date_events:
                if ev.event_type == "EFFECTIVE" and ev.date and not eff_date:
                    eff_date = ev.date
                    derivation_type = ev.derivation_type
                elif ev.event_type == "EXPIRES" and ev.date and not exp_date:
                    exp_date = ev.date
                elif ev.event_type == "PUBLISHED" and ev.date and not pub_date:
                    pub_date = ev.date

        # Normalize date strings if valid
        pub_date = pub_date.strip() if _is_valid_iso_date(pub_date) else None
        eff_date = eff_date.strip() if _is_valid_iso_date(eff_date) else None
        exp_date = exp_date.strip() if _is_valid_iso_date(exp_date) else None
        sup_date = sup_date.strip() if _is_valid_iso_date(sup_date) else None

        # 2. Check for Date Conflicts & Inconsistencies (64.16, 64.17)
        conflicts = self.detect_date_conflicts(
            document_id=doc_id,
            published_date=pub_date,
            effective_date=eff_date,
            expiry_date=exp_date,
            superseded_date=sup_date,
            date_events=date_events
        )

        # 3. Check explicit statuses (REPEALED, WITHDRAWN, SUPERSEDED)
        raw_status = (doc_data.get("status") or meta.get("status") or "").strip().upper()
        if raw_status in ("REPEALED", "WITHDRAWN"):
            return TemporalStateEvaluation(
                document_id=doc_id,
                document_version_id=version_id,
                as_of_date=ref_date,
                state=raw_status,
                effective_date=eff_date,
                published_date=pub_date,
                expiry_date=exp_date,
                superseded_date=sup_date,
                derivation_type=derivation_type,
                reason=f"Document explicitly marked as {raw_status} in source metadata.",
                conflicts=conflicts,
                provenance={"status_source": "document_metadata"}
            )

        # 4. Check Supersession relative to as_of_date
        is_superseded = bool(doc_data.get("superseded_by") or meta.get("superseded_by") or raw_status == "SUPERSEDED")
        if is_superseded:
            # If superseded_date is known, check if it had happened by as_of_date
            if sup_date and ref_date < sup_date:
                # Not yet superseded on ref_date! Will fall through to effective date check
                pass
            else:
                return TemporalStateEvaluation(
                    document_id=doc_id,
                    document_version_id=version_id,
                    as_of_date=ref_date,
                    state="SUPERSEDED",
                    effective_date=eff_date,
                    published_date=pub_date,
                    expiry_date=exp_date,
                    superseded_date=sup_date,
                    derivation_type=derivation_type,
                    reason=f"Document was superseded on {sup_date or 'an unrecorded date'} (prior to {ref_date}).",
                    conflicts=conflicts,
                    provenance={"superseded_by": doc_data.get("superseded_by") or meta.get("superseded_by")}
                )

        # 5. Check Expiry relative to as_of_date
        if exp_date and ref_date >= exp_date:
            return TemporalStateEvaluation(
                document_id=doc_id,
                document_version_id=version_id,
                as_of_date=ref_date,
                state="EXPIRED",
                effective_date=eff_date,
                published_date=pub_date,
                expiry_date=exp_date,
                superseded_date=sup_date,
                derivation_type=derivation_type,
                reason=f"Document expired on {exp_date} (prior to {ref_date}).",
                conflicts=conflicts,
                provenance={"expiry_date": exp_date}
            )

        # 6. Check Effective Date relative to as_of_date
        if eff_date:
            if ref_date < eff_date:
                days_until = calculate_days_delta(eff_date, ref_date)
                return TemporalStateEvaluation(
                    document_id=doc_id,
                    document_version_id=version_id,
                    as_of_date=ref_date,
                    state="NOT_YET_EFFECTIVE",
                    effective_date=eff_date,
                    published_date=pub_date,
                    expiry_date=exp_date,
                    superseded_date=sup_date,
                    derivation_type=derivation_type,
                    reason=f"Document becomes effective on {eff_date} ({days_until} days after {ref_date}).",
                    conflicts=conflicts,
                    provenance={"effective_date": eff_date, "derivation_type": derivation_type}
                )
            else:
                return TemporalStateEvaluation(
                    document_id=doc_id,
                    document_version_id=version_id,
                    as_of_date=ref_date,
                    state="EFFECTIVE",
                    effective_date=eff_date,
                    published_date=pub_date,
                    expiry_date=exp_date,
                    superseded_date=sup_date,
                    derivation_type=derivation_type,
                    reason=f"Document came into effect on {eff_date} (in force on {ref_date}).",
                    conflicts=conflicts,
                    provenance={"effective_date": eff_date, "derivation_type": derivation_type}
                )

        # 7. No explicit effective date: DO NOT silently convert publication_date into effective_date!
        # If published date exists and in past, mark as UNKNOWN effective date but note published.
        if pub_date:
            return TemporalStateEvaluation(
                document_id=doc_id,
                document_version_id=version_id,
                as_of_date=ref_date,
                state="UNKNOWN",
                effective_date=None,
                published_date=pub_date,
                expiry_date=exp_date,
                superseded_date=sup_date,
                derivation_type="UNKNOWN",
                reason=f"Published on {pub_date}, but effective date is not explicitly stated or determinable.",
                conflicts=conflicts,
                provenance={"published_date": pub_date}
            )

        return TemporalStateEvaluation(
            document_id=doc_id,
            document_version_id=version_id,
            as_of_date=ref_date,
            state="UNKNOWN",
            effective_date=None,
            published_date=None,
            expiry_date=None,
            superseded_date=None,
            derivation_type="UNKNOWN",
            reason="Neither effective date nor publication date could be verified.",
            conflicts=conflicts,
            provenance={}
        )

    def detect_date_conflicts(
        self,
        document_id: str,
        published_date: Optional[str],
        effective_date: Optional[str],
        expiry_date: Optional[str],
        superseded_date: Optional[str],
        date_events: Optional[List[RegulatoryDateEvent]] = None
    ) -> List[DateConflict]:
        """
        Validates temporal consistency (64.16, 64.17):
        - effective_date >= published_date
        - expiry_date >= effective_date
        - superseded_date >= effective_date
        - Conflicting date events of same event_type
        """
        conflicts: List[DateConflict] = []

        # Check cross-version temporal consistency
        if published_date and effective_date:
            if effective_date < published_date:
                conflicts.append(DateConflict(
                    document_id=document_id,
                    event_type="EFFECTIVE_BEFORE_PUBLICATION",
                    conflicting_values=[
                        {"published_date": published_date},
                        {"effective_date": effective_date}
                    ],
                    evidence=f"Effective date ({effective_date}) is chronologically earlier than publication date ({published_date}).",
                    severity="WARNING",
                    notes="Unusual temporal semantics: retroactive application or data anomaly."
                ))

        if effective_date and expiry_date:
            if expiry_date < effective_date:
                conflicts.append(DateConflict(
                    document_id=document_id,
                    event_type="EXPIRY_BEFORE_EFFECTIVE",
                    conflicting_values=[
                        {"effective_date": effective_date},
                        {"expiry_date": expiry_date}
                    ],
                    evidence=f"Expiry date ({expiry_date}) precedes effective date ({effective_date}).",
                    severity="ERROR",
                    notes="Logically contradictory: document cannot expire before coming into force."
                ))

        if effective_date and superseded_date:
            if superseded_date < effective_date:
                conflicts.append(DateConflict(
                    document_id=document_id,
                    event_type="SUPERSEDED_BEFORE_EFFECTIVE",
                    conflicting_values=[
                        {"effective_date": effective_date},
                        {"superseded_date": superseded_date}
                    ],
                    evidence=f"Superseded date ({superseded_date}) precedes effective date ({effective_date}).",
                    severity="WARNING",
                    notes="Regulation superseded or replaced prior to its scheduled effective date."
                ))

        # Check conflicting values among multiple date events of the same type
        if date_events:
            effective_events = [e for e in date_events if e.event_type == "EFFECTIVE" and e.date]
            distinct_eff_dates = {e.date for e in effective_events}
            if len(distinct_eff_dates) > 1:
                conflicts.append(DateConflict(
                    document_id=document_id,
                    event_type="DATE_CONFLICT",
                    conflicting_values=[{"date": e.date, "source_text": e.source_text} for e in effective_events],
                    evidence=f"Multiple conflicting effective dates found: {list(distinct_eff_dates)}",
                    severity="WARNING",
                    notes="Text mentions multiple differing effective dates across sections."
                ))

        return conflicts

    # =========================================================================
    # REQUIREMENT & OBLIGATION TEMPORAL EVALUATION (64.10, 64.11)
    # =========================================================================

    def evaluate_requirement_temporal_state(
        self,
        requirement: RegulatoryRequirement,
        as_of_date: Optional[str] = None,
        document_eval: Optional[TemporalStateEvaluation] = None
    ) -> RequirementTemporalState:
        """
        Evaluates whether a specific requirement is active on as_of_date (64.10).
        """
        ref_date = as_of_date or datetime.utcnow().strftime("%Y-%m-%d")

        # 1. Check parent document state if available
        if document_eval:
            if document_eval.state in ("SUPERSEDED", "REPEALED", "WITHDRAWN", "EXPIRED"):
                return RequirementTemporalState(
                    requirement_id=requirement.requirement_id,
                    document_id=requirement.document_id,
                    as_of_date=ref_date,
                    is_active=False,
                    state=document_eval.state,
                    effective_date=document_eval.effective_date,
                    superseded_date=document_eval.superseded_date,
                    reason=f"Parent document is {document_eval.state} on {ref_date}."
                )
            if document_eval.state == "NOT_YET_EFFECTIVE":
                return RequirementTemporalState(
                    requirement_id=requirement.requirement_id,
                    document_id=requirement.document_id,
                    as_of_date=ref_date,
                    is_active=False,
                    state="NOT_YET_EFFECTIVE",
                    effective_date=document_eval.effective_date,
                    reason=f"Parent document is not yet effective on {ref_date} (effective {document_eval.effective_date})."
                )

        # 2. Check requirement's own effective_date
        req_eff = requirement.effective_date
        if req_eff and _is_valid_iso_date(req_eff):
            if ref_date < req_eff:
                days_until = calculate_days_delta(req_eff, ref_date)
                return RequirementTemporalState(
                    requirement_id=requirement.requirement_id,
                    document_id=requirement.document_id,
                    as_of_date=ref_date,
                    is_active=False,
                    state="NOT_YET_EFFECTIVE",
                    effective_date=req_eff,
                    reason=f"Requirement becomes effective on {req_eff} ({days_until} days after {ref_date})."
                )
            else:
                return RequirementTemporalState(
                    requirement_id=requirement.requirement_id,
                    document_id=requirement.document_id,
                    as_of_date=ref_date,
                    is_active=True,
                    state="ACTIVE",
                    effective_date=req_eff,
                    reason=f"Requirement effective from {req_eff}."
                )

        # Fallback to document state or active if parent is EFFECTIVE
        if document_eval and document_eval.state == "EFFECTIVE":
            return RequirementTemporalState(
                requirement_id=requirement.requirement_id,
                document_id=requirement.document_id,
                as_of_date=ref_date,
                is_active=True,
                state="ACTIVE",
                effective_date=document_eval.effective_date,
                reason="Inherited active effective state from parent document."
            )

        return RequirementTemporalState(
            requirement_id=requirement.requirement_id,
            document_id=requirement.document_id,
            as_of_date=ref_date,
            is_active=False,
            state="UNKNOWN",
            effective_date=None,
            reason="Effective date could not be verified."
        )

    def evaluate_obligation_temporal_state(
        self,
        obligation: RegulatoryObligation,
        as_of_date: Optional[str] = None,
        document_eval: Optional[TemporalStateEvaluation] = None
    ) -> ObligationTemporalState:
        """
        Evaluates operational obligation lifecycle state relative to as_of_date (64.11).
        Possible states: FUTURE, ACTIVE, HISTORICAL, SUPERSEDED, EXPIRED, UNKNOWN.
        """
        ref_date = as_of_date or datetime.utcnow().strftime("%Y-%m-%d")

        # 1. Document-level status check
        if document_eval:
            if document_eval.state in ("SUPERSEDED", "REPEALED", "WITHDRAWN"):
                return ObligationTemporalState(
                    obligation_id=obligation.obligation_id,
                    requirement_id=obligation.requirement_id,
                    document_id=obligation.document_id,
                    as_of_date=ref_date,
                    status="SUPERSEDED" if document_eval.state == "SUPERSEDED" else "HISTORICAL",
                    effective_date=document_eval.effective_date,
                    days_until_effective=None,
                    reason=f"Parent document is {document_eval.state} as of {ref_date}."
                )
            if document_eval.state == "EXPIRED":
                return ObligationTemporalState(
                    obligation_id=obligation.obligation_id,
                    requirement_id=obligation.requirement_id,
                    document_id=obligation.document_id,
                    as_of_date=ref_date,
                    status="EXPIRED",
                    effective_date=document_eval.effective_date,
                    days_until_effective=None,
                    reason=f"Parent document expired on {document_eval.expiry_date}."
                )
            if document_eval.state == "NOT_YET_EFFECTIVE":
                days_until = calculate_days_delta(document_eval.effective_date, ref_date)
                return ObligationTemporalState(
                    obligation_id=obligation.obligation_id,
                    requirement_id=obligation.requirement_id,
                    document_id=obligation.document_id,
                    as_of_date=ref_date,
                    status="FUTURE",
                    effective_date=document_eval.effective_date,
                    days_until_effective=days_until,
                    reason=f"Obligation becomes effective in the future on {document_eval.effective_date}."
                )

        # 2. Check obligation's own effective_date
        ob_eff = obligation.effective_date
        if ob_eff and _is_valid_iso_date(ob_eff):
            if ref_date < ob_eff:
                days_until = calculate_days_delta(ob_eff, ref_date)
                return ObligationTemporalState(
                    obligation_id=obligation.obligation_id,
                    requirement_id=obligation.requirement_id,
                    document_id=obligation.document_id,
                    as_of_date=ref_date,
                    status="FUTURE",
                    effective_date=ob_eff,
                    days_until_effective=days_until,
                    reason=f"Obligation becomes effective on {ob_eff} ({days_until} days remaining)."
                )
            else:
                return ObligationTemporalState(
                    obligation_id=obligation.obligation_id,
                    requirement_id=obligation.requirement_id,
                    document_id=obligation.document_id,
                    as_of_date=ref_date,
                    status="ACTIVE",
                    effective_date=ob_eff,
                    days_until_effective=0,
                    reason=f"Obligation active since {ob_eff}."
                )

        # 3. If parent document is EFFECTIVE
        if document_eval and document_eval.state == "EFFECTIVE":
            return ObligationTemporalState(
                obligation_id=obligation.obligation_id,
                requirement_id=obligation.requirement_id,
                document_id=obligation.document_id,
                as_of_date=ref_date,
                status="ACTIVE",
                effective_date=document_eval.effective_date,
                days_until_effective=0,
                reason="Active under in-force parent regulation."
            )

        return ObligationTemporalState(
            obligation_id=obligation.obligation_id,
            requirement_id=obligation.requirement_id,
            document_id=obligation.document_id,
            as_of_date=ref_date,
            status="UNKNOWN",
            effective_date=None,
            days_until_effective=None,
            reason="Obligation temporal status is unverified."
        )

    # =========================================================================
    # CHECKLIST TEMPORAL EVALUATION (64.12)
    # =========================================================================

    def evaluate_checklist_item_temporal_state(
        self,
        item: ChecklistItem,
        as_of_date: Optional[str] = None,
        obligation_state: Optional[ObligationTemporalState] = None
    ) -> ChecklistItemTemporalState:
        """
        Evaluates temporal applicability for an individual compliance checklist item (64.12).
        Distinguishes ACTIVE, UPCOMING, HISTORICAL, NOT_YET_APPLICABLE, SUPERSEDED, UNKNOWN.
        """
        ref_date = as_of_date or datetime.utcnow().strftime("%Y-%m-%d")

        if obligation_state:
            if obligation_state.status == "ACTIVE":
                return ChecklistItemTemporalState(
                    item_id=item.item_id,
                    obligation_id=item.obligation_id,
                    as_of_date=ref_date,
                    temporal_status="ACTIVE",
                    effective_date=obligation_state.effective_date,
                    days_until_effective=0,
                    is_actionable_now=True
                )
            elif obligation_state.status == "FUTURE":
                return ChecklistItemTemporalState(
                    item_id=item.item_id,
                    obligation_id=item.obligation_id,
                    as_of_date=ref_date,
                    temporal_status="UPCOMING",
                    effective_date=obligation_state.effective_date,
                    days_until_effective=obligation_state.days_until_effective,
                    is_actionable_now=False
                )
            elif obligation_state.status in ("SUPERSEDED", "HISTORICAL"):
                return ChecklistItemTemporalState(
                    item_id=item.item_id,
                    obligation_id=item.obligation_id,
                    as_of_date=ref_date,
                    temporal_status=obligation_state.status,
                    effective_date=obligation_state.effective_date,
                    days_until_effective=None,
                    is_actionable_now=False
                )

        return ChecklistItemTemporalState(
            item_id=item.item_id,
            obligation_id=item.obligation_id,
            as_of_date=ref_date,
            temporal_status="UNKNOWN",
            effective_date=None,
            days_until_effective=None,
            is_actionable_now=False
        )


_global_state_engine = EffectiveStateEngine()


def get_effective_state_engine() -> EffectiveStateEngine:
    """Returns singleton instance of EffectiveStateEngine."""
    return _global_state_engine
