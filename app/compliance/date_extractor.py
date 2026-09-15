"""
Regulatory Date & Temporal Extraction Engine (Phase 64).

Provides:
- 64.1 & 64.2: Semantic date extraction into RegulatoryDateEvent.
- 64.3: Deterministic date extraction first (regex, calendar, relative patterns).
- 64.4: LLM temporal classification fallback (Gemini / Ollama via get_llm_provider).
- 64.5: Relative-date resolution (e.g., 30 days from publication -> derived date).
- 64.6 & 64.7: Explicit vs Derived vs Inferred date provenance tracking.
"""

import re
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field

from app.compliance.temporal_models import (
    RegulatoryDateEvent,
    RegulatoryDateType,
    DatePrecision,
    TemporalDerivationType,
    TemporalConfidence,
    ExtractionMethod,
)
from app.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# =============================================================================
# CALENDAR PARSER & NORMALIZATION UTILITIES
# =============================================================================

MONTHS_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12
}

CALENDAR_DATE_REGEXES = [
    # 01 April 2027, 1st April 2027, 1 April, 2027
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})\b", re.IGNORECASE),
    # April 01, 2027, April 1 2027
    re.compile(r"\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.IGNORECASE),
    # 2027-04-01
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    # 01/04/2027 or 01-04-2027 (DD-MM-YYYY Indian/UK regulatory format)
    re.compile(r"\b(\d{2})[\/\-](\d{2})[\/\-](\d{4})\b"),
]


def parse_calendar_date(text: str) -> Optional[str]:
    """Parses and normalizes a calendar date string to ISO YYYY-MM-DD."""
    if not text:
        return None
    cleaned = text.strip()

    # Try ISO YYYY-MM-DD
    m_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", cleaned)
    if m_iso:
        try:
            y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
            dt = datetime(y, m, d)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Try DD Month YYYY
    m_dmy = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})\b", cleaned, re.IGNORECASE)
    if m_dmy:
        day_str, month_str, year_str = m_dmy.group(1), m_dmy.group(2).lower(), m_dmy.group(3)
        if month_str in MONTHS_MAP:
            try:
                dt = datetime(int(year_str), MONTHS_MAP[month_str], int(day_str))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Try Month DD, YYYY
    m_mdy = re.search(r"\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", cleaned, re.IGNORECASE)
    if m_mdy:
        month_str, day_str, year_str = m_mdy.group(1).lower(), m_mdy.group(2), m_mdy.group(3)
        if month_str in MONTHS_MAP:
            try:
                dt = datetime(int(year_str), MONTHS_MAP[month_str], int(day_str))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Try DD/MM/YYYY or DD-MM-YYYY
    m_slash = re.search(r"\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})\b", cleaned)
    if m_slash:
        d_str, m_str, y_str = m_slash.group(1), m_slash.group(2), m_slash.group(3)
        try:
            dt = datetime(int(y_str), int(m_str), int(d_str))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


# =============================================================================
# DETERMINISTIC DATE PATTERN REGEXES (64.3)
# =============================================================================

# Explicit effective date phrases with specific date attached (ordered from most specific to generic)
EXPLICIT_EFFECTIVE_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?:shall\s+come\s+into\s+(?:force|effect)\s+(?:on|from|with\s+effect\s+from))\s+([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4}|[A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4})", re.IGNORECASE),
    re.compile(r"(?:applicable\s+(?:with\s+effect\s+from|from|on))\s+([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4}|[A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4})", re.IGNORECASE),
    re.compile(r"(?:with\s+effect\s+from|effective\s+from|w\.e\.f\.?|on\s+and\s+from|from)\s+([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4}|[A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4})", re.IGNORECASE),
]

# Immediate effect phrases
IMMEDIATE_EFFECT_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(?:with\s+immediate\s+effect|effective\s+immediately|shall\s+come\s+into\s+force\s+at\s+once|shall\s+come\s+into\s+effect\s+at\s+once)\b", re.IGNORECASE),
    re.compile(r"\bcomes\s+into\s+force\s+immediately\b", re.IGNORECASE),
]

# Relative effective date phrases based on publication / notification
RELATIVE_EFFECTIVE_PATTERNS: List[re.Pattern] = [
    re.compile(r"within\s+(\d+)\s+days\s+(?:from|of)\s+(?:the\s+date\s+of\s+)?(?:publication|notification|issue|issuance)", re.IGNORECASE),
    re.compile(r"(?:from|on)\s+the\s+date\s+of\s+(?:its\s+)?(?:publication|notification|issue|issuance)", re.IGNORECASE),
    re.compile(r"after\s+(\d+)\s+days\s+(?:from|of)\s+(?:the\s+date\s+of\s+)?(?:publication|notification|issue|issuance)", re.IGNORECASE),
    re.compile(r"within\s+(\d+)\s+months\s+(?:from|of)\s+(?:the\s+date\s+of\s+)?(?:publication|notification|issue|issuance)", re.IGNORECASE),
]

# Expiry / sunset patterns
EXPIRY_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?:shall\s+remain\s+in\s+force\s+until|valid\s+up\s+to|expires\s+on|sunset\s+date\s+is)\s+([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4}|[A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4})", re.IGNORECASE),
    re.compile(r"(?:applicable\s+until|valid\s+until)\s+([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4}|[A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4})", re.IGNORECASE),
]

# Publication / notification date patterns
PUBLICATION_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?:dated|date\s+of\s+issue|notified\s+on|issued\s+on|published\s+on)\s*[:\-]?\s*([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4}|[A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4})", re.IGNORECASE),
]


# =============================================================================
# STRUCTURED LLM CLASSIFICATION SCHEMA (64.4)
# =============================================================================

class LLMDateClassification(BaseModel):
    """Structured Pydantic response for LLM temporal interpretation."""
    date_type: RegulatoryDateType = "UNKNOWN"
    normalized_date: Optional[str] = None
    source_text: str = ""
    confidence: TemporalConfidence = "MEDIUM"
    reason: str = ""


# =============================================================================
# REGULATORY DATE EXTRACTOR SERVICE
# =============================================================================

class RegulatoryDateExtractor:
    """
    Deterministic-first regulatory date extractor with relative resolution
    and structured LLM fallback.
    """

    def __init__(self):
        pass

    def extract_dates(
        self,
        text: str,
        document_id: str,
        document_version_id: Optional[str] = "1.0",
        section_id: Optional[str] = None,
        source_locator: Optional[Dict[str, Any]] = None,
        known_publication_date: Optional[str] = None,
        known_notification_date: Optional[str] = None,
        use_llm_fallback: bool = False
    ) -> List[RegulatoryDateEvent]:
        """
        Extracts all identifiable regulatory date events from text:
        1. Deterministic pattern scanning.
        2. Relative date resolution against known publication/notification dates.
        3. LLM fallback for ambiguous clauses when requested.
        """
        if not text or not text.strip():
            return []

        locator = source_locator or {}
        events: List[RegulatoryDateEvent] = []
        found_signatures = set()

        # 1. Check Explicit Effective Date Patterns
        for pattern in EXPLICIT_EFFECTIVE_PATTERNS:
            for match in pattern.finditer(text):
                raw_date = match.group(1)
                normalized = parse_calendar_date(raw_date)
                sig = ("EFFECTIVE", normalized, match.group(0).strip().lower())
                if sig not in found_signatures:
                    found_signatures.add(sig)
                    events.append(RegulatoryDateEvent(
                        event_id=f"rde_{uuid.uuid4().hex[:12]}",
                        document_id=document_id,
                        document_version_id=document_version_id,
                        section_id=section_id,
                        event_type="EFFECTIVE",
                        date=normalized,
                        date_precision="DAY" if normalized else "PERIOD",
                        source_text=match.group(0).strip(),
                        source_locator=locator,
                        confidence="HIGH" if normalized else "MEDIUM",
                        extraction_method="DETERMINISTIC",
                        derivation_type="EXPLICIT",
                        derivation_rule="Explicit textual statement"
                    ))

        # 2. Check Immediate Effect Patterns
        for pattern in IMMEDIATE_EFFECT_PATTERNS:
            for match in pattern.finditer(text):
                sig = ("EFFECTIVE_IMMEDIATE", match.group(0).strip().lower())
                if sig not in found_signatures:
                    found_signatures.add(sig)
                    base_date = known_notification_date or known_publication_date
                    events.append(RegulatoryDateEvent(
                        event_id=f"rde_{uuid.uuid4().hex[:12]}",
                        document_id=document_id,
                        document_version_id=document_version_id,
                        section_id=section_id,
                        event_type="EFFECTIVE",
                        date=base_date,
                        date_precision="DAY" if base_date else "PERIOD",
                        source_text=match.group(0).strip(),
                        source_locator=locator,
                        confidence="HIGH" if base_date else "MEDIUM",
                        extraction_method="DERIVED" if base_date else "DETERMINISTIC",
                        derivation_type="DERIVED",
                        derivation_rule="Immediate effect: set to publication/notification date" if base_date else "Immediate effect (base publication date pending)",
                        base_event_type="PUBLISHED" if known_publication_date else ("NOTIFIED" if known_notification_date else None),
                        offset_days=0
                    ))

        # 3. Check Relative Effective Date Patterns (e.g. within 30 days from publication)
        for pattern in RELATIVE_EFFECTIVE_PATTERNS:
            for match in pattern.finditer(text):
                expr = match.group(0).strip()
                days_match = re.search(r"(\d+)\s+days", expr, re.IGNORECASE)
                months_match = re.search(r"(\d+)\s+months", expr, re.IGNORECASE)
                is_on_date = bool(re.search(r"(?:from|on)\s+the\s+date\s+of", expr, re.IGNORECASE))

                offset_days = 0
                if days_match:
                    offset_days = int(days_match.group(1))
                elif months_match:
                    offset_days = int(months_match.group(1)) * 30  # Standard 30-day month approximation

                base_type = "PUBLISHED" if "publication" in expr.lower() else "NOTIFIED"
                base_date = known_publication_date if base_type == "PUBLISHED" else (known_notification_date or known_publication_date)

                derived_date = None
                if base_date:
                    try:
                        base_dt = datetime.strptime(base_date, "%Y-%m-%d")
                        derived_dt = base_dt + timedelta(days=offset_days)
                        derived_date = derived_dt.strftime("%Y-%m-%d")
                    except Exception as e:
                        logger.warning(f"Error calculating relative date from base {base_date}: {e}")

                sig = ("EFFECTIVE_RELATIVE", offset_days, base_type, expr.lower())
                if sig not in found_signatures:
                    found_signatures.add(sig)
                    rule_desc = f"Relative: {base_type} + {offset_days} days" if offset_days > 0 else f"Relative: on date of {base_type}"
                    events.append(RegulatoryDateEvent(
                        event_id=f"rde_{uuid.uuid4().hex[:12]}",
                        document_id=document_id,
                        document_version_id=document_version_id,
                        section_id=section_id,
                        event_type="EFFECTIVE",
                        date=derived_date,
                        date_precision="DAY" if derived_date else "PERIOD",
                        source_text=expr,
                        source_locator=locator,
                        confidence="HIGH" if derived_date else "MEDIUM",
                        extraction_method="DERIVED",
                        derivation_type="DERIVED",
                        derivation_rule=rule_desc,
                        base_event_type=base_type,
                        offset_days=offset_days
                    ))

        # 4. Check Expiry Patterns
        for pattern in EXPIRY_PATTERNS:
            for match in pattern.finditer(text):
                raw_date = match.group(1)
                normalized = parse_calendar_date(raw_date)
                sig = ("EXPIRES", normalized, match.group(0).strip().lower())
                if sig not in found_signatures:
                    found_signatures.add(sig)
                    events.append(RegulatoryDateEvent(
                        event_id=f"rde_{uuid.uuid4().hex[:12]}",
                        document_id=document_id,
                        document_version_id=document_version_id,
                        section_id=section_id,
                        event_type="EXPIRES",
                        date=normalized,
                        date_precision="DAY" if normalized else "PERIOD",
                        source_text=match.group(0).strip(),
                        source_locator=locator,
                        confidence="HIGH" if normalized else "MEDIUM",
                        extraction_method="DETERMINISTIC",
                        derivation_type="EXPLICIT",
                        derivation_rule="Explicit expiry/sunset statement"
                    ))

        # 5. Check Publication / Issue Date Patterns
        for pattern in PUBLICATION_PATTERNS:
            for match in pattern.finditer(text):
                raw_date = match.group(1)
                normalized = parse_calendar_date(raw_date)
                sig = ("PUBLISHED", normalized, match.group(0).strip().lower())
                if sig not in found_signatures:
                    found_signatures.add(sig)
                    events.append(RegulatoryDateEvent(
                        event_id=f"rde_{uuid.uuid4().hex[:12]}",
                        document_id=document_id,
                        document_version_id=document_version_id,
                        section_id=section_id,
                        event_type="PUBLISHED",
                        date=normalized,
                        date_precision="DAY" if normalized else "PERIOD",
                        source_text=match.group(0).strip(),
                        source_locator=locator,
                        confidence="HIGH" if normalized else "MEDIUM",
                        extraction_method="DETERMINISTIC",
                        derivation_type="EXPLICIT",
                        derivation_rule="Explicit publication/issue statement"
                    ))

        # 6. LLM Fallback (64.4): if requested and no explicit effective date found yet
        has_effective = any(e.event_type == "EFFECTIVE" for e in events)
        if use_llm_fallback and not has_effective:
            llm_events = self._classify_temporal_clauses_llm(
                text=text,
                document_id=document_id,
                document_version_id=document_version_id,
                section_id=section_id,
                locator=locator
            )
            for le in llm_events:
                sig = (le.event_type, le.date, le.source_text.lower())
                if sig not in found_signatures:
                    found_signatures.add(sig)
                    events.append(le)

        return events

    def _classify_temporal_clauses_llm(
        self,
        text: str,
        document_id: str,
        document_version_id: Optional[str],
        section_id: Optional[str],
        locator: Dict[str, Any]
    ) -> List[RegulatoryDateEvent]:
        """
        Uses LLM provider abstraction (Gemini / Ollama) to classify ambiguous temporal clauses.
        """
        # Only invoke if text contains some temporal indicator to avoid unnecessary calls
        if not re.search(r"\b(date|effect|force|commence|effective|valid|expires|timeline)\b", text, re.IGNORECASE):
            return []

        prompt = f"""You are an expert regulatory legal temporal analyst.
Analyze the following regulatory text snippet and classify any temporal or effective date clauses.
Classify each clause into:
- date_type: One of [PUBLISHED, NOTIFIED, ISSUED, EFFECTIVE, COMMENCEMENT, EXPIRES, APPLICABLE_FROM, APPLICABLE_UNTIL, DEADLINE, REFERENCE, UNKNOWN]
- normalized_date: ISO date (YYYY-MM-DD) if determinable, or null
- source_text: The exact verbatim snippet from the text
- confidence: HIGH, MEDIUM, LOW
- reason: Concise explanation

Text:
"{text[:2000]}"

Respond ONLY with a JSON array of objects matching the schema:
[
  {{
    "date_type": "EFFECTIVE",
    "normalized_date": "2026-10-01",
    "source_text": "verbatim text",
    "confidence": "HIGH",
    "reason": "explanation"
  }}
]
If no regulatory dates are present, return an empty array: []"""

        try:
            provider = get_llm_provider()
            response = provider.generate(prompt=prompt, temperature=0.0)
            raw_content = response.content if hasattr(response, "content") else str(response)

            import json
            cleaned = raw_content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            events: List[RegulatoryDateEvent] = []
            if isinstance(parsed, list):
                for item in parsed:
                    dtype = item.get("date_type", "UNKNOWN")
                    norm_date = item.get("normalized_date")
                    if norm_date and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(norm_date)):
                        norm_date = parse_calendar_date(str(norm_date))

                    events.append(RegulatoryDateEvent(
                        event_id=f"rde_llm_{uuid.uuid4().hex[:10]}",
                        document_id=document_id,
                        document_version_id=document_version_id,
                        section_id=section_id,
                        event_type=dtype,
                        date=norm_date,
                        date_precision="DAY" if norm_date else "PERIOD",
                        source_text=item.get("source_text") or text[:100],
                        source_locator=locator,
                        confidence=item.get("confidence", "MEDIUM"),
                        extraction_method="LLM",
                        derivation_type="INFERRED",
                        derivation_rule=f"LLM interpretation: {item.get('reason', '')}"
                    ))
            return events
        except Exception as e:
            logger.warning(f"LLM temporal classification failed or timed out: {e}")
            return []


_global_date_extractor = RegulatoryDateExtractor()


def get_regulatory_date_extractor() -> RegulatoryDateExtractor:
    """Returns singleton instance of RegulatoryDateExtractor."""
    return _global_date_extractor


def extract_regulatory_dates(
    text: str,
    document_id: str,
    document_version_id: Optional[str] = "1.0",
    section_id: Optional[str] = None,
    source_locator: Optional[Dict[str, Any]] = None,
    publication_date: Optional[str] = None,
    notification_date: Optional[str] = None,
    use_llm_fallback: bool = False
) -> List[RegulatoryDateEvent]:
    """Convenience wrapper around get_regulatory_date_extractor().extract_dates."""
    return _global_date_extractor.extract_dates(
        text=text,
        document_id=document_id,
        document_version_id=document_version_id,
        section_id=section_id,
        source_locator=source_locator,
        known_publication_date=publication_date,
        known_notification_date=notification_date,
        use_llm_fallback=use_llm_fallback
    )

