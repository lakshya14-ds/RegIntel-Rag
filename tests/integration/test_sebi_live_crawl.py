"""
Optional Live Crawl Test for SEBI Official Portal (Phase 54.29).

Only runs when environment variable RUN_SEBI_LIVE_CRAWL=true.
Crawls a very small number of official pages to verify network and parser readiness
without impacting normal CI or external server availability.
"""

import os
import pytest
from scraper.sebi_scraper import SEBIScraper


@pytest.mark.asyncio
async def test_sebi_live_crawl_small_batch(tmp_path):
    """Executes a bounded live crawl against 1 official SEBI source page."""
    if os.environ.get("RUN_SEBI_LIVE_CRAWL", "").lower() not in ("true", "1", "yes"):
        pytest.skip("RUN_SEBI_LIVE_CRAWL is not set to true. Skipping live SEBI crawler test.")

    scraper = SEBIScraper(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        crawl_delay_seconds=1.5,
        max_concurrency=1,
        max_retries=2
    )

    test_url = "https://www.sebi.gov.in/legal/circulars/may-2024/master-circular-for-investment-advisers-ias-_83556.html"
    result = await scraper.fetch_document(test_url)

    assert result is not None
    assert result.url == test_url
    if result.success:
        assert result.content is not None
        assert len(result.content) > 50
        assert result.content_type in ("HTML", "PDF")
    else:
        # If external server is down or blocked, ensure structured error is captured
        assert result.error is not None
