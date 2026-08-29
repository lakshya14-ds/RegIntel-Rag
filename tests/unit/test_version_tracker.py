"""
Unit Tests for Regulatory Version Tracker (Phase 31).
"""

import pytest
from unittest.mock import MagicMock

from app.ingestion.version_tracker import VersionTracker


def test_detect_explicit_supersession():
    tracker = VersionTracker()

    text1 = "This circular is issued in supersession of circular SEBI/HO/MIRSD/DOS3/CIR/P/2018/115 dated July 13, 2018."
    ref1 = tracker.detect_explicit_supersession(text1)
    assert ref1 is not None
    assert "SEBI/HO/MIRSD/DOS3/CIR/P/2018/115" in ref1

    text2 = "The provisions of this circular shall replace circular no. CIR/MIRSD/01/2014 with immediate effect."
    ref2 = tracker.detect_explicit_supersession(text2)
    assert ref2 is not None
    assert "CIR/MIRSD/01/2014" in ref2

    text3 = "General guidelines for stock brokers and trading members."
    assert tracker.detect_explicit_supersession(text3) is None


def test_resolve_relationships_explicit():
    tracker = VersionTracker()

    mock_doc = {
        "document_id": "doc_current_01",
        "title": "Master Circular for Investment Advisers 2024",
        "category": "Investment Adviser",
        "source": "SEBI",
        "published_date": "2024-05-15",
        "content": "This circular supersedes circular SEBI/HO/MIRSD/DOS3/CIR/P/2018/115.",
        "status": "current",
        "metadata": {
            "document_version": "2.0"
        }
    }

    tracker._get_document = MagicMock(return_value=mock_doc)
    tracker._load_all_documents = MagicMock(return_value=[
        mock_doc,
        {
            "document_id": "doc_old_01",
            "title": "Master Circular for Investment Advisers 2018",
            "category": "Investment Adviser",
            "source": "SEBI",
            "circular_number": "SEBI/HO/MIRSD/DOS3/CIR/P/2018/115",
            "published_date": "2018-07-13",
            "content": "Old circular text"
        }
    ])

    info = tracker.resolve_document_relationships("doc_current_01")
    assert info["relationship_type"] == "SUPERSEDES"
    assert info["relationship_confidence"] == "high"
    assert info["predecessor_id"] == "doc_old_01"


def test_resolve_relationships_unknown_document():
    tracker = VersionTracker()
    tracker._get_document = MagicMock(return_value=None)

    info = tracker.resolve_document_relationships("nonexistent_id")
    assert info["status"] == "unknown"
    assert info["relationship_type"] == "UNKNOWN"
    assert info["relationship_confidence"] == "low"
    assert info["predecessor_id"] is None
