import pytest
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.change_detection.detector import RegulatoryChangeDetector, ChangeReport, validate_change_report


@pytest.fixture
def mock_documents_for_change():
    doc_curr = RegulatoryDocument(
        document_id="doc_curr_ia",
        url="https://sebi.gov.in/curr.html",
        title="Master Circular for Investment Advisers 2024",
        source="SEBI",
        document_type="Master Circular",
        category="Investment Adviser",
        published_date="2024-05-24",
        content="""# 1. Eligibility
Net worth required is INR 50 Lakhs.

# 2. Record Keeping
Records must be maintained for 8 years.

# 3. Cybersecurity Policy
Must implement periodic vulnerability assessment.
""",
        metadata=DocumentMetadata(
            document_type="Master Circular",
            category="Investment Adviser",
            published_date="2024-05-24"
        )
    )

    doc_prev = RegulatoryDocument(
        document_id="doc_prev_ia",
        url="https://sebi.gov.in/prev.html",
        title="Master Circular for Investment Advisers 2020",
        source="SEBI",
        document_type="Master Circular",
        category="Investment Adviser",
        published_date="2020-09-23",
        content="""# 1. Eligibility
Net worth required is INR 25 Lakhs.

# 2. Record Keeping
Records must be maintained for 8 years.

# 4. Physical Submission
Quarterly physical letters must be sent.
""",
        metadata=DocumentMetadata(
            document_type="Master Circular",
            category="Investment Adviser",
            published_date="2020-09-23"
        )
    )

    return doc_curr, doc_prev


def test_change_detector_full_analysis(mock_documents_for_change):
    doc_curr, doc_prev = mock_documents_for_change
    detector = RegulatoryChangeDetector()

    report: ChangeReport = detector.analyze_documents(doc_curr, previous_doc=doc_prev)

    assert report.status == "SUCCESS"
    assert report.total_sections_compared == 4
    assert report.modified_count == 1   # Eligibility changed (25L -> 50L)
    assert report.unchanged_count == 1  # Record keeping (8 years)
    assert report.added_count == 1      # Cybersecurity Policy
    assert report.removed_count == 1    # Physical Submission
    assert validate_change_report(report) is True


def test_change_detector_no_predecessor():
    doc_curr = RegulatoryDocument(
        document_id="doc_unique",
        url="https://sebi.gov.in/unique.html",
        title="Unique First Time Sandbox Guidelines",
        source="SEBI",
        document_type="Circular",
        category="Sandboxes",
        published_date="2026-08-26",
        content="# 1. Framework\nSandbox guidelines.",
        metadata=DocumentMetadata(category="Sandboxes")
    )

    detector = RegulatoryChangeDetector()
    report = detector.analyze_documents(doc_curr, candidate_docs=[])

    assert report.status == "NO_RELIABLE_PREDECESSOR"
    assert "No sufficiently reliable predecessor" in report.message
