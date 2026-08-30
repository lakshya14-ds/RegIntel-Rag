"""
Unit Tests for Regulatory Version Tracker (Phase 47).
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


def test_resolve_relationships_candidate_predecessor():
    tracker = VersionTracker()

    mock_doc = {
        "document_id": "doc_current_02",
        "title": "Operating Guidelines for Investment Advisers in IFSC",
        "category": "Investment Adviser",
        "source": "SEBI",
        "published_date": "2024-01-10",
        "content": "Standard guidelines without explicit supersession statement.",
        "status": "current"
    }

    tracker._get_document = MagicMock(return_value=mock_doc)
    tracker._load_all_documents = MagicMock(return_value=[
        mock_doc,
        {
            "document_id": "doc_old_02",
            "title": "Operating Guidelines for Investment Advisers in IFSC 2020",
            "category": "Investment Adviser",
            "source": "SEBI",
            "published_date": "2020-09-28",
            "content": "Earlier IFSC guidelines"
        },
        {
            "document_id": "doc_unrelated",
            "title": "Mutual Fund Valuation Norms",
            "category": "Mutual Funds",
            "source": "SEBI",
            "published_date": "2021-03-01",
            "content": "Mutual fund rules"
        }
    ])

    info = tracker.resolve_document_relationships("doc_current_02")
    assert info["relationship_type"] == "UPDATE"
    assert info["relationship_confidence"] == "medium"
    assert info["predecessor_id"] == "doc_old_02"


def test_version_chain_and_timeline():
    tracker = VersionTracker()

    doc_a = {
        "document_id": "doc_a",
        "title": "Circular 2018",
        "published_date": "2018-01-01",
        "status": "historical",
        "content": "Base rules."
    }
    doc_b = {
        "document_id": "doc_b",
        "title": "Circular 2021",
        "published_date": "2021-01-01",
        "status": "historical",
        "content": "This circular supersedes circular doc_a."
    }
    doc_c = {
        "document_id": "doc_c",
        "title": "Circular 2024",
        "published_date": "2024-01-01",
        "status": "current",
        "content": "This circular supersedes circular doc_b."
    }

    docs_map = {"doc_a": doc_a, "doc_b": doc_b, "doc_c": doc_c}
    tracker._get_document = MagicMock(side_effect=lambda did: docs_map.get(did))
    tracker._load_all_documents = MagicMock(return_value=[doc_a, doc_b, doc_c])

    # Test timeline for doc_b
    v_info = tracker.get_document_versions("doc_b")
    timeline = v_info.get("timeline", [])
    assert len(timeline) >= 1
    assert v_info["document_id"] == "doc_b"


def test_determine_comparison_eligibility():
    tracker = VersionTracker()

    doc_a = {
        "document_id": "doc_a",
        "title": "IA Norms 2020",
        "category": "Investment Adviser",
        "circular_number": "CIR/2020/01",
        "content": "IA rules."
    }
    doc_b = {
        "document_id": "doc_b",
        "title": "IA Norms 2024",
        "category": "Investment Adviser",
        "circular_number": "CIR/2024/01",
        "content": "This circular supersedes circular CIR/2020/01."
    }
    doc_c = {
        "document_id": "doc_c",
        "title": "MF Rules",
        "category": "Mutual Funds",
        "circular_number": "CIR/MF/2022",
        "content": "MF rules."
    }

    docs_map = {"doc_a": doc_a, "doc_b": doc_b, "doc_c": doc_c}
    tracker._get_document = MagicMock(side_effect=lambda did: docs_map.get(did))

    # doc_a and doc_b have explicit supersession
    elig_ab, _ = tracker.determine_comparison_eligibility("doc_a", "doc_b")
    assert elig_ab == "high"

    # doc_a and doc_c have different categories
    elig_ac, msg = tracker.determine_comparison_eligibility("doc_a", "doc_c")
    assert elig_ac == "low"
    assert "not share the same regulatory category" in msg
