"""
Unit Tests for Embedding Reuse on Unchanged Chunks (Phase 46).
"""

import pytest
from unittest.mock import MagicMock
from app.config import settings
from app.ingestion.models import generate_document_id
from app.ingestion.pipeline import IngestionPipeline, compute_content_hash


def test_embedding_reuse_on_unchanged_chunks():
    pipeline = IngestionPipeline()

    url = "https://sebi.gov.in/circular_amended.html"
    doc_id = generate_document_id("SEBI", url)

    # Realistic sections exceeding min_chunk_tokens (150 tokens)
    sec1_text = (
        "## Section 1: Capital Adequacy and Net Worth Framework\n"
        "1.1 All registered investment advisers shall continuously maintain a minimum net worth of Rs 50 Lakhs for non-individuals "
        "and Rs 5 Lakhs for individuals throughout their operational tenure. "
        "1.2 The net worth certificate shall be issued by a practicing Chartered Accountant and submitted annually within six months "
        "of the close of the financial year to the designated supervisory body. "
        "1.3 Failure to maintain required capital adequacy shall attract regulatory penalties under the SEBI Act 1992."
    ) * 4

    sec2_text = (
        "## Section 2: Fee Cap and Client Remuneration Framework\n"
        "2.1 Investment advisers shall charge fees strictly based on either an Assets Under Advice (AUA) model or a fixed fee model. "
        "2.2 The maximum fee under the AUA model shall not exceed 2.5 percent per annum of the client portfolio. "
        "2.3 The maximum fee under the fixed fee model shall not exceed Rs 1,25,000 per annum per family across all advisory accounts. "
        "2.4 Advisers shall not receive any indirect remuneration, commission, or referral fee from product providers."
    ) * 4

    # Candidate with modified content (Section 1 unchanged, Section 2 added)
    sample_candidate = [{
        "url": url,
        "title": "Amended Circular",
        "content": f"{sec1_text}\n\n{sec2_text}"
    }]

    pipeline.discover_candidates = MagicMock(return_value=(sample_candidate, 0))
    pipeline._load_stored_document = MagicMock(return_value={
        "document_id": doc_id,
        "content_hash": "old_different_hash",
        "content": sec1_text
    })

    # Mock chunker returning 2 chunks for this document
    def mock_embed(chunks):
        for c in chunks:
            c.embedding = [0.10] * settings.embedding_dimension
        return chunks

    pipeline.embedding_service.embed_chunks_batch = MagicMock(side_effect=mock_embed)
    pipeline.repository.save_document = MagicMock()
    pipeline.repository.save_chunks = MagicMock()

    # Pre-populate stored chunk hash cache for the first chunk
    chunk0_hash = compute_content_hash(sec1_text)
    stored_chunks = {
        f"{doc_id}_chunk_0": {
            "chunk_id": f"{doc_id}_chunk_0",
            "content_hash": chunk0_hash,
            "embedding": [0.05] * settings.embedding_dimension,
            "embedding_model": settings.embedding_model
        }
    }
    pipeline._load_stored_chunk_hashes = MagicMock(return_value=stored_chunks)

    stats = pipeline.run(source="sebi", dry_run=False)

    assert stats["updated"] == 1
    assert stats["embeddings_generated"] >= 1
    assert stats["embeddings_skipped"] >= 1
