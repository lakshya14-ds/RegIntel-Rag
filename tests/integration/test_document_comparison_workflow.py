"""
Integration tests for End-to-End Regulatory Document Comparison Workflow (Phases 39–41).
"""

import json
import pytest
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.change_detection.document_comparator import DocumentComparator, ComparisonReport
from app.config import settings


@pytest.fixture
def complex_regulatory_circular_pair(tmp_path):
    doc_2020 = RegulatoryDocument(
        document_id="sebi_ia_circ_2020",
        url="https://sebi.gov.in/sebi_ia_circ_2020.html",
        circular_number="SEBI/HO/IMD/DF1/CIR/P/2020/182",
        title="SEBI Circular on Administration and Supervision of Investment Advisers",
        source="SEBI",
        document_type="Circular",
        category="Investment Adviser",
        published_date="2020-09-23",
        effective_date="2020-09-23",
        status="historical",
        content="""# 1. Qualification and Experience Criteria
Individuals registered as investment advisers shall hold a postgraduate degree and minimum 5 years experience.

# 2. Client Agreement and Fee Cap
Investment Advisers shall charge fees under either Fixed Fee (max INR 1,25,000 per annum) or Percentage of AUA (max 2.5% per annum).

# 3. Physical Records Retention
All client risk profiling records shall be maintained physically for a period of 5 years.

# 4. Grievance Redressal
Resolve client complaints within 30 calendar days.
""",
        metadata=DocumentMetadata(
            category="Investment Adviser",
            circular_number="SEBI/HO/IMD/DF1/CIR/P/2020/182",
            published_date="2020-09-23"
        )
    )

    doc_2024 = RegulatoryDocument(
        document_id="sebi_ia_master_2024",
        url="https://sebi.gov.in/sebi_ia_master_2024.html",
        circular_number="SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2024/56",
        title="Master Circular for Investment Advisers (IAs)",
        source="SEBI",
        document_type="Master Circular",
        category="Investment Adviser",
        published_date="2024-05-24",
        effective_date="2024-05-24",
        status="current",
        content="""# 1. Qualification and Experience Criteria
Individuals registered as investment advisers shall hold a postgraduate degree and minimum 5 years experience.

# 2. Client Agreement and Fee Schedules
Investment Advisers shall charge fees under either Fixed Fee (max INR 1,25,000 per annum) or Percentage of AUA (max 2.5% per annum) with mandatory digital agreement execution.

# 3. Digital Records Retention
All client risk profiling records shall be maintained in secure digital format for a minimum period of 8 years.

# 5. SCORES 2.0 Escalation Matrix
Mandatory auto-routing and redressal within 21 calendar days via SCORES 2.0 portal.
""",
        metadata=DocumentMetadata(
            category="Investment Adviser",
            circular_number="SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2024/56",
            published_date="2024-05-24",
            supersedes="sebi_ia_circ_2020"
        )
    )

    with open(tmp_path / "sebi_ia_circ_2020.json", "w", encoding="utf-8") as f:
        json.dump(doc_2020.model_dump(), f)
    with open(tmp_path / "sebi_ia_master_2024.json", "w", encoding="utf-8") as f:
        json.dump(doc_2024.model_dump(), f)

    return tmp_path, "sebi_ia_circ_2020", "sebi_ia_master_2024"


def test_end_to_end_comparison_workflow(complex_regulatory_circular_pair):
    dir_path, doc_2020_id, doc_2024_id = complex_regulatory_circular_pair
    comparator = DocumentComparator(processed_data_dir=dir_path)

    # Compare Document 2020 and 2024
    report: ComparisonReport = comparator.compare_documents(doc_2020_id, doc_2024_id, generate_summaries=False)

    assert report.status == "SUCCESS"
    assert report.older_document["document_id"] == doc_2020_id
    assert report.newer_document["document_id"] == doc_2024_id
    assert report.document_order_confidence == "high"

    # Verify counts:
    # 1. Sec 1: UNCHANGED (Exact match)
    # 2. Sec 2: MODIFIED (Digital agreement added)
    # 3. Sec 3: MODIFIED (5 years -> 8 years)
    # 4. Sec 5 (SCORES): ADDED (in 2024)
    # 5. Sec 4 (Grievance): REMOVED (in 2020)
    counts = report.summary_counts
    assert counts["unchanged"] == 1
    assert counts["modified"] == 2
    assert counts["added"] == 1
    assert counts["removed"] == 1

    # Verify all substantive changes have evidence mapping
    for ch in report.changes:
        if ch.change_type == "MODIFIED":
            assert ch.old_source is not None
            assert ch.new_source is not None
            assert ch.previous_text is not None
            assert ch.current_text is not None
        elif ch.change_type == "ADDED":
            assert ch.new_source is not None
            assert ch.previous_text is None
        elif ch.change_type == "REMOVED":
            assert ch.old_source is not None
            assert ch.current_text is None

    # Test reverse order input (user provides doc_2024_id as A and doc_2020_id as B)
    # System must still correctly identify doc_2020 as older and doc_2024 as newer!
    reverse_report = comparator.compare_documents(doc_2024_id, doc_2020_id, generate_summaries=False)
    assert reverse_report.older_document["document_id"] == doc_2020_id
    assert reverse_report.newer_document["document_id"] == doc_2024_id
    assert reverse_report.document_order_confidence == "high"
