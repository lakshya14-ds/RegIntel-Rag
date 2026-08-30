"""
Integration Test for End-to-End Incremental Ingestion Workflow (Phases 46 & 47).
"""

import pytest
from unittest.mock import MagicMock
from app.config import settings
from app.ingestion.models import generate_document_id
from app.ingestion.pipeline import IngestionPipeline, compute_content_hash
from app.versioning.timeline import get_document_timeline


def test_incremental_ingestion_and_version_chain_workflow():
    pipeline = IngestionPipeline()

    url = "https://sebi.gov.in/legal/circulars/ia_test.html"
    doc_id = generate_document_id("SEBI", url)

    sec1_text = (
        "## Section 1: Net Worth and Capital Adequacy\n"
        "1.1 Investment advisers shall maintain net worth of Rs 50 Lakhs. "
        "1.2 Compliance with capital adequacy norms is mandatory for all registered entities operating in Indian securities markets. "
        "1.3 Annual CA net worth certificate is required within six months from close of financial year."
    ) * 4

    sec2_text = (
        "## Section 2: Fee Limit and Charging Mechanism\n"
        "2.1 Fee limit is capped at 2.5% of AUA per client family. "
        "2.2 Under the fixed fee model, the fee cannot exceed Rs 1,25,000 per annum. "
        "2.3 Advisers must maintain transparent invoice records for client audits."
    ) * 4

    content_v1 = sec1_text
    content_v2 = f"{sec1_text}\n\n{sec2_text}"

    # Stage 1: Initial Crawl -> NEW
    candidate_v1 = [{
        "url": url,
        "title": "IA Test Circular",
        "content": content_v1
    }]

    pipeline.discover_candidates = MagicMock(return_value=(candidate_v1, 0))
    pipeline._load_stored_document = MagicMock(return_value=None)
    pipeline._load_stored_chunk_hashes = MagicMock(return_value={})

    def mock_embed(chunks):
        for c in chunks:
            c.embedding = [0.10] * settings.embedding_dimension
        return chunks

    pipeline.embedding_service.embed_chunks_batch = MagicMock(side_effect=mock_embed)
    pipeline.repository.save_document = MagicMock()
    pipeline.repository.save_chunks = MagicMock()

    stats_run1 = pipeline.run(source="sebi", dry_run=False)
    assert stats_run1["new"] == 1
    assert stats_run1["unchanged"] == 0
    assert stats_run1["embeddings_generated"] >= 1

    # Stage 2: Identical Crawl -> UNCHANGED (Idempotency)
    pipeline._load_stored_document = MagicMock(return_value={
        "document_id": doc_id,
        "content_hash": compute_content_hash(content_v1),
        "content": content_v1
    })

    stats_run2 = pipeline.run(source="sebi", dry_run=False)
    assert stats_run2["new"] == 0
    assert stats_run2["unchanged"] == 1
    assert stats_run2["embeddings_generated"] == 0

    # Stage 3: Modified Content Crawl -> CHANGED with Embedding Reuse
    candidate_v2 = [{
        "url": url,
        "title": "IA Test Circular Revised",
        "content": content_v2
    }]

    # Chunk 0 has unchanged content
    stored_chunks = {
        f"{doc_id}_chunk_0": {
            "chunk_id": f"{doc_id}_chunk_0",
            "content_hash": compute_content_hash(sec1_text),
            "embedding": [0.05] * settings.embedding_dimension,
            "embedding_model": settings.embedding_model
        }
    }
    pipeline._load_stored_chunk_hashes = MagicMock(return_value=stored_chunks)
    pipeline.discover_candidates = MagicMock(return_value=(candidate_v2, 0))

    stats_run3 = pipeline.run(source="sebi", dry_run=False)
    assert stats_run3["updated"] == 1
    assert stats_run3["embeddings_skipped"] >= 1  # Unchanged chunk reused
    assert stats_run3["embeddings_generated"] >= 1  # Changed/new chunk embedded
