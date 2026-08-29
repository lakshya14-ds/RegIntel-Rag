"""
Unit tests for DocumentComparator and Direct Comparison Engine (Phase 39).
"""

import json
import pytest
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.change_detection.document_comparator import DocumentComparator, ComparisonReport


@pytest.fixture
def sample_comparator_docs(tmp_path):
    doc_a = RegulatoryDocument(
        document_id="doc_a_baseline",
        url="https://sebi.gov.in/baseline.html",
        title="SEBI Circular 2020 on IA Framework",
        source="SEBI",
        document_type="Circular",
        category="Investment Adviser",
        published_date="2020-09-23",
        content="""# 1. Net Worth
Net worth requirement is INR 25 Lakhs.

# 2. Audit
Annual compliance audit within 6 months.

# 3. Paper Submissions
Submit physical quarterly reports.
""",
        metadata=DocumentMetadata(category="Investment Adviser", published_date="2020-09-23")
    )

    doc_b = RegulatoryDocument(
        document_id="doc_b_revised",
        url="https://sebi.gov.in/revised.html",
        title="SEBI Master Circular 2024 for IAs",
        source="SEBI",
        document_type="Master Circular",
        category="Investment Adviser",
        published_date="2024-05-24",
        content="""# 1. Net Worth
Net worth requirement is INR 50 Lakhs.

# 2. Audit
Annual compliance audit within 6 months.

# 4. Digital Portal
Submit quarterly reports via SEBI portal.
""",
        metadata=DocumentMetadata(category="Investment Adviser", published_date="2024-05-24")
    )

    with open(tmp_path / "doc_a_baseline.json", "w", encoding="utf-8") as f:
        json.dump(doc_a.model_dump(), f)
    with open(tmp_path / "doc_b_revised.json", "w", encoding="utf-8") as f:
        json.dump(doc_b.model_dump(), f)

    return tmp_path, "doc_a_baseline", "doc_b_revised"


def test_document_comparator_direct_comparison(sample_comparator_docs):
    dir_path, doc_a_id, doc_b_id = sample_comparator_docs
    comparator = DocumentComparator(processed_data_dir=dir_path)

    report: ComparisonReport = comparator.compare_documents(doc_a_id, doc_b_id, generate_summaries=False)

    assert report.status == "SUCCESS"
    assert report.total_sections_compared == 4
    assert report.modified_count == 1   # Net worth modified
    assert report.unchanged_count == 1  # Audit unchanged
    assert report.added_count == 1      # Digital Portal added
    assert report.removed_count == 1    # Paper Submissions removed

    # Check chronology
    assert report.older_document.get("document_id") == doc_a_id
    assert report.newer_document.get("document_id") == doc_b_id
    assert report.document_order_confidence == "high"

    # Check evidence mapping
    mod_changes = [c for c in report.changes if c.change_type == "MODIFIED"]
    assert len(mod_changes) == 1
    assert mod_changes[0].old_source is not None
    assert mod_changes[0].new_source is not None
    assert mod_changes[0].old_source.document_id == doc_a_id
    assert mod_changes[0].new_source.document_id == doc_b_id


def test_document_comparator_missing_document(tmp_path):
    comparator = DocumentComparator(processed_data_dir=tmp_path)
    report = comparator.compare_documents("nonexistent_a", "nonexistent_b")

    assert report.status == "ERROR"
    assert "was not found" in report.message


def test_document_comparator_identical_documents(sample_comparator_docs):
    dir_path, doc_a_id, _ = sample_comparator_docs
    comparator = DocumentComparator(processed_data_dir=dir_path)

    report: ComparisonReport = comparator.compare_documents(doc_a_id, doc_a_id, generate_summaries=False)

    assert report.status == "SUCCESS"
    assert report.modified_count == 0
    assert report.added_count == 0
    assert report.removed_count == 0
    assert report.unchanged_count == 3


def test_document_comparator_formatting_only_difference(tmp_path):
    doc_1 = RegulatoryDocument(
        document_id="doc_fmt_1",
        url="https://sebi.gov.in/doc_fmt_1.html",
        title="Circular 1",
        source="SEBI",
        category="Investment Adviser",
        published_date="2021-01-01",
        content="""# 1. Audit
Annual compliance audit within 6 months.
""",
        metadata=DocumentMetadata(category="Investment Adviser", published_date="2021-01-01")
    )
    doc_2 = RegulatoryDocument(
        document_id="doc_fmt_2",
        url="https://sebi.gov.in/doc_fmt_2.html",
        title="Circular 2",
        source="SEBI",
        category="Investment Adviser",
        published_date="2022-01-01",
        content="""# 1. Audit
  Annual compliance audit within 6 months.  
""",
        metadata=DocumentMetadata(category="Investment Adviser", published_date="2022-01-01")
    )
    with open(tmp_path / "doc_fmt_1.json", "w", encoding="utf-8") as f:
        json.dump(doc_1.model_dump(), f)
    with open(tmp_path / "doc_fmt_2.json", "w", encoding="utf-8") as f:
        json.dump(doc_2.model_dump(), f)

    comparator = DocumentComparator(processed_data_dir=tmp_path)
    report = comparator.compare_documents("doc_fmt_1", "doc_fmt_2", generate_summaries=False)

    assert report.status == "SUCCESS"
    assert report.unchanged_count == 1
    assert report.modified_count == 0
