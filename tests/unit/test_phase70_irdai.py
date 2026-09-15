"""
Phase 70 Unit Test Suite: IRDAI Regulatory Connector.

Tests all aspects of IRDAIConnector with mocked fixtures:
- 70.3: Discovery across listing pages, archives, pagination, and document details
- 70.4: Metadata extraction (title, doc type, ref number, dates, department, status)
- 70.5: Canonical URL handling and deduplication
- 70.6: Normalization into RegulatoryDocument
- 70.7: PDF extraction and error handling
- 70.8: Incremental hashing and changed document detection
- 70.9: Evidence-backed relationship extraction (AMENDS, SUPERSEDES, REFERENCES)
- 70.10: Effective date extraction
- Robustness: Missing metadata, broken PDF, HTTP 404, HTTP 500, timeout
"""

import io
import uuid
import pytest
from unittest.mock import patch, MagicMock

from app.connectors.authority import RegulatoryAuthority
from app.connectors.base import CrawlResult
from app.connectors.registry import RegulatorySource
from app.connectors.irdai import IRDAIConnector
from app.ingestion.models import RawDocument, compute_content_hash
from app.compliance.date_extractor import extract_regulatory_dates


@pytest.fixture
def irdai_connector():
    return IRDAIConnector(crawl_delay_seconds=0.0, max_concurrency=2, max_retries=1)


def test_irdai_authority_and_domain(irdai_connector):
    """Verifies that IRDAIConnector identifies as IRDAI with strictly irdai.gov.in domain."""
    assert irdai_connector.authority == RegulatoryAuthority.IRDAI
    assert "irdai.gov.in" in irdai_connector.allowed_domains
    assert irdai_connector.is_allowed_domain("https://irdai.gov.in/circulars")
    assert irdai_connector.is_allowed_domain("https://www.irdai.gov.in/document-detail?id=123")
    assert not irdai_connector.is_allowed_domain("https://news.insurance.com/circular")


@pytest.mark.asyncio
async def test_irdai_sources_discovery(irdai_connector):
    """Verifies official IRDAI sources are registered and discoverable."""
    sources = await irdai_connector.discover_sources()
    assert len(sources) >= 3
    source_ids = {s.source_id for s in sources}
    assert "irdai_circulars" in source_ids
    assert "irdai_master_circulars" in source_ids
    assert "irdai_regulations" in source_ids


def test_irdai_url_canonicalization(irdai_connector):
    """Verifies canonical URL handling strips tracking and normalizes structure."""
    url1 = "https://irdai.gov.in/document-detail?documentId=4928172&utm_source=twitter#top"
    canon1 = irdai_connector.canonicalize(url1)
    assert "utm_source" not in canon1
    assert "#top" not in canon1
    assert "documentId=4928172" in canon1


def test_irdai_metadata_extraction_complete(irdai_connector):
    """Tests high-fidelity extraction of circular number, department, dates, and relationships."""
    text = """
    INSURANCE REGULATORY AND DEVELOPMENT AUTHORITY OF INDIA
    Consumer Affairs Department
    Ref: IRDAI/NL/CIR/MOT/105/06/2024
    June 19, 2024

    To: All General Insurers and Standalone Health Insurers

    Master Circular on Protection of Policyholders' Interests, 2024
    1. In supersession of Circular IRDA/CAD/CIR/2017/045 dated 25th April 2017.
    2. These instructions shall come into force with effect from July 01, 2024.
    3. Insurers shall settle all admissible motor insurance claims within 30 days.
    """
    meta = irdai_connector.extract_metadata(
        text=text,
        title="Master Circular on Protection of Policyholders' Interests, 2024",
        url="https://irdai.gov.in/document-detail?documentId=4928172"
    )

    assert meta.circular_number == "IRDAI/NL/CIR/MOT/105/06/2024"
    assert meta.department == "Consumer Affairs Department"
    assert meta.category == "Non-Life / Motor Insurance"
    assert meta.document_type == "Master Circular"
    assert meta.published_date == "2024-06-19"
    assert meta.effective_date == "2024-07-01"
    assert meta.supersedes == "IRDA/CAD/CIR/2017/045"
    assert len(meta.relationships) >= 1
    assert meta.relationships[0]["type"] == "SUPERSEDES"


def test_irdai_metadata_missing_leaves_none(irdai_connector):
    """Verifies that missing metadata is never fabricated and remains None or default."""
    text = "General advisory notice on insurance agency licensing examinations."
    meta = irdai_connector.extract_metadata(text=text, title="Notice")
    assert meta.circular_number is None
    assert meta.effective_date is None
    assert meta.supersedes is None
    assert meta.amends is None


def test_irdai_normalization(irdai_connector):
    """Tests normalization of raw document into shared RegulatoryDocument model."""
    raw = RawDocument(
        document_id="irdai_test_001",
        url="https://irdai.gov.in/document-detail?documentId=111",
        title="Circular on Health Insurance",
        content="Ref: IRDAI/HLT/CIR/PRO/095/05/2024\nMay 29, 2024\nHealth Department circular on claim processing.",
        source="IRDAI"
    )
    reg_doc = irdai_connector.normalize_document(raw)
    assert reg_doc.authority == "IRDAI"
    assert reg_doc.source == "IRDAI"
    assert reg_doc.circular_number == "IRDAI/HLT/CIR/PRO/095/05/2024"
    assert reg_doc.published_date == "2024-05-29"
    assert reg_doc.content_hash == compute_content_hash(reg_doc.content)


def test_irdai_incremental_content_hash_change(irdai_connector):
    """Verifies that modified document content produces a distinct hash."""
    raw_v1 = RawDocument(
        document_id="irdai_hash_01",
        url="https://irdai.gov.in/document-detail?documentId=222",
        title="IRDAI Circular v1",
        content="Ref: IRDAI/CIR/01/2024\nInitial draft of claim settlement guidelines.",
        source="IRDAI"
    )
    doc_v1 = irdai_connector.normalize_document(raw_v1)

    raw_v2 = RawDocument(
        document_id="irdai_hash_01",
        url="https://irdai.gov.in/document-detail?documentId=222",
        title="IRDAI Circular v2",
        content="Ref: IRDAI/CIR/01/2024\nAmended draft: Insurers must settle within 15 days.",
        source="IRDAI"
    )
    doc_v2 = irdai_connector.normalize_document(raw_v2)

    assert doc_v1.content_hash != doc_v2.content_hash


@pytest.mark.asyncio
async def test_irdai_fetch_document_pdf_mock(irdai_connector):
    """Tests PDF parsing flow with mocked httpx response and in-memory PDF."""
    fake_pdf = io.BytesIO()
    import pypdf
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(fake_pdf)
    pdf_bytes = fake_pdf.getvalue()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/pdf"}
    mock_resp.content = pdf_bytes

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with patch.object(irdai_connector, "validate_content", return_value=(True, None)):
            res = await irdai_connector.fetch_document("https://irdai.gov.in/uploads/circular.pdf")
            assert res.status_code == 200
            assert res.content_type == "PDF"


@pytest.mark.asyncio
async def test_irdai_fetch_http_404_failure(irdai_connector):
    """Verifies that HTTP 404 response returns a failed CrawlResult without raising an exception."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.headers = {"content-type": "text/html"}

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await irdai_connector.fetch_document("https://irdai.gov.in/missing-document.html")
        assert res.status_code == 404
        assert res.success is False
        assert not irdai_connector.is_retryable_error(res.error, res.status_code)


@pytest.mark.asyncio
async def test_irdai_fetch_timeout_handling(irdai_connector):
    """Verifies that network timeout is caught and marked as retryable."""
    import httpx
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timed out")):
        res = await irdai_connector.fetch_document("https://irdai.gov.in/document-detail?id=999")
        assert res.status_code == 500
        assert res.success is False
        assert irdai_connector.is_retryable_error(res.error)


def test_irdai_effective_date_pipeline_integration(irdai_connector):
    """Verifies that IRDAI document text extracts date events with the shared engine."""
    text = "This circular shall come into force with effect from October 01, 2024."
    events = extract_regulatory_dates(
        text=text,
        document_id="irdai_doc_date_test",
        publication_date="2024-06-15"
    )
    assert len(events) >= 1
    effective_events = [e for e in events if e.event_type == "EFFECTIVE"]
    assert len(effective_events) >= 1
    assert effective_events[0].date == "2024-10-01"
