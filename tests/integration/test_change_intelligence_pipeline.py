"""
Integration tests for the complete Change Intelligence and Regulatory Diff Pipeline (Phase 60.23).
"""

import pytest
from unittest.mock import MagicMock
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.change_detection.change_intelligence import ChangeIntelligenceEngine, ChangeIntelligenceCache
from app.change_detection.diff_engine import RegulatoryDiffEngine, SectionDiffCache


def test_end_to_end_pipeline_integration():
    """
    Simulates complete pipeline:
    Document A + Document B
    -> Section hierarchy
    -> Section diff (Added, Removed, Modified, Moved)
    -> Paragraph & Numerical changes (30 days -> 15 days, 25 Lakhs -> 50 Lakhs)
    -> Substantive change detection & severity
    -> Evidence mapping to both documents and sections
    -> What Changed report synthesis
    """
    doc_a_content = """
    Chapter I: Obligations
    ## 1. Eligibility Criteria
    Page 1. The intermediary must possess a minimum net worth of INR 25 Lakhs.
    
    ## 2. Reporting Timelines
    Page 2. The compliance certificate shall be submitted within 30 days.
    
    ## 3. Prior Requirement to Repeal
    Page 3. Physical paper filings are required.
    """

    doc_b_content = """
    Chapter I: Obligations
    ## 1. Eligibility Criteria
    Page 5. The intermediary must possess a minimum net worth of INR 50 Lakhs.
    
    ## 2. Reporting Timelines
    Page 6. The compliance certificate shall be submitted within 15 days.
    
    ## 4. New Digital Governance
    Page 7. All submissions must be performed digitally on the SEBI portal.
    """

    doc_a = RegulatoryDocument(
        document_id="sebi_ia_2020",
        url="https://www.sebi.gov.in/cir_2020.html",
        title="SEBI (Investment Advisers) Circular 2020",
        source="SEBI",
        circular_number="SEBI/HO/IMD/2020/01",
        published_date="2020-09-23",
        effective_date="2021-01-01",
        content=doc_a_content,
        metadata=DocumentMetadata(
            circular_number="SEBI/HO/IMD/2020/01",
            published_date="2020-09-23",
            effective_date="2021-01-01",
            category="Investment Adviser"
        )
    )

    doc_b = RegulatoryDocument(
        document_id="sebi_ia_2024",
        url="https://www.sebi.gov.in/cir_2024.html",
        title="SEBI Master Circular for Investment Advisers 2024",
        source="SEBI",
        circular_number="SEBI/HO/MIRSD/2024/15",
        published_date="2024-05-15",
        effective_date="2024-06-01",
        content=doc_b_content,
        metadata=DocumentMetadata(
            circular_number="SEBI/HO/MIRSD/2024/15",
            published_date="2024-05-15",
            effective_date="2024-06-01",
            category="Investment Adviser",
            supersedes="sebi_ia_2020"
        )
    )

    # 1. Section Diff Pipeline
    diff_engine = RegulatoryDiffEngine(cache=SectionDiffCache())
    diff_report = diff_engine.diff_documents(
        older_doc_id=doc_a.document_id,
        older_content=doc_a.content,
        newer_doc_id=doc_b.document_id,
        newer_content=doc_b.content
    )

    assert diff_report.status == "SUCCESS"
    assert diff_report.statistics["modified"] == 2
    assert diff_report.statistics["removed"] == 1
    assert diff_report.statistics["added"] == 1

    # Verify numerical shift in Section 1 (25 Lakhs -> 50 Lakhs)
    sec_eligibility = next(s for s in diff_report.sections if s.heading == "Eligibility Criteria")
    assert sec_eligibility.change_type == "MODIFIED"
    assert sec_eligibility.old_page == 1
    assert sec_eligibility.new_page == 5
    assert any("25 Lakhs" in nc.previous_value and "50 Lakhs" in nc.new_value for nc in sec_eligibility.numerical_changes)

    # Verify numerical shift in Section 2 (30 days -> 15 days)
    sec_reporting = next(s for s in diff_report.sections if s.heading == "Reporting Timelines")
    assert sec_reporting.change_type == "MODIFIED"
    assert sec_reporting.old_page == 2
    assert sec_reporting.new_page == 6
    assert any("30 days" in nc.previous_value and "15 days" in nc.new_value for nc in sec_reporting.numerical_changes)

    # 2. Change Intelligence Pipeline
    mock_comparator = MagicMock()
    mock_comparator.load_document.side_effect = lambda did: doc_a if did == doc_a.document_id else doc_b
    mock_comparator.determine_chronology.return_value = (doc_a, doc_b, "high")
    mock_comparator.determine_version_relationship.return_value = ("SUPERSEDES", "HIGH", "Master circular supersession")

    ci_engine = ChangeIntelligenceEngine(
        comparator=mock_comparator,
        cache=ChangeIntelligenceCache()
    )

    ci_report = ci_engine.compare_pair(
        doc_a_id=doc_a.document_id,
        doc_b_id=doc_b.document_id,
        generate_summaries=False
    )

    assert ci_report.status == "SUCCESS"
    assert ci_report.summary.modified == 2
    assert ci_report.summary.added == 1
    assert ci_report.summary.removed == 1
    assert ci_report.summary.total_substantive >= 3

    # Evidence Mapping Verification
    for change in ci_report.changes:
        if change.change_type == "MODIFIED":
            assert change.previous_document_id == "sebi_ia_2020"
            assert change.new_document_id == "sebi_ia_2024"
            assert len(change.evidence) > 0
        elif change.change_type == "ADDED":
            assert change.previous_document_id is None
            assert change.new_document_id == "sebi_ia_2024"
        elif change.change_type == "REMOVED":
            assert change.previous_document_id == "sebi_ia_2020"
            assert change.new_document_id is None

    # Markdown Export
    md_export = ci_report.export_markdown()
    assert "REGULATORY CHANGE INTELLIGENCE REPORT" in md_export
    assert "SEBI (Investment Advisers) Circular 2020" in md_export
    assert "SEBI Master Circular for Investment Advisers 2024" in md_export
