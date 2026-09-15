"""
Regulatory Deadline Extraction & Recurrence Intelligence Engine (Phase 65.2, 65.3, 65.4).

Provides:
- Extraction of absolute, relative, and recurring compliance deadlines from requirements and obligations.
- Bounded recurrence generation (monthly, quarterly, half-yearly, annually) for planning windows.
- Calculation of due dates, days remaining, and deadline status (UPCOMING, DUE_SOON, DUE_TODAY, OVERDUE).
- Explicit vs Calculated due date provenance tracking.
"""

import re
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from app.compliance.alert_models import (
    RegulatoryDeadline,
    DeadlineType,
    DeadlineStatus,
)
from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
)
from app.compliance.date_extractor import parse_calendar_date

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# =============================================================================
# DEADLINE PATTERN REGEXES (65.2)
# =============================================================================

RELATIVE_DAYS_REGEX = re.compile(
    r"\bwithin\s+(\d+)\s+days\b(?:\s+(?:from|of)\s+(?:the\s+)?([A-Za-z0-9\s]+))?",
    re.IGNORECASE
)

ABSOLUTE_BY_DATE_REGEX = re.compile(
    r"\bby\s+([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4}|[A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4})\b",
    re.IGNORECASE
)

FREQUENCY_REGEX = re.compile(
    r"\b(monthly|quarterly|half-yearly|half\s+yearly|semi-annually|annually|annual|yearly)\b",
    re.IGNORECASE
)


class DeadlineIntelligenceEngine:
    """
    Extracts and evaluates compliance deadlines for regulatory obligations.
    """

    def __init__(self):
        pass

    def extract_deadlines_from_obligation(
        self,
        obligation: RegulatoryObligation,
        as_of_date: Optional[str] = None,
        planning_window_days: int = 180
    ) -> List[RegulatoryDeadline]:
        """
        Extracts deadlines from an obligation's text, deadline expression, and frequency.
        Generates bounded recurring occurrences when recurring patterns exist (65.4).
        """
        ref_str = as_of_date or datetime.utcnow().strftime("%Y-%m-%d")
        ref_dt = datetime.strptime(ref_str, "%Y-%m-%d")
        deadlines: List[RegulatoryDeadline] = []

        raw_deadline = (obligation.deadline or "").strip()
        raw_freq = (obligation.frequency or "").strip().upper()
        source_ev = obligation.source_evidence or raw_deadline or "Extracted obligation"

        # 1. Check for Absolute Date Deadline ("by 30 June 2026")
        abs_match = ABSOLUTE_BY_DATE_REGEX.search(raw_deadline or source_ev)
        if abs_match:
            date_str = parse_calendar_date(abs_match.group(1))
            if date_str:
                days_rem = (datetime.strptime(date_str, "%Y-%m-%d") - ref_dt).days
                status_val = self._compute_status(days_rem)
                deadlines.append(RegulatoryDeadline(
                    deadline_id=f"ddl_{uuid.uuid4().hex[:12]}",
                    obligation_id=obligation.obligation_id,
                    requirement_id=obligation.requirement_id,
                    document_id=obligation.document_id,
                    deadline_type="ABSOLUTE",
                    deadline_expression=abs_match.group(0),
                    due_date=date_str,
                    due_date_derivation="EXPLICIT",
                    frequency=raw_freq or None,
                    source_evidence=source_ev,
                    confidence="HIGH",
                    status=status_val,
                    days_remaining=days_rem
                ))
                return deadlines

        # 2. Check for Relative Days ("within 15 days")
        rel_match = RELATIVE_DAYS_REGEX.search(raw_deadline or source_ev)
        offset_days = int(rel_match.group(1)) if rel_match else None
        trigger_expr = rel_match.group(2).strip() if (rel_match and rel_match.group(2)) else None

        # 3. Check for Frequency / Recurring Deadlines (65.4)
        freq_norm = self._normalize_frequency(raw_freq or source_ev)

        if freq_norm:
            # Generate bounded occurrences for the planning window
            recurring_ddls = self._generate_recurring_occurrences(
                obligation=obligation,
                frequency=freq_norm,
                offset_days=offset_days or 15,
                ref_dt=ref_dt,
                window_days=planning_window_days,
                source_evidence=source_ev
            )
            deadlines.extend(recurring_ddls)
            return deadlines

        # 4. Single relative deadline relative to effective date or trigger
        if offset_days:
            base_date = obligation.effective_date
            due_date = None
            days_rem = None
            if base_date:
                try:
                    b_dt = datetime.strptime(base_date, "%Y-%m-%d")
                    d_dt = b_dt + timedelta(days=offset_days)
                    due_date = d_dt.strftime("%Y-%m-%d")
                    days_rem = (d_dt - ref_dt).days
                except Exception:
                    pass

            deadlines.append(RegulatoryDeadline(
                deadline_id=f"ddl_{uuid.uuid4().hex[:12]}",
                obligation_id=obligation.obligation_id,
                requirement_id=obligation.requirement_id,
                document_id=obligation.document_id,
                deadline_type="RELATIVE",
                trigger_event=trigger_expr or "occurrence of regulatory trigger",
                deadline_expression=f"within {offset_days} days",
                due_date=due_date,
                due_date_derivation="CALCULATED" if due_date else "UNKNOWN",
                frequency=None,
                source_evidence=source_ev,
                confidence="HIGH" if due_date else "MEDIUM",
                status=self._compute_status(days_rem) if days_rem is not None else "UPCOMING",
                days_remaining=days_rem
            ))
            return deadlines

        # Fallback if raw_deadline exists
        if raw_deadline:
            deadlines.append(RegulatoryDeadline(
                deadline_id=f"ddl_{uuid.uuid4().hex[:12]}",
                obligation_id=obligation.obligation_id,
                requirement_id=obligation.requirement_id,
                document_id=obligation.document_id,
                deadline_type="UNKNOWN",
                deadline_expression=raw_deadline,
                due_date=None,
                due_date_derivation="UNKNOWN",
                source_evidence=source_ev,
                confidence="MEDIUM",
                status="UPCOMING",
                days_remaining=None
            ))

        return deadlines

    def _normalize_frequency(self, text: str) -> Optional[str]:
        if not text:
            return None
        upper = text.upper()
        if "QUARTER" in upper:
            return "QUARTERLY"
        if "MONTH" in upper:
            return "MONTHLY"
        if "HALF" in upper or "SEMI" in upper:
            return "HALF_YEARLY"
        if "ANNUAL" in upper or "YEAR" in upper:
            return "ANNUALLY"
        return None

    def _generate_recurring_occurrences(
        self,
        obligation: RegulatoryObligation,
        frequency: str,
        offset_days: int,
        ref_dt: datetime,
        window_days: int,
        source_evidence: str
    ) -> List[RegulatoryDeadline]:
        """
        Generates recurring deadlines bounded by window_days.
        Anchored to standard quarters (March 31, June 30, September 30, December 31).
        """
        occurrences: List[RegulatoryDeadline] = []
        end_window_dt = ref_dt + timedelta(days=window_days)
        year = ref_dt.year

        # Generate anchor period ends for current and next year
        period_ends: List[Tuple[str, datetime]] = []

        if frequency == "QUARTERLY":
            for y in [year - 1, year, year + 1]:
                period_ends.append((f"Q4 FY {y}", datetime(y, 3, 31)))
                period_ends.append((f"Q1 FY {y+1}", datetime(y, 6, 30)))
                period_ends.append((f"Q2 FY {y+1}", datetime(y, 9, 30)))
                period_ends.append((f"Q3 FY {y+1}", datetime(y, 12, 31)))
        elif frequency == "ANNUALLY":
            for y in [year - 1, year, year + 1]:
                period_ends.append((f"FY {y}", datetime(y, 3, 31)))
        elif frequency == "HALF_YEARLY":
            for y in [year - 1, year, year + 1]:
                period_ends.append((f"H1 FY {y}", datetime(y, 9, 30)))
                period_ends.append((f"H2 FY {y}", datetime(y, 3, 31)))
        elif frequency == "MONTHLY":
            for month_offset in range(-1, 12):
                target_m = ((ref_dt.month - 1 + month_offset) % 12) + 1
                target_y = ref_dt.year + ((ref_dt.month - 1 + month_offset) // 12)
                # Last day of target month
                next_m = target_m + 1 if target_m < 12 else 1
                next_y = target_y if target_m < 12 else target_y + 1
                last_day = datetime(next_y, next_m, 1) - timedelta(days=1)
                period_ends.append((f"{last_day.strftime('%B %Y')}", last_day))

        for period_label, period_end_dt in period_ends:
            due_dt = period_end_dt + timedelta(days=offset_days)
            # Only keep occurrences within planning window: [ref_dt - 15 days, end_window_dt]
            if (ref_dt - timedelta(days=15)) <= due_dt <= end_window_dt:
                days_rem = (due_dt - ref_dt).days
                status_val = self._compute_status(days_rem)
                occurrences.append(RegulatoryDeadline(
                    deadline_id=f"ddl_rec_{uuid.uuid4().hex[:10]}",
                    obligation_id=obligation.obligation_id,
                    requirement_id=obligation.requirement_id,
                    document_id=obligation.document_id,
                    deadline_type="RECURRING",
                    trigger_event=f"End of {period_label}",
                    deadline_expression=f"{frequency.lower().capitalize()} within {offset_days} days of period end",
                    due_date=due_dt.strftime("%Y-%m-%d"),
                    due_date_derivation="CALCULATED",
                    frequency=frequency,
                    source_evidence=source_evidence,
                    confidence="HIGH",
                    status=status_val,
                    days_remaining=days_rem,
                    recurrence_rule={
                        "frequency": frequency,
                        "offset_days": offset_days,
                        "period": period_label
                    }
                ))

        occurrences.sort(key=lambda x: x.due_date or "9999-99-99")
        return occurrences

    def _compute_status(self, days_remaining: Optional[int]) -> DeadlineStatus:
        if days_remaining is None:
            return "UNKNOWN"
        if days_remaining < 0:
            return "OVERDUE"
        if days_remaining == 0:
            return "DUE_TODAY"
        if days_remaining <= 7:
            return "DUE_SOON"
        return "UPCOMING"


_global_deadline_engine = DeadlineIntelligenceEngine()


def get_deadline_engine() -> DeadlineIntelligenceEngine:
    return _global_deadline_engine


def generate_deadlines_from_obligation(
    obligation: RegulatoryObligation,
    date_events: Optional[List[Any]] = None,
    publication_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    planning_window_days: int = 180
) -> List[RegulatoryDeadline]:
    """Convenience wrapper around get_deadline_engine().extract_deadlines_from_obligation."""
    return _global_deadline_engine.extract_deadlines_from_obligation(
        obligation=obligation,
        as_of_date=as_of_date,
        planning_window_days=planning_window_days
    )

