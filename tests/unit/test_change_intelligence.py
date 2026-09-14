"""
Unit tests for Regulatory Change Intelligence Engine ("What Changed?") (Phase 59).
"""

import pytest
from unittest.mock import MagicMock
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.change_detection.change_intelligence import (
    ChangeIntelligenceEngine,
    ChangeIntelligenceCache,
    determine_change_severity,
    ImpactDetails,
    CHANGE_ENGINE_VERSION
)


@pytest.fixture
def mock_comparator():
    comparator = MagicMock()
    return comparator


@pytest.fixture
def mock_timeline_service():
    timeline_service = MagicMock()
    return timeline_service


def _make_doc(doc_id: str, title: str, content: str, circ_num: str = "CIR/001", pub_date: str = "2024-01-01"):
    return RegulatoryDocument(
        document_id=doc_id,
        url=f"https://www.sebi.gov.in/{doc_id}.html",
        title=title,
        source="SEBI",
        circular_number=circ_num,
        published_date=pub_date,
        content=content,
        metadata=DocumentMetadata(
            circular_number=circ_num,
            published_date=pub_date
        )
    )


def test_mode_a_no_reliable_predecessor(mock_comparator, mock_timeline_service):
    """Test Mode A when document has no reliable predecessor returns NO_RELIABLE_PREDECESSOR."""
    doc_new = _make_doc("doc_standalone", "Standalone Circular", "Content of standalone circular.")
    mock_comparator.load_document.return_value = doc_new
    mock_timeline_service.get_document_timeline.return_value = {
        "has_reliable_predecessor": False,
        "predecessor_id": None,
        "status": "UNKNOWN"
    }

    engine = ChangeIntelligenceEngine(
        comparator=mock_comparator,
        timeline_service=mock_timeline_service,
        cache=ChangeIntelligenceCache()
    )

    report = engine.analyze_document_changes(current_document_id="doc_standalone")
    assert report.status == "NO_RELIABLE_PREDECESSOR"
    assert "No reliable predecessor" in report.message
    assert report.current_document["document_id"] == "doc_standalone"


def test_identical_documents_unchanged(mock_comparator):
    """Test identical documents return UNCHANGED without calling LLM."""
    content = "## 1. Eligibility Norms\nNet worth of INR 50 Lakhs shall be maintained."
    doc_a = _make_doc("doc_a", "Circular 2020", content, pub_date="2020-01-01")
    doc_b = _make_doc("doc_b", "Circular 2024", content, pub_date="2024-01-01")

    mock_comparator.load_document.side_effect = lambda did: doc_a if did == "doc_a" else doc_b
    mock_comparator.determine_chronology.return_value = (doc_a, doc_b, "high")
    mock_comparator.determine_version_relationship.return_value = ("SUPERSEDES", "HIGH", "Explicit supersession")

    mock_llm = MagicMock()
    engine = ChangeIntelligenceEngine(
        comparator=mock_comparator,
        cache=ChangeIntelligenceCache(),
        generator_client=mock_llm
    )

    report = engine.compare_pair(doc_a_id="doc_a", doc_b_id="doc_b", generate_summaries=True)
    assert report.status == "SUCCESS"
    assert report.summary.unchanged == 1
    assert report.summary.modified == 0
    assert report.summary.added == 0
    assert report.summary.removed == 0
    # Gemini must NOT be called for identical sections
    mock_llm.models.generate_content.assert_not_called()


def test_formatting_only_change_is_unchanged(mock_comparator):
    """Superficial formatting and quote variations must be treated as UNCHANGED."""
    text_old = "## 1. Compliance Norms\nThe adviser shall submit reports within '30 days'."
    text_new = "## 1. Compliance Norms\n\n  The adviser  shall submit  reports within “30 days”.  \n"

    doc_a = _make_doc("doc_a", "Circular 2020", text_old, pub_date="2020-01-01")
    doc_b = _make_doc("doc_b", "Circular 2024", text_new, pub_date="2024-01-01")

    mock_comparator.load_document.side_effect = lambda did: doc_a if did == "doc_a" else doc_b
    mock_comparator.determine_chronology.return_value = (doc_a, doc_b, "high")
    mock_comparator.determine_version_relationship.return_value = ("UPDATE", "HIGH", "Matched")

    mock_llm = MagicMock()
    engine = ChangeIntelligenceEngine(
        comparator=mock_comparator,
        cache=ChangeIntelligenceCache(),
        generator_client=mock_llm
    )

    report = engine.compare_pair(doc_a_id="doc_a", doc_b_id="doc_b", generate_summaries=True)
    assert report.status == "SUCCESS"
    assert report.summary.unchanged == 1
    mock_llm.models.generate_content.assert_not_called()


def test_added_and_removed_sections(mock_comparator):
    """Test detection of added and removed sections with evidence mapping."""
    text_old = "## 1. Existing Section\nRetained text.\n## 2. Removed Section\nThis clause is eliminated."
    text_new = "## 1. Existing Section\nRetained text.\n## 3. Brand New Section\nNew disclosure requirement."

    doc_a = _make_doc("doc_a", "Circular 2020", text_old, pub_date="2020-01-01")
    doc_b = _make_doc("doc_b", "Circular 2024", text_new, pub_date="2024-01-01")

    mock_comparator.load_document.side_effect = lambda did: doc_a if did == "doc_a" else doc_b
    mock_comparator.determine_chronology.return_value = (doc_a, doc_b, "high")
    mock_comparator.determine_version_relationship.return_value = ("UPDATE", "HIGH", "Matched")

    engine = ChangeIntelligenceEngine(
        comparator=mock_comparator,
        cache=ChangeIntelligenceCache()
    )

    report = engine.compare_pair(doc_a_id="doc_a", doc_b_id="doc_b", generate_summaries=False)
    assert report.status == "SUCCESS"
    assert report.summary.added == 1
    assert report.summary.removed == 1
    assert report.summary.unchanged == 1

    added_item = next(c for c in report.changes if c.change_type == "ADDED")
    assert added_item.new_document_id == "doc_b"
    assert added_item.previous_document_id is None
    assert len(added_item.evidence) > 0

    removed_item = next(c for c in report.changes if c.change_type == "REMOVED")
    assert removed_item.previous_document_id == "doc_a"
    assert removed_item.new_document_id is None
    assert len(removed_item.evidence) > 0


def test_modified_deadline_and_threshold_change(mock_comparator):
    """Test substantive changes with deadline and threshold subtypes and HIGH severity."""
    text_old = "## 1. Net Worth Requirements\nNet worth requirement is INR 25 Lakhs.\n## 2. Reporting Deadline\nSubmit report within 30 days."
    text_new = "## 1. Net Worth Requirements\nNet worth requirement is INR 50 Lakhs.\n## 2. Reporting Deadline\nSubmit report within 15 days."

    doc_a = _make_doc("doc_a", "Circular 2020", text_old, pub_date="2020-01-01")
    doc_b = _make_doc("doc_b", "Circular 2024", text_new, pub_date="2024-01-01")

    mock_comparator.load_document.side_effect = lambda did: doc_a if did == "doc_a" else doc_b
    mock_comparator.determine_chronology.return_value = (doc_a, doc_b, "high")
    mock_comparator.determine_version_relationship.return_value = ("SUPERSEDES", "HIGH", "Explicit")

    engine = ChangeIntelligenceEngine(
        comparator=mock_comparator,
        cache=ChangeIntelligenceCache()
    )

    report = engine.compare_pair(doc_a_id="doc_a", doc_b_id="doc_b", generate_summaries=False)
    assert report.status == "SUCCESS"
    assert report.summary.modified == 2

    # Check evidence mapping
    for ch in report.changes:
        if ch.change_type == "MODIFIED":
            assert ch.previous_document_id == "doc_a"
            assert ch.new_document_id == "doc_b"
            assert ch.substantive_change is True
            assert ch.severity == "HIGH"


def test_severity_logic():
    """Verify conservative severity classification rules."""
    assert determine_change_severity("THRESHOLD_CHANGED", True, None) == "HIGH"
    assert determine_change_severity("DEADLINE_CHANGED", True, None) == "HIGH"
    assert determine_change_severity("REPORTING_CHANGED", True, None) == "MEDIUM"
    assert determine_change_severity("PROCEDURE_CHANGED", True, None) == "MEDIUM"
    assert determine_change_severity(None, False, None) == "LOW"


def test_cache_hit_and_engine_version(mock_comparator):
    """Test caching by content hash and engine version."""
    doc_a = _make_doc("doc_a", "Circular A", "Content A", pub_date="2020-01-01")
    doc_b = _make_doc("doc_b", "Circular B", "Content B", pub_date="2024-01-01")

    mock_comparator.load_document.side_effect = lambda did: doc_a if did == "doc_a" else doc_b
    mock_comparator.determine_chronology.return_value = (doc_a, doc_b, "high")
    mock_comparator.determine_version_relationship.return_value = ("UPDATE", "HIGH", "Matched")

    cache = ChangeIntelligenceCache()
    engine = ChangeIntelligenceEngine(comparator=mock_comparator, cache=cache)

    res1 = engine.compare_pair("doc_a", "doc_b", generate_summaries=False)
    assert res1.cached is False
    assert res1.change_engine_version == CHANGE_ENGINE_VERSION

    # Second call returns cached = True
    res2 = engine.compare_pair("doc_a", "doc_b", generate_summaries=False)
    assert res2.cached is True

    # Invalidate cache
    cache.clear()
    res3 = engine.compare_pair("doc_a", "doc_b", generate_summaries=False)
    assert res3.cached is False


def test_markdown_export(mock_comparator):
    """Verify Markdown export format includes old/new docs, statistics, and evidence."""
    doc_a = _make_doc("doc_a", "Circular 2020", "## 1. Scope\nOld rules.", pub_date="2020-01-01")
    doc_b = _make_doc("doc_b", "Circular 2024", "## 1. Scope\nNew rules.", pub_date="2024-01-01")

    mock_comparator.load_document.side_effect = lambda did: doc_a if did == "doc_a" else doc_b
    mock_comparator.determine_chronology.return_value = (doc_a, doc_b, "high")
    mock_comparator.determine_version_relationship.return_value = ("UPDATE", "HIGH", "Matched")

    engine = ChangeIntelligenceEngine(comparator=mock_comparator, cache=ChangeIntelligenceCache())
    report = engine.compare_pair("doc_a", "doc_b", generate_summaries=False)

    md = report.export_markdown()
    assert "REGULATORY CHANGE INTELLIGENCE REPORT" in md
    assert "Circular 2020" in md
    assert "Circular 2024" in md
    assert "Executive Change Summary" in md
