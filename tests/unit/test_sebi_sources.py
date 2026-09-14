"""
Unit Tests for SEBI Source Configuration (Phase 54.1 & 54.2).
"""

import pytest
from scraper.sebi_sources import (
    SEBI_SOURCES,
    SebiSourceConfig,
    get_active_sources,
    get_listing_sources,
    get_curated_documents,
    get_seed_urls
)


def test_sebi_sources_structure():
    """Verify that SEBI_SOURCES contains structured SebiSourceConfig objects."""
    assert len(SEBI_SOURCES) >= 2
    for source in SEBI_SOURCES:
        assert isinstance(source, SebiSourceConfig)
        assert source.source_name
        assert source.source_url.startswith("https://www.sebi.gov.in")
        assert source.source_type in ["Listing", "CuratedDocument"]
        assert source.expected_document_type in [
            "Circular", "Master Circular", "Regulation", "Amendment", "Consultation Paper"
        ]
        assert isinstance(source.enabled, bool)
        assert source.max_pages >= 1


def test_get_active_sources():
    """Verify active sources filter only enabled sources."""
    active = get_active_sources()
    assert len(active) >= 2
    assert all(s.enabled for s in active)


def test_get_listing_sources():
    """Verify listing sources contain the official listing endpoints."""
    listing_sources = get_listing_sources()
    assert len(listing_sources) >= 2
    urls = [s.source_url for s in listing_sources]
    assert any("smid=0" in u for u in urls)  # Circulars
    assert any("smid=1" in u for u in urls)  # Master circulars


def test_curated_documents_seed():
    """Verify curated documents have required fields and non-hallucinated URLs."""
    curated = get_curated_documents()
    assert len(curated) >= 15
    for doc in curated:
        assert "url" in doc
        assert doc["url"].startswith("https://www.sebi.gov.in/legal/circulars/")
        assert "title" in doc
        assert "expected_category" in doc

    seed_urls = get_seed_urls()
    assert len(seed_urls) == len(curated)
    assert all(u.startswith("https://") for u in seed_urls)
