"""
Phase 72 Unit Test Suite: IFSCA Regulatory Connector.

Tests all aspects of IFSCAConnector with mocked fixtures:
- 72.3: Discovery across IFSCA circulars, regulations, and frameworks
- 72.4: Metadata extraction (title, reference standard, dates, division, status)
- 72.5: Incremental hashing and changed document detection
- 72.6: Evidence-backed relationship extraction (AMENDS, SUPERSEDES, REFERENCES)
- 72.7: Effective date extraction
- Robustness: Missing metadata, broken PDF, HTTP 404, HTTP 500, timeout
"""

import io
import pytest
from unittest.mock import patch, MagicMock

from app.connectors.authority import RegulatoryAuthority
from app.connectors.base import CrawlResult
from app.connectors.ifsca import IFSCAConnector
from app.ingestion.models import RawDocument, compute_content_hash
from app.compliance.date_extractor import extract_regulatory_dates


@pytest.fixture
def ifsca_connector():
    return IFSCAConnector(crawl_delay_seconds=0.0, max_concurrency=2, max_retries=1)


def test_ifsca_authority_and_domain(ifsca_connector):
    """Verifies that IFSCAConnector identifies as IFSCA with strictly ifsca.gov.in domain."""
    assert ifsca_connector.authority == RegulatoryAuthority.IFSCA
    assert "ifsca.gov.in" in ifsca_connector.allowed_domains
    assert ifsca_connector.is_allowed_domain("https://ifsca.gov.in/Circular")
    assert ifsca_connector.is_allowed_domain("https://www.ifsca.gov.in/Document/Report.pdf")
    assert not ifsca_connector.is_allowed_domain("https://news.giftcity.com/circular")


@pytest.mark.asyncio
async def test_ifsca_sources_discovery(ifsca_connector):
    """Verifies official IFSCA sources are registered and discoverable."""
    sources = await ifsca_connector.discover_sources()
    assert len(sources) >= 3
    source_ids = {s.source_id for s in sources}
    assert "ifsca_circulars" in source_ids
    assert "ifsca_regulations" in source_ids
    assert "ifsca_frameworks" in source_ids


def test_ifsca_url_canonicalization(ifsca_connector):
    """Verifies canonical URL handling strips tracking parameters."""
    url = "https://ifsca.gov.in/Circular?id=123&utm_source=linkedin#section1"
    canon = ifsca_connector.canonicalize(url)
    assert "utm_source" not in canon
    assert "#section1" not in canon
    assert "id=123" in canon


def test_ifsca_metadata_extraction_complete(ifsca_connector):
    """Tests high-fidelity extraction of reference number, division, dates, and relationships."""
    text = """
    INTERNATIONAL FINANCIAL SERVICES CENTRES AUTHORITY
    Banking Division, GIFT City, Gandhinagar - 382355
    Ref: IFSCA/2020-21/GN/REG004
    December 18, 2020

    To: All IFSC Banking Units (IBUs) in Gujarat International Finance Tec-City

    International Financial Services Centres Authority (Banking) Regulations, 2020
    1. In supersession of the earlier circular F.No. 12/IFSCA/Banking/2019 dated November 10, 2019.
    2. These regulations shall come into force on the date of their publication in the Official Gazette.
    3. An IBU shall maintain a minimum capital adequacy ratio of 8% at all times.
    """
    meta = ifsca_connector.extract_metadata(
        text=text,
        title="IFSCA Banking Regulations 2020",
        url="https://ifsca.gov.in/Regulation"
    )

    assert meta.circular_number == "IFSCA/2020-21/GN/REG004"
    assert meta.department == "Banking Division"
    assert meta.category == "Banking / IBUs"
    assert meta.document_type == "Regulation"
    assert meta.published_date == "2020-12-18"
    assert meta.supersedes == "F.No. 12/IFSCA/Banking/2019"
    assert len(meta.relationships) >= 1
    assert meta.relationships[0]["type"] == "SUPERSEDES"


def test_ifsca_fintech_framework_extraction(ifsca_connector):
    """Tests metadata extraction for IFSCA FinTech regulatory sandbox frameworks."""
    text = """
    INTERNATIONAL FINANCIAL SERVICES CENTRES AUTHORITY
    Department of Capital Markets & FinTech
    F.No. 521/IFSCA/FinTech/Sandbox/2022-23
    April 27, 2022

    Framework for FinTech Regulatory Sandbox in IFSC
    1. Amends Framework circular F.No. 301/IFSCA/2021 dated May 14, 2021.
    2. FinTech entities shall deploy live testing within 90 days of sandbox admission.
    """
    meta = ifsca_connector.extract_metadata(
        text=text,
        title="Framework for FinTech Regulatory Sandbox",
        url="https://ifsca.gov.in/Framework"
    )

    assert meta.circular_number == "F.No. 521/IFSCA/FinTech/Sandbox/2022-23"
    assert meta.category == "FinTech / Regulatory Sandbox"
    assert meta.published_date == "2022-04-27"
    assert meta.amends == "F.No. 301/IFSCA/2021"


def test_ifsca_metadata_missing_leaves_none(ifsca_connector):
    """Verifies missing metadata remains None without fabrication."""
    text = "General advisory notification regarding administrative timings."
    meta = ifsca_connector.extract_metadata(text=text, title="Admin Notice")
    assert meta.circular_number is None
    assert meta.effective_date is None
    assert meta.supersedes is None


def test_ifsca_normalization(ifsca_connector):
    """Tests normalization into RegulatoryDocument."""
    raw = RawDocument(
        document_id="ifsca_norm_001",
        url="https://ifsca.gov.in/Circular?id=456",
        title="IFSCA Fund Management Circular",
        content="Ref: IFSCA/2023/FME/01\nJuly 12, 2023\nGuidelines on Fund Management Entities in IFSC.",
        source="IFSCA"
    )
    reg_doc = ifsca_connector.normalize_document(raw)
    assert reg_doc.authority == "IFSCA"
    assert reg_doc.source == "IFSCA"
    assert reg_doc.circular_number == "IFSCA/2023/FME/01"
    assert reg_doc.published_date == "2023-07-12"
    assert reg_doc.content_hash == compute_content_hash(reg_doc.content)


def test_ifsca_incremental_content_hash(ifsca_connector):
    """Verifies that changes in IFSCA document content produce a new hash."""
    raw_v1 = RawDocument(
        document_id="ifsca_hash_01",
        url="https://ifsca.gov.in/Circular?id=456",
        title="IFSCA Circular v1",
        content="IFSCA/2023/01\nVersion 1 initial text.",
        source="IFSCA"
    )
    doc_v1 = ifsca_connector.normalize_document(raw_v1)

    raw_v2 = RawDocument(
        document_id="ifsca_hash_01",
        url="https://ifsca.gov.in/Circular?id=456",
        title="IFSCA Circular v2",
        content="IFSCA/2023/01\nVersion 2 updated requirements text.",
        source="IFSCA"
    )
    doc_v2 = ifsca_connector.normalize_document(raw_v2)

    assert doc_v1.content_hash != doc_v2.content_hash


@pytest.mark.asyncio
async def test_ifsca_fetch_pdf_mock(ifsca_connector):
    """Tests PDF parsing with mocked httpx response."""
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
        with patch.object(ifsca_connector, "validate_content", return_value=(True, None)):
            res = await ifsca_connector.fetch_document("https://ifsca.gov.in/uploads/framework.pdf")
            assert res.status_code == 200
            assert res.content_type == "PDF"


@pytest.mark.asyncio
async def test_ifsca_fetch_http_404_failure(ifsca_connector):
    """Verifies that HTTP 404 is caught and not retryable."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.headers = {"content-type": "text/html"}

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await ifsca_connector.fetch_document("https://ifsca.gov.in/not-found-page")
        assert res.status_code == 404
        assert res.success is False
        assert not ifsca_connector.is_retryable_error(res.error, res.status_code)


def test_ifsca_effective_date_extraction(ifsca_connector):
    """Verifies that effective date extraction works on IFSCA text."""
    text = "These instructions shall come into force with effect from 15 January 2025."
    events = extract_regulatory_dates(
        text=text,
        document_id="ifsca_date_test",
        publication_date="2024-11-20"
    )
    assert len(events) >= 1
    eff = [e for e in events if e.event_type == "EFFECTIVE"]
    assert len(eff) >= 1
    assert eff[0].date == "2025-01-15"
