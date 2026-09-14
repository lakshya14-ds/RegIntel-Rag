"""
Unit Tests for Ingestion Checkpointing & Failure Retries (Phase 54.18 & 55.27).
"""

import json
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from app.ingestion.pipeline import IngestionPipeline, REPORTS_DIR
from scraper.sebi_scraper import SEBIScraper, CHECKPOINTS_DIR


def test_scraper_checkpoint_workflow(tmp_path):
    """Verify that crawler checkpoint preserves progress across interruptions."""
    scraper = SEBIScraper(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed"
    )

    run_id = "SEBI_TEST_CHECKPOINT_RESUME"
    processed = [
        "https://sebi.gov.in/doc1.html",
        "https://sebi.gov.in/doc2.html"
    ]

    cp_file = scraper.save_checkpoint(
        run_id=run_id,
        last_url=processed[-1],
        discovered_count=10,
        processed_count=2,
        failed_count=0,
        processed_urls=processed
    )
    assert cp_file.exists()

    loaded = scraper.load_checkpoint(run_id)
    assert loaded["run_id"] == run_id
    assert loaded["last_processed_url"] == "https://sebi.gov.in/doc2.html"
    assert loaded["processed_count"] == 2
    assert len(loaded["processed_urls"]) == 2

    # Cleanup
    if cp_file.exists():
        cp_file.unlink()


def test_retry_failed_loading():
    """Verify that --retry-failed loads failed items from previous run."""
    pipeline = IngestionPipeline()
    test_run_id = "SEBI_FAIL_RUN_001"

    fail_file = REPORTS_DIR / "failed_items.json"
    dummy_fails = [
        {"run_id": test_run_id, "url": "https://sebi.gov.in/failed_doc1.html", "title": "Failed Doc 1", "content": "Now available content"},
        {"run_id": "OTHER_RUN", "url": "https://sebi.gov.in/other.html", "title": "Other", "content": "Text"}
    ]

    with open(fail_file, "w", encoding="utf-8") as f:
        json.dump(dummy_fails, f, indent=2)

    try:
        candidates, dups = pipeline.discover_candidates(source="sebi", retry_run_id=test_run_id)
        assert len(candidates) == 1
        assert candidates[0]["url"] == "https://sebi.gov.in/failed_doc1.html"
    finally:
        if fail_file.exists():
            fail_file.unlink()


def test_pipeline_force_mode():
    """Verify that --force processes documents even if content_hash matches."""
    pipeline = IngestionPipeline()
    url = "https://sebi.gov.in/forced_doc.html"
    content = "Regulatory content to be re-embedded under --force mode."

    candidate = [{"url": url, "title": "Forced Doc", "content": content}]
    pipeline.discover_candidates = MagicMock(return_value=(candidate, 0))
    pipeline._load_stored_document = MagicMock(return_value={
        "document_id": "forced_id",
        "content_hash": pipeline.run.__globals__["compute_content_hash"](content),
        "content": content
    })

    # Dry run with force=False -> UNCHANGED
    summary_normal = pipeline.run(source="sebi", dry_run=True, force=False)
    assert summary_normal.unchanged == 1
    assert summary_normal.changed == 0

    # Dry run with force=True -> CHANGED (reprocessed)
    summary_forced = pipeline.run(source="sebi", dry_run=True, force=True)
    assert summary_forced.changed == 1
    assert summary_forced.unchanged == 0
