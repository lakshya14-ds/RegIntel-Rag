"""
Integration Tests for Automated Ingestion Pipeline (Phase 30).
"""

import pytest
from unittest.mock import MagicMock

from app.ingestion.pipeline import IngestionPipeline, compute_content_hash


def test_compute_content_hash():
    text1 = "This is a regulatory circular content."
    text2 = "  This   is a regulatory    circular content.  "
    assert compute_content_hash(text1) == compute_content_hash(text2)


def test_ingestion_pipeline_dry_run():
    pipeline = IngestionPipeline()
    stats = pipeline.run(source="sebi", limit=5, dry_run=True)

    assert "discovered" in stats
    assert "new" in stats
    assert "unchanged" in stats
    assert stats["embeddings_generated"] == 0  # In dry run, zero embeddings generated
    assert stats["discovered"] >= 0
