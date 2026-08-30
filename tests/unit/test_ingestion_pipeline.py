"""
Unit Tests for Ingestion Pipeline Orchestrator (Phase 46).
"""

import pytest
from unittest.mock import MagicMock, patch
from app.ingestion.pipeline import IngestionPipeline, compute_content_hash
from app.ingestion.models import RegulatoryDocument, DocumentChunk, DocumentMetadata


def test_ingestion_classification_dry_run():
    pipeline = IngestionPipeline()

    sample_candidates = [
        {
            "url": "https://sebi.gov.in/legal/circulars/mar-2024/t0-settlement_12345.html",
            "title": "Beta Version of T+0 Settlement",
            "content": "Framework for introduction of Beta version of T+0 settlement cycle."
        },
        {
            "url": "https://sebi.gov.in/legal/circulars/may-2024/ia-guidelines_67890.html",
            "title": "Guidelines for Investment Advisers",
            "content": "Revised regulatory framework for investment advisers."
        }
    ]

    pipeline.discover_candidates = MagicMock(return_value=sample_candidates)
    pipeline._load_stored_document = MagicMock(return_value=None)

    stats = pipeline.run(source="sebi", dry_run=True)
    assert stats["discovered"] == 2
    assert stats["new"] == 2
    assert stats["failed"] == 0
    assert stats["documents_chunked"] == 0  # Dry run doesn't persist/chunk


def test_ingestion_unchanged_detection():
    pipeline = IngestionPipeline()

    content = "Framework for introduction of Beta version of T+0 settlement cycle."
    c_hash = compute_content_hash(content)

    sample_candidates = [
        {
            "url": "https://sebi.gov.in/legal/circulars/mar-2024/t0-settlement_12345.html",
            "title": "Beta Version of T+0 Settlement",
            "content": content
        }
    ]

    pipeline.discover_candidates = MagicMock(return_value=sample_candidates)
    # Existing stored doc has identical hash
    pipeline._load_stored_document = MagicMock(return_value={
        "document_id": "test_doc_123",
        "content_hash": c_hash,
        "content": content
    })

    stats = pipeline.run(source="sebi", dry_run=False)
    assert stats["discovered"] == 1
    assert stats["unchanged"] == 1
    assert stats["new"] == 0
    assert stats["updated"] == 0


def test_ingestion_changed_detection_and_embedding_reuse():
    pipeline = IngestionPipeline()

    old_content = "Old regulatory content."
    new_content = "Revised regulatory content with amendments."

    sample_candidates = [
        {
            "url": "https://sebi.gov.in/legal/circulars/mar-2024/doc_1.html",
            "title": "Amended Circular",
            "content": new_content
        }
    ]

    pipeline.discover_candidates = MagicMock(return_value=sample_candidates)
    pipeline._load_stored_document = MagicMock(return_value={
        "document_id": "doc_1",
        "content_hash": compute_content_hash(old_content),
        "content": old_content
    })

    pipeline.embedding_service.embed_chunks_batch = MagicMock(side_effect=lambda chunks: chunks)
    pipeline.repository.save_document = MagicMock()
    pipeline.repository.save_chunks = MagicMock()

    stats = pipeline.run(source="sebi", dry_run=False)
    assert stats["discovered"] == 1
    assert stats["updated"] == 1
    assert stats["new"] == 0
    assert stats["unchanged"] == 0


def test_ingestion_failure_isolation():
    pipeline = IngestionPipeline()

    invalid_candidates = [
        {"url": "", "title": "Missing URL", "content": "Some text"},
        {"url": "https://sebi.gov.in/doc.html", "title": "Missing Content", "content": ""}
    ]

    pipeline.discover_candidates = MagicMock(return_value=invalid_candidates)
    stats = pipeline.run(source="sebi", dry_run=False)

    assert stats["discovered"] == 2
    assert stats["failed"] == 2
    assert len(stats["failures"]) == 2
