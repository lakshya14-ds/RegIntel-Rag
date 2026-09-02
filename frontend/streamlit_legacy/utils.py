"""
Frontend Utility Helpers and Safe Streamlit Caching for RegIntel.
"""

import re
from typing import Optional, Dict, Any, List
import streamlit as st

def format_date(date_str: Optional[str]) -> str:
    """Formats ISO/string dates for clean human display."""
    if not date_str or date_str in ("N/A", "None", "1970-01-01", "9999-99-99"):
        return "N/A"
    return str(date_str).split("T")[0]


def get_status_badge(status: Optional[str]) -> str:
    """Returns HTML badge for document status (Current, Historical, Unknown)."""
    st_clean = (status or "unknown").lower()
    if st_clean == "current":
        return '<span class="badge badge-green">🟢 CURRENT</span>'
    elif st_clean == "historical":
        return '<span class="badge badge-amber">📜 HISTORICAL</span>'
    return '<span class="badge badge-gray">⚪ UNKNOWN</span>'


def get_confidence_badge(confidence: Optional[str]) -> str:
    """Returns HTML badge for relationship confidence."""
    conf_clean = (confidence or "unknown").upper()
    if conf_clean == "HIGH":
        return '<span class="badge badge-green">Confidence: HIGH</span>'
    elif conf_clean == "MEDIUM":
        return '<span class="badge badge-amber">Confidence: MEDIUM</span>'
    elif conf_clean == "LOW":
        return '<span class="badge badge-red">Confidence: LOW</span>'
    return '<span class="badge badge-gray">Confidence: UNKNOWN</span>'


def get_change_type_badge(change_type: str) -> str:
    """Returns HTML badge for change type (ADDED, REMOVED, MODIFIED, UNCHANGED)."""
    ctype = change_type.upper()
    badge_map = {
        "ADDED": "badge-green",
        "REMOVED": "badge-red",
        "MODIFIED": "badge-amber",
        "UNCHANGED": "badge-gray"
    }
    cls_name = badge_map.get(ctype, "badge-blue")
    return f'<span class="badge {cls_name}">{ctype}</span>'
