"""
Unit tests for Version Relationships, Timeline, and Lineage Resolution (Phase 40).
"""

import json
import pytest
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.ingestion.version_tracker import VersionTracker


@pytest.fixture
def sample_version_chain_docs(tmp_path):
    # Chain: A -> B -> C
    doc_a = RegulatoryDocument(
        document_id="doc_a_2020",
        url="https://sebi.gov.in/doc_a_2020.html",
        circular_number="SEBI/HO/IMD/2020/01",
        title="SEBI Master Circular 2020 for IAs",
        source="SEBI",
        category="Investment Adviser",
        published_date="2020-01-15",
        content="Base guidelines for investment advisers.",
        metadata=DocumentMetadata(circular_number="SEBI/HO/IMD/2020/01", category="Investment Adviser", published_date="2020-01-15")
    )

    doc_b = RegulatoryDocument(
        document_id="doc_b_2022",
        url="https://sebi.gov.in/doc_b_2022.html",
        circular_number="SEBI/HO/IMD/2022/05",
        title="SEBI Master Circular 2022 for IAs",
        source="SEBI",
        category="Investment Adviser",
        published_date="2022-06-10",
        content="In supersession of circular SEBI/HO/IMD/2020/01, updated IA norms are notified.",
        metadata=DocumentMetadata(circular_number="SEBI/HO/IMD/2022/05", category="Investment Adviser", published_date="2022-06-10")
    )

    doc_c = RegulatoryDocument(
        document_id="doc_c_2024",
        url="https://sebi.gov.in/doc_c_2024.html",
        circular_number="SEBI/HO/IMD/2024/09",
        title="SEBI Master Circular 2024 for IAs",
        source="SEBI",
        category="Investment Adviser",
        published_date="2024-05-24",
        content="This master circular supersedes circular SEBI/HO/IMD/2022/05 for investment advisers.",
        metadata=DocumentMetadata(circular_number="SEBI/HO/IMD/2024/09", category="Investment Adviser", published_date="2024-05-24")
    )

    with open(tmp_path / "doc_a_2020.json", "w", encoding="utf-8") as f:
        json.dump(doc_a.model_dump(), f)
    with open(tmp_path / "doc_b_2022.json", "w", encoding="utf-8") as f:
        json.dump(doc_b.model_dump(), f)
    with open(tmp_path / "doc_c_2024.json", "w", encoding="utf-8") as f:
        json.dump(doc_c.model_dump(), f)

    return tmp_path


def test_detect_explicit_supersession():
    vt = VersionTracker()
    text = "This circular is issued in supersession of circular SEBI/HO/IMD/DF1/CIR/P/2020/182 dated September 23, 2020."
    res = vt.detect_explicit_supersession(text)
    assert res is not None
    assert "SEBI/HO/IMD/DF1/CIR/P/2020/182" in res


def test_resolve_version_chain_and_timeline(sample_version_chain_docs, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "processed_data_dir", sample_version_chain_docs)

    vt = VersionTracker()
    versions_c = vt.get_document_versions("doc_c_2024")

    assert versions_c["document_id"] == "doc_c_2024"
    assert versions_c["relationship_type"] == "SUPERSEDES"
    assert versions_c["relationship_confidence"] == "high"
    assert versions_c["predecessor"] is not None
    assert versions_c["predecessor"]["document_id"] == "doc_b_2022"

    # Verify timeline nodes contain chronological order
    timeline = versions_c["timeline"]
    assert len(timeline) >= 2
    timeline_ids = [n["document_id"] for n in timeline]
    assert "doc_a_2020" in timeline_ids
    assert "doc_b_2022" in timeline_ids
    assert "doc_c_2024" in timeline_ids


def test_comparison_eligibility(sample_version_chain_docs, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "processed_data_dir", sample_version_chain_docs)

    vt = VersionTracker()
    eligibility, warn = vt.determine_comparison_eligibility("doc_b_2022", "doc_c_2024")
    assert eligibility == "high"
    assert warn is None
