"""
Unit Tests for Timeline Service (Phase 47).
"""

import pytest
from unittest.mock import MagicMock
from app.versioning.timeline import get_document_timeline
from app.ingestion.version_tracker import VersionTracker


def test_get_document_timeline_structure():
    tracker = VersionTracker()

    doc_a = {
        "document_id": "doc_baseline",
        "title": "Baseline Circular 2018",
        "published_date": "2018-05-10",
        "status": "historical",
        "content": "Base rules."
    }
    doc_b = {
        "document_id": "doc_current",
        "title": "Revised Circular 2024",
        "published_date": "2024-05-15",
        "status": "current",
        "content": "This circular supersedes circular doc_baseline."
    }

    tracker._get_document = MagicMock(side_effect=lambda did: doc_a if did == "doc_baseline" else (doc_b if did == "doc_current" else None))
    tracker._load_all_documents = MagicMock(return_value=[doc_a, doc_b])

    timeline_data = get_document_timeline("doc_current", tracker=tracker)

    assert timeline_data["document_id"] == "doc_current"
    events = timeline_data["events"]
    assert len(events) == 2
    # Events should be chronologically ordered
    assert events[0]["document_id"] == "doc_baseline"
    assert events[1]["document_id"] == "doc_current"
    assert events[1]["relationship"] == "TARGET"
