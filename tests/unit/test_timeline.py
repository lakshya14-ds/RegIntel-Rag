"""
Unit tests for Regulatory Version Timeline 2.0 Service (Phase 58).
"""

import pytest
from unittest.mock import MagicMock
from app.versioning.timeline import TimelineService, TimelineCache, clear_timeline_cache


@pytest.fixture
def mock_tracker():
    tracker = MagicMock()
    return tracker


def test_linear_history(mock_tracker):
    """Test standard linear progression: Doc A superseded by Doc B."""
    docs = [
        {
            "document_id": "doc_a",
            "title": "Circular A 2020",
            "circular_number": "SEBI/HO/IMD/2020/01",
            "published_date": "2020-06-10",
            "effective_date": "2020-07-01",
            "status": "historical",
            "content": "Circular A instructions"
        },
        {
            "document_id": "doc_b",
            "title": "Circular B 2024",
            "circular_number": "SEBI/HO/IMD/2024/05",
            "published_date": "2024-05-15",
            "effective_date": "2024-06-01",
            "status": "current",
            "supersedes": "doc_a",
            "content": "In supersession of circular SEBI/HO/IMD/2020/01"
        }
    ]

    mock_tracker._load_all_documents.return_value = docs
    mock_tracker._get_document.side_effect = lambda did: next((d for d in docs if d["document_id"] == did), None)

    cache = TimelineCache()
    service = TimelineService(tracker=mock_tracker, cache=cache)

    res = service.get_document_timeline("doc_b", current_date="2026-09-01")
    assert res["document_id"] == "doc_b"
    assert res["has_reliable_predecessor"] is True
    assert res["predecessor_id"] == "doc_a"
    assert len(res["events"]) == 2

    # Chronological sort: doc_a first, doc_b second
    assert res["events"][0]["document_id"] == "doc_a"
    assert res["events"][1]["document_id"] == "doc_b"
    assert res["events"][0]["status"] == "SUPERSEDED"


def test_branching_timeline_amendment_and_corrigendum(mock_tracker):
    """Test multi-branch timeline: Base circular A with an Amendment B and Corrigendum C."""
    docs = [
        {
            "document_id": "doc_base",
            "title": "Master Circular for MFs",
            "circular_number": "SEBI/CIR/MF/2023/10",
            "published_date": "2023-01-10",
            "effective_date": "2023-02-01",
            "status": "current",
            "document_type": "Master Circular",
            "content": "Base guidelines for Mutual Funds."
        },
        {
            "document_id": "doc_amend",
            "title": "Amendment to MF Guidelines",
            "circular_number": "SEBI/CIR/MF/2023/45",
            "published_date": "2023-06-20",
            "effective_date": "2023-07-01",
            "amends": "doc_base",
            "content": "Amends circular SEBI/CIR/MF/2023/10 regarding expense ratios."
        },
        {
            "document_id": "doc_corrig",
            "title": "Corrigendum to Master Circular",
            "circular_number": "SEBI/CIR/MF/2023/10/CORR",
            "published_date": "2023-02-15",
            "effective_date": "2023-02-15",
            "corrigendum_of": "doc_base",
            "content": "Corrigendum to circular SEBI/CIR/MF/2023/10 clause 4."
        }
    ]

    mock_tracker._load_all_documents.return_value = docs
    mock_tracker._get_document.side_effect = lambda did: next((d for d in docs if d["document_id"] == did), None)

    cache = TimelineCache()
    service = TimelineService(tracker=mock_tracker, cache=cache)

    res = service.get_document_timeline("doc_base", current_date="2026-09-01")
    events = res["events"]
    assert len(events) == 3

    # Check that branches are correctly flagged
    amend_ev = next(e for e in events if e["document_id"] == "doc_amend")
    assert amend_ev["is_branch"] is True
    assert amend_ev["relationship_to_previous"] == "AMENDS"

    corrig_ev = next(e for e in events if e["document_id"] == "doc_corrig")
    assert corrig_ev["is_branch"] is True
    assert corrig_ev["relationship_to_previous"] == "CORRIGENDUM_OF"


def test_missing_dates_chronology_uncertain(mock_tracker):
    """Test that missing dates flags chronology_uncertain instead of inventing dates."""
    docs = [
        {
            "document_id": "doc_undated_1",
            "title": "Undated Order",
            "published_date": None,
            "effective_date": None,
            "content": "SEBI order details."
        }
    ]

    mock_tracker._load_all_documents.return_value = docs
    mock_tracker._get_document.side_effect = lambda did: next((d for d in docs if d["document_id"] == did), None)

    cache = TimelineCache()
    service = TimelineService(tracker=mock_tracker, cache=cache)

    res = service.get_document_timeline("doc_undated_1")
    assert res["chronology_uncertain"] is True
    assert res["events"][0]["chronology_uncertain"] is True
    assert res["events"][0]["published_date"] is None
    assert res["events"][0]["effective_date"] is None


def test_uncertain_relationship_labeled_low_confidence(mock_tracker):
    """Test that low confidence relationship displays LOW confidence and is marked."""
    docs = [
        {
            "document_id": "doc_target",
            "title": "Target Document",
            "category": "Investment Adviser",
            "published_date": "2024-01-01",
            "content": "Target notice"
        },
        {
            "document_id": "doc_other",
            "title": "Other Related Notice",
            "category": "Investment Adviser",
            "published_date": "2023-01-01",
            "content": "Earlier notice"
        }
    ]

    mock_tracker._load_all_documents.return_value = docs
    mock_tracker._get_document.side_effect = lambda did: next((d for d in docs if d["document_id"] == did), None)
    mock_tracker.resolve_document_relationships.return_value = {
        "predecessor_id": "doc_other",
        "relationship_confidence": "low",
        "relationship_type": "RELATED_TO"
    }

    cache = TimelineCache()
    service = TimelineService(tracker=mock_tracker, cache=cache)

    res = service.get_document_timeline("doc_target")
    # Low confidence should NOT qualify as reliable predecessor
    assert res["has_reliable_predecessor"] is False


def test_cache_hit_and_invalidation(mock_tracker):
    """Test timeline caching and invalidation behavior."""
    docs = [
        {
            "document_id": "doc_cache_test",
            "title": "Test Doc",
            "published_date": "2024-01-01",
            "content_hash": "hash_123",
            "content": "Content"
        }
    ]

    mock_tracker._load_all_documents.return_value = docs
    mock_tracker._get_document.side_effect = lambda did: next((d for d in docs if d["document_id"] == did), None)

    cache = TimelineCache()
    service = TimelineService(tracker=mock_tracker, cache=cache)

    # First call: fresh calculation (cached = False)
    res1 = service.get_document_timeline("doc_cache_test")
    assert res1["cached"] is False

    # Second call: cache hit (cached = True)
    res2 = service.get_document_timeline("doc_cache_test")
    assert res2["cached"] is True

    # Invalidate cache
    cache.invalidate("doc_cache_test")
    res3 = service.get_document_timeline("doc_cache_test")
    assert res3["cached"] is False
