from unittest.mock import patch, MagicMock
import pytest
from app.change_detection.detector import RegulatoryChangeDetector, ChangeReport
from app.rag.pipeline import RAGPipeline


def test_integration_change_detection_pipeline():
    detector = RegulatoryChangeDetector()
    all_docs = detector.load_all_documents()
    if len(all_docs) < 2:
        from app.ingestion.models import RegulatoryDocument, DocumentMetadata
        doc1 = RegulatoryDocument(
            document_id="sebi_ia_2024",
            url="https://sebi.gov.in/ia2024.html",
            title="Master Circular for Investment Advisers 2024",
            source="SEBI",
            document_type="Master Circular",
            category="Investment Adviser",
            published_date="2024-05-24",
            content="# Section 1. Qualifications\nAdvisers must hold NISM certification.\n# Section 2. Record Keeping\nMaintain records for 8 years.",
            metadata=DocumentMetadata(category="Investment Adviser", published_date="2024-05-24")
        )
        doc2 = RegulatoryDocument(
            document_id="sebi_ia_2020",
            url="https://sebi.gov.in/ia2020.html",
            title="Master Circular for Investment Advisers 2020",
            source="SEBI",
            document_type="Master Circular",
            category="Investment Adviser",
            published_date="2020-09-23",
            content="# Section 1. Qualifications\nAdvisers must hold NISM certification.\n# Section 2. Record Keeping\nMaintain records for 5 years.",
            metadata=DocumentMetadata(category="Investment Adviser", published_date="2020-09-23")
        )
        all_docs = [doc1, doc2]

    # Pick the newest Investment Adviser or general document
    current_doc = all_docs[0]
    report: ChangeReport = detector.analyze_documents(current_doc, candidate_docs=all_docs)

    assert report is not None
    assert report.status in {"SUCCESS", "NO_RELIABLE_PREDECESSOR"}
    if report.status == "SUCCESS":
        assert report.total_sections_compared > 0
        assert len(report.changes) > 0


def test_integration_rag_pipeline_change_analysis_routing():
    pipeline = RAGPipeline(retrieval_mode="hybrid", enable_reranker=False)
    query = "What changed in the SEBI investment adviser circulars?"

    with patch.object(pipeline, "retrieve_candidates", return_value=[]), \
         patch.object(pipeline.generator, "generate_answer", return_value={"answer": "Changes detected [1].", "sources": []}):
        response = pipeline.answer(query)
        assert response is not None
        assert response.query_intent is not None
        assert response.query_intent.get("query_type") == "change_analysis"
