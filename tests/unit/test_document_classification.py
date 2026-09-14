"""
Unit Tests for Document Classification & Hash Tracking (Phase 55.2 & 55.34).

Verifies exact classification states:
- NEW
- UNCHANGED
- CHANGED
- DUPLICATE
- FAILED
- UNSUPPORTED
"""

import pytest
from unittest.mock import MagicMock

from app.ingestion.pipeline import IngestionPipeline, compute_content_hash
from app.ingestion.models import generate_document_id
from scraper.base_scraper import BaseScraper


def test_classify_new_document():
    """Verify that an unrecorded document URL is classified as NEW."""
    pipeline = IngestionPipeline()
    url = "https://sebi.gov.in/legal/circulars/doc_brand_new.html"
    doc_id = generate_document_id("SEBI", url)

    candidate = [{"url": url, "title": "New Circular", "content": "Brand new circular content for FY2026."}]
    pipeline.discover_candidates = MagicMock(return_value=(candidate, 0))
    pipeline._load_stored_document = MagicMock(return_value=None)

    summary = pipeline.run(source="sebi", dry_run=True)
    assert summary.new == 1
    assert summary.unchanged == 0
    assert summary.changed == 0
    assert summary.failed == 0


def test_classify_unchanged_document():
    """Verify that a document with matching content_hash is classified as UNCHANGED."""
    pipeline = IngestionPipeline()
    url = "https://sebi.gov.in/legal/circulars/doc_existing.html"
    content = "Static regulatory provisions that have not changed."
    c_hash = compute_content_hash(content)

    candidate = [{"url": url, "title": "Existing Circular", "content": content}]
    pipeline.discover_candidates = MagicMock(return_value=(candidate, 0))
    pipeline._load_stored_document = MagicMock(return_value={
        "document_id": generate_document_id("SEBI", url),
        "content_hash": c_hash,
        "content": content
    })

    summary = pipeline.run(source="sebi", dry_run=True)
    assert summary.unchanged == 1
    assert summary.new == 0
    assert summary.changed == 0


def test_classify_changed_document():
    """Verify that a document with different content_hash is classified as CHANGED."""
    pipeline = IngestionPipeline()
    url = "https://sebi.gov.in/legal/circulars/doc_amended.html"
    old_content = "Old requirements: Net worth of Rs 25 Lakhs required."
    new_content = "Amended requirements: Net worth of Rs 50 Lakhs required."

    candidate = [{"url": url, "title": "Amended Circular", "content": new_content}]
    pipeline.discover_candidates = MagicMock(return_value=(candidate, 0))
    pipeline._load_stored_document = MagicMock(return_value={
        "document_id": generate_document_id("SEBI", url),
        "content_hash": compute_content_hash(old_content),
        "content": old_content
    })

    summary = pipeline.run(source="sebi", dry_run=True)
    assert summary.changed == 1
    assert summary.new == 0
    assert summary.unchanged == 0


def test_classify_duplicates_during_discovery(tmp_path):
    """Verify that duplicate URLs are detected and counted during discovery."""
    pipeline = IngestionPipeline()
    # Create raw candidates with intentional duplicate canonical URLs
    url = "https://sebi.gov.in/legal/circulars/doc_dup.html"
    raw_candidates = [
        {"url": url, "content": "Body text 1"},
        {"url": f"{url}?utm_source=twitter", "content": "Body text 1 with tracking"},
        {"url": f"{url}#section2", "content": "Body text 1 with anchor"}
    ]

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    import json
    with open(raw_dir / "test_raw.json", "w", encoding="utf-8") as f:
        json.dump(raw_candidates, f)

    from app.config import settings
    orig_raw = settings.raw_data_dir
    try:
        settings.raw_data_dir = raw_dir
        unique_cands, dup_count = pipeline.discover_candidates(source="other")
        assert len(unique_cands) == 1
        assert dup_count == 2
    finally:
        settings.raw_data_dir = orig_raw


def test_classify_failed_empty_content():
    """Verify that empty documents are classified as FAILED with audit reason."""
    pipeline = IngestionPipeline()
    invalid_cands = [
        {"url": "", "title": "Empty URL", "content": "Some text"},
        {"url": "https://sebi.gov.in/empty.html", "title": "Empty Content", "content": ""}
    ]
    pipeline.discover_candidates = MagicMock(return_value=(invalid_cands, 0))

    summary = pipeline.run(source="sebi", dry_run=False)
    assert summary.failed == 2
    assert len(summary.failures) == 2


def test_classify_unsupported_document():
    """Verify that non-regulatory or binary files are classified as UNSUPPORTED."""
    scraper = BaseScraper(source_name="SEBI")
    assert scraper.classify_document_type("https://sebi.gov.in/data.zip") == "UNSUPPORTED"
    assert scraper.classify_document_type("https://sebi.gov.in/app.exe") == "UNSUPPORTED"
    assert scraper.classify_document_type("https://sebi.gov.in/video.mp4") == "UNSUPPORTED"
    assert scraper.classify_document_type("https://sebi.gov.in/circular.pdf") == "PDF"
    assert scraper.classify_document_type("https://sebi.gov.in/circular.html") == "HTML"
