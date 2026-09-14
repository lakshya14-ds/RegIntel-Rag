"""
Unit Tests for Production-Grade SEBI Scraper (Phase 54).
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from scraper.sebi_scraper import SEBIScraper, CHECKPOINTS_DIR
from scraper.base_scraper import CrawlResult


@pytest.fixture
def scraper(tmp_path):
    """Initializes a test SEBIScraper with temporary directories."""
    return SEBIScraper(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        crawl_delay_seconds=0.01,
        max_concurrency=2,
        max_retries=2
    )


def test_domain_restriction(scraper):
    """Verify that only sebi.gov.in domains are permitted."""
    assert scraper.is_allowed_domain("https://www.sebi.gov.in/legal/circulars/doc.html") is True
    assert scraper.is_allowed_domain("https://sebi.gov.in/doc.pdf") is True
    assert scraper.is_allowed_domain("https://evil.com/doc.html") is False
    assert scraper.is_allowed_domain("https://google.com") is False
    assert scraper.is_allowed_domain("invalid-url") is False


def test_document_link_filtering(scraper):
    """Verify distinction between document links and navigation/irrelevant links."""
    # Valid regulatory links
    assert scraper.is_document_link("https://www.sebi.gov.in/legal/circulars/may-2024/doc_123.html") is True
    assert scraper.is_document_link("https://www.sebi.gov.in/legal/master-circulars/jun-2024/doc_456.html") is True
    assert scraper.is_document_link("https://www.sebi.gov.in/reports-and-statistics/report.html") is True
    assert scraper.is_document_link("https://www.sebi.gov.in/files/circular.pdf") is True

    # Irrelevant/navigation links
    assert scraper.is_document_link("https://www.sebi.gov.in/login") is False
    assert scraper.is_document_link("https://www.sebi.gov.in/search?q=query") is False
    assert scraper.is_document_link("https://www.sebi.gov.in/feedback") is False
    assert scraper.is_document_link("javascript:void(0)") is False
    assert scraper.is_document_link("mailto:info@sebi.gov.in") is False


def test_document_type_classification(scraper):
    """Verify classification into HTML, PDF, and UNSUPPORTED."""
    assert scraper.classify_document_type("https://www.sebi.gov.in/circular.html") == "HTML"
    assert scraper.classify_document_type("https://www.sebi.gov.in/circular.pdf") == "PDF"
    assert scraper.classify_document_type("https://www.sebi.gov.in/archive.zip") == "UNSUPPORTED"
    assert scraper.classify_document_type("https://www.sebi.gov.in/installer.exe") == "UNSUPPORTED"
    assert scraper.classify_document_type("https://www.sebi.gov.in/data.xlsx") == "UNSUPPORTED"
    assert scraper.classify_document_type("https://www.sebi.gov.in/page", "application/pdf") == "PDF"


def test_retry_classification(scraper):
    """Verify distinction between retryable and non-retryable errors."""
    # Non-retryable
    assert scraper.is_retryable_error("404 Not Found", status_code=404) is False
    assert scraper.is_retryable_error("Access Denied", status_code=403) is False
    assert scraper.is_retryable_error("Unsupported document format", status_code=415) is False
    assert scraper.is_retryable_error("Invalid URL format") is False

    # Retryable
    assert scraper.is_retryable_error("Connection timeout", status_code=504) is True
    assert scraper.is_retryable_error("502 Bad Gateway", status_code=502) is True
    assert scraper.is_retryable_error("Server disconnected", status_code=500) is True


def test_content_validation(scraper):
    """Verify content validation rules."""
    # Blank / empty
    is_valid, err = scraper.validate_content("")
    assert is_valid is False
    assert "empty or blank" in err

    # Below threshold (< 50 chars)
    is_valid, err = scraper.validate_content("Too short circular text")
    assert is_valid is False
    assert "below minimum threshold" in err

    # Access Denied
    is_valid, err = scraper.validate_content("Access Denied: You do not have permission to view this regulatory resource on the server.")
    assert is_valid is False
    assert "Access Denied" in err

    # Valid regulatory content
    valid_text = (
        "Securities and Exchange Board of India (SEBI) circular regarding master framework "
        "for mutual funds compliance and risk surveillance reporting requirements."
    )
    is_valid, err = scraper.validate_content(valid_text)
    assert is_valid is True
    assert err is None


def test_checkpoint_save_and_load(scraper, tmp_path):
    """Verify checkpoint save, load, and resumption state."""
    run_id = "SEBI_TEST_CHECKPOINT_001"
    processed_urls = ["https://www.sebi.gov.in/legal/circulars/doc1.html"]
    
    cp_path = scraper.save_checkpoint(
        run_id=run_id,
        last_url=processed_urls[0],
        discovered_count=10,
        processed_count=1,
        failed_count=0,
        processed_urls=processed_urls
    )
    assert cp_path.exists()

    loaded = scraper.load_checkpoint(run_id)
    assert loaded is not None
    assert loaded["run_id"] == run_id
    assert loaded["last_processed_url"] == processed_urls[0]
    assert loaded["processed_count"] == 1
    assert loaded["processed_urls"] == processed_urls

    # Cleanup test checkpoint
    if cp_path.exists():
        cp_path.unlink()


@pytest.mark.asyncio
async def test_discover_documents_mocked(scraper):
    """Verify discovery flow with mocked crawler returning HTML containing links."""
    sample_html = """
    <html>
      <body>
        <a href="/legal/circulars/may-2024/doc1_83556.html">Circular 1</a>
        <a href="/legal/master-circulars/jun-2024/doc2_84439.html">Master Circular 2</a>
        <a href="/login">Login</a>
        <a href="/archive.zip">Archive</a>
        <a href="https://external.com/legal/circulars/doc3.html">External</a>
      </body>
    </html>
    """

    mock_crawler = AsyncMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.html = sample_html
    mock_crawler.arun.return_value = mock_result

    report = await scraper.discover_documents(
        sources=None,
        max_pages=1,
        crawler=mock_crawler,
        run_id="SEBI_TEST_DISCOVER"
    )

    assert report["run_id"] == "SEBI_TEST_DISCOVER"
    assert report["unique_urls"] > 0
    urls = report["urls"]
    # Curated and discovered URLs must be present
    assert any("doc1_83556.html" in u for u in urls)
    assert any("doc2_84439.html" in u for u in urls)
    # External, login, zip should NOT be in valid document URLs
    assert not any("external.com" in u for u in urls)
    assert not any("login" in u for u in urls)
    assert not any("archive.zip" in u for u in urls)
