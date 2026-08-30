"""
Unit Tests for Predecessor Detection and Confidence Scoring (Phase 47).
"""

import pytest
from unittest.mock import MagicMock
from app.ingestion.version_tracker import VersionTracker


def test_predecessor_detection_exact_circular_number():
    tracker = VersionTracker()

    target_doc = {
        "document_id": "target_doc",
        "title": "Master Circular for Depositories 2024",
        "category": "Depositories",
        "source": "SEBI",
        "published_date": "2024-10-01",
        "content": "This master circular is issued in supersession of circular SEBI/HO/MRD/DP/CIR/P/2021/100."
    }

    predecessor_doc = {
        "document_id": "pred_doc_exact",
        "title": "Circular on Depository Operations 2021",
        "category": "Depositories",
        "source": "SEBI",
        "circular_number": "SEBI/HO/MRD/DP/CIR/P/2021/100",
        "published_date": "2021-06-15",
        "content": "Original depository guidelines."
    }

    tracker._get_document = MagicMock(return_value=target_doc)
    tracker._load_all_documents = MagicMock(return_value=[target_doc, predecessor_doc])

    candidates = tracker.find_predecessor_candidates("target_doc")
    assert len(candidates) >= 1
    assert candidates[0]["document_id"] == "pred_doc_exact"


def test_predecessor_detection_weak_similarity_and_confidence():
    tracker = VersionTracker()

    target_doc = {
        "document_id": "target_weak",
        "title": "Advisory on Cybersecurity Practices",
        "category": "Cybersecurity",
        "source": "SEBI",
        "published_date": "2024-03-01",
        "content": "Cybersecurity advisory notice."
    }

    unrelated_doc = {
        "document_id": "unrelated_1",
        "title": "Mutual Fund Scheme Categorization",
        "category": "Mutual Funds",
        "source": "SEBI",
        "published_date": "2020-01-01",
        "content": "MF categorisation rules."
    }

    tracker._get_document = MagicMock(return_value=target_doc)
    tracker._load_all_documents = MagicMock(return_value=[target_doc, unrelated_doc])

    candidates = tracker.find_predecessor_candidates("target_weak")
    # Should not invent relationships for unrelated categories
    assert len(candidates) == 0

    rel_info = tracker.resolve_document_relationships("target_weak")
    assert rel_info["relationship_type"] == "NEW"
    assert rel_info["relationship_confidence"] == "low"
