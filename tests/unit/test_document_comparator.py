import pytest
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.change_detection.document_comparator import DocumentComparator
from app.change_detection.detector import ChangeReport


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
        metadata=DocumentMetadata(category="Investment Adviser")
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
        metadata=DocumentMetadata(category="Investment Adviser")
    )

    # Save to tmp_path
    import json
    with open(tmp_path / "doc_a_baseline.json", "w", encoding="utf-8") as f:
        json.dump(doc_a.model_dump(), f)
    with open(tmp_path / "doc_b_revised.json", "w", encoding="utf-8") as f:
        json.dump(doc_b.model_dump(), f)

    return tmp_path, "doc_a_baseline", "doc_b_revised"


def test_document_comparator_direct_comparison(sample_comparator_docs):
    dir_path, doc_a_id, doc_b_id = sample_comparator_docs
    comparator = DocumentComparator(processed_data_dir=dir_path)

    report: ChangeReport = comparator.compare_documents(doc_a_id, doc_b_id)

    assert report.status == "SUCCESS"
    assert report.total_sections_compared == 4
    assert report.modified_count == 1   # Net worth modified
    assert report.unchanged_count == 1  # Audit unchanged
    assert report.added_count == 1      # Digital Portal added
    assert report.removed_count == 1    # Paper Submissions removed


def test_document_comparator_missing_document(tmp_path):
    comparator = DocumentComparator(processed_data_dir=tmp_path)
    report = comparator.compare_documents("nonexistent_a", "nonexistent_b")

    assert report.status == "ERROR"
    assert "was not found" in report.message


def test_document_comparator_identical_documents(sample_comparator_docs):
    dir_path, doc_a_id, _ = sample_comparator_docs
    comparator = DocumentComparator(processed_data_dir=dir_path)

    report: ChangeReport = comparator.compare_documents(doc_a_id, doc_a_id)

    assert report.status == "SUCCESS"
    assert report.modified_count == 0
    assert report.added_count == 0
    assert report.removed_count == 0
    assert report.unchanged_count == 3
