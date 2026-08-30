"""
End-to-End Version Lineage & Timeline Workflow Test (Phase 51.13).

Tests:
Document Registration -> Predecessor Resolution -> Explicit Supersession Detection ->
Relationship Classification (SUPERSEDES / UPDATE / NEW) -> Lineage Graph Consistency.
"""

import pytest
from unittest.mock import MagicMock
from app.ingestion.version_tracker import VersionTracker


def test_e2e_version_timeline_workflow():
    tracker = VersionTracker()

    doc_2018 = {
        "document_id": "sebi_ia_cir_2018",
        "title": "Master Circular for Investment Advisers 2018",
        "category": "Investment Adviser",
        "source": "SEBI",
        "circular_number": "SEBI/HO/MIRSD/DOS3/CIR/P/2018/115",
        "published_date": "2018-07-13",
        "content": "Original guidelines for Investment Advisers.",
        "status": "historical"
    }

    doc_2024 = {
        "document_id": "sebi_ia_master_2024",
        "title": "Master Circular for Investment Advisers 2024",
        "category": "Investment Adviser",
        "source": "SEBI",
        "circular_number": "SEBI/HO/MIRSD/DOS3/CIR/P/2024/05",
        "published_date": "2024-05-24",
        "content": "This master circular is issued in supersession of circular SEBI/HO/MIRSD/DOS3/CIR/P/2018/115.",
        "status": "current"
    }

    tracker._get_document = MagicMock(side_effect=lambda did: doc_2024 if did == "sebi_ia_master_2024" else doc_2018)
    tracker._load_all_documents = MagicMock(return_value=[doc_2018, doc_2024])

    # 1. Detect explicit legal supersession clause
    ref = tracker.detect_explicit_supersession(doc_2024["content"])
    assert ref is not None
    assert "SEBI/HO/MIRSD/DOS3/CIR/P/2018/115" in ref

    # 2. Resolve document relationship & predecessor
    rel_info = tracker.resolve_document_relationships("sebi_ia_master_2024")
    assert rel_info["relationship_type"] == "SUPERSEDES"
    assert rel_info["relationship_confidence"] == "high"
    assert rel_info["predecessor_id"] == "sebi_ia_cir_2018"
