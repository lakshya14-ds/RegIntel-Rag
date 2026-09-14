"""
Unit tests for Evidence-Based Document Status Determination (Phase 58.7).
"""

import pytest
from datetime import datetime, timedelta
from app.versioning.timeline import determine_document_status


def test_status_explicit_superseded():
    """Explicitly superseded document must be marked SUPERSEDED."""
    doc = {
        "document_id": "doc_old",
        "title": "Old Circular",
        "published_date": "2020-01-01",
        "effective_date": "2020-02-01",
        "status": "historical"
    }
    status = determine_document_status(doc, is_superseded=True)
    assert status == "SUPERSEDED"


def test_status_superseded_by_metadata():
    """Document with superseded_by in metadata is SUPERSEDED."""
    doc = {
        "document_id": "doc_old",
        "title": "Old Circular",
        "published_date": "2020-01-01",
        "metadata": {"superseded_by": "doc_new"}
    }
    status = determine_document_status(doc, is_superseded=False)
    assert status == "SUPERSEDED"


def test_status_future_effective_date():
    """Document with an effective date in the future must be NOT_YET_EFFECTIVE."""
    future_date = (datetime.utcnow() + timedelta(days=60)).strftime("%Y-%m-%d")
    doc = {
        "document_id": "doc_future",
        "title": "Future Regulation",
        "published_date": "2026-01-01",
        "effective_date": future_date,
        "status": "current"
    }
    status = determine_document_status(doc, is_superseded=False)
    assert status == "NOT_YET_EFFECTIVE"


def test_status_not_assumed_current_simply_because_newest():
    """System must NOT assume newest document is automatically CURRENT without evidence."""
    doc = {
        "document_id": "doc_recent",
        "title": "Recent Unverified Notice",
        "published_date": "2026-03-01",
        "effective_date": "2026-03-01",
        "status": "unknown"
    }
    status = determine_document_status(doc, is_superseded=False)
    assert status == "UNKNOWN"


def test_status_master_circular_active():
    """Consolidated master circular not superseded is treated as CURRENT."""
    doc = {
        "document_id": "doc_master",
        "title": "Master Circular for Investment Advisers",
        "document_type": "Master Circular",
        "published_date": "2024-05-15",
        "effective_date": "2024-05-15",
        "status": "current"
    }
    status = determine_document_status(doc, is_superseded=False)
    assert status == "CURRENT"


def test_status_empty_or_no_evidence():
    """Empty doc or doc with missing metadata yields UNKNOWN."""
    assert determine_document_status({}) == "UNKNOWN"
    assert determine_document_status({"document_id": "x"}) == "UNKNOWN"
