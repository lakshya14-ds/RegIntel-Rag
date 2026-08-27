import pytest
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.change_detection.document_matcher import DocumentMatcher, PredecessorMatch


@pytest.fixture
def sample_documents():
    doc_2024 = RegulatoryDocument(
        document_id="doc_ia_2024",
        url="https://sebi.gov.in/ia_2024.html",
        title="Master Circular for Investment Advisers (IAs)",
        source="SEBI",
        document_type="Master Circular",
        category="Investment Adviser",
        circular_number="SEBI/HO/MIRSD/2024/56",
        published_date="2024-05-24",
        content="This master circular supersedes circular SEBI/HO/MIRSD/2020/12.",
        metadata=DocumentMetadata(
            document_type="Master Circular",
            category="Investment Adviser",
            circular_number="SEBI/HO/MIRSD/2024/56",
            published_date="2024-05-24"
        )
    )

    doc_2020 = RegulatoryDocument(
        document_id="doc_ia_2020",
        url="https://sebi.gov.in/ia_2020.html",
        title="Guidelines and Master Circular for Investment Advisers",
        source="SEBI",
        document_type="Master Circular",
        category="Investment Adviser",
        circular_number="SEBI/HO/MIRSD/2020/12",
        published_date="2020-09-23",
        content="Initial guidelines for registered investment advisers.",
        metadata=DocumentMetadata(
            document_type="Master Circular",
            category="Investment Adviser",
            circular_number="SEBI/HO/MIRSD/2020/12",
            published_date="2020-09-23"
        )
    )

    doc_mf_2023 = RegulatoryDocument(
        document_id="doc_mf_2023",
        url="https://sebi.gov.in/mf_2023.html",
        title="Simplification of Framework for Overseas Investment by Mutual Funds",
        source="SEBI",
        document_type="Circular",
        category="Mutual Funds",
        circular_number="SEBI/HO/IMD/2023/11",
        published_date="2023-11-01",
        content="Mutual funds overseas guidelines.",
        metadata=DocumentMetadata(
            document_type="Circular",
            category="Mutual Funds",
            circular_number="SEBI/HO/IMD/2023/11",
            published_date="2023-11-01"
        )
    )

    return doc_2024, doc_2020, doc_mf_2023


def test_document_matcher_explicit_circular_reference(sample_documents):
    doc_2024, doc_2020, doc_mf_2023 = sample_documents
    candidates = [doc_2020, doc_mf_2023]

    match: PredecessorMatch = DocumentMatcher.find_predecessor(doc_2024, candidates)
    assert match is not None
    assert match.predecessor.document_id == "doc_ia_2020"
    assert match.confidence == "high"
    assert "SEBI/HO/MIRSD/2020/12" in match.match_reason


def test_document_matcher_category_and_title_similarity():
    current_doc = RegulatoryDocument(
        document_id="doc_curr",
        url="https://sebi.gov.in/curr.html",
        title="Master Circular for Compliance by Listed Entities",
        source="SEBI",
        document_type="Master Circular",
        category="Securities Markets",
        published_date="2026-08-01",
        content="Compliance requirements for listed companies.",
        metadata=DocumentMetadata(
            document_type="Master Circular",
            category="Securities Markets",
            published_date="2026-08-01"
        )
    )

    older_doc = RegulatoryDocument(
        document_id="doc_prev",
        url="https://sebi.gov.in/prev.html",
        title="Master Circular for Compliance by Listed Entities",
        source="SEBI",
        document_type="Master Circular",
        category="Securities Markets",
        published_date="2024-06-01",
        content="Prior compliance requirements for listed companies.",
        metadata=DocumentMetadata(
            document_type="Master Circular",
            category="Securities Markets",
            published_date="2024-06-01"
        )
    )

    match = DocumentMatcher.find_predecessor(current_doc, [older_doc])
    assert match is not None
    assert match.predecessor.document_id == "doc_prev"
    assert match.confidence in {"high", "medium"}


def test_document_matcher_no_predecessor_available(sample_documents):
    doc_2024, doc_2020, doc_mf_2023 = sample_documents
    # Only MF candidate provided for IA current document
    match = DocumentMatcher.find_predecessor(doc_2024, [doc_mf_2023])
    assert match is None
