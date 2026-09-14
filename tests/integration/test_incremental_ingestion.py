"""
Integration Test for End-to-End Incremental Ingestion Workflow (Phase 55.36).

Validates:
- 10-Document Corpus Ingestion
- Run 1: 10 NEW documents -> 10 chunked, all embeddings created
- Run 2: 10 UNCHANGED documents -> 0 chunked, 0 embeddings created (100% IDEMPOTENCY)
- Run 3: 1 CHANGED document, 9 UNCHANGED documents -> only changed chunks embedded, unchanged chunks reused
"""

import pytest
from unittest.mock import MagicMock
from app.config import settings
from app.ingestion.models import generate_document_id
from app.ingestion.pipeline import IngestionPipeline, compute_content_hash


def test_incremental_ingestion_and_version_chain_workflow():
    """Validates 3-stage lifecycle for an individual document: NEW -> UNCHANGED -> CHANGED."""
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


def test_ten_document_corpus_multi_run_idempotency_and_delta():
    """
    Phase 55.36 Specification Scenario:
    Corpus: 10 documents
    Run 1: 10 NEW
    Run 2: 10 UNCHANGED (0 embeddings generated)
    Run 3: 1 CHANGED, 9 UNCHANGED (only changed chunks embedded)
    """
    pipeline = IngestionPipeline()

    # Generate 10 distinct document candidates
    corpus = []
    for i in range(1, 11):
        body = (
            f"## Section {i}: Compliance Framework for Category {i}\n"
            f"Mandatory requirement for regulated entities under circular index {i}. "
            f"All registered market participants shall maintain compliance records for verification. "
            f"Failure to adhere to these provisions will attract regulatory enforcement and penalty actions under the SEBI Act. "
        ) * 8
        corpus.append({
            "url": f"https://sebi.gov.in/legal/circulars/doc_{i}.html",
            "title": f"Regulatory Notice {i}",
            "content": body
        })

    mock_db = {}
    mock_chunk_db = {}

    def mock_load_doc(doc_id):
        return mock_db.get(doc_id)

    def mock_load_chunks(doc_id):
        return {c["chunk_id"]: c for c in mock_chunk_db.get(doc_id, [])}

    def mock_save_doc(doc):
        mock_db[doc.document_id] = {
            "document_id": doc.document_id,
            "content_hash": doc.content_hash,
            "content": doc.content
        }

    def mock_save_chunks(chunks):
        if chunks:
            did = chunks[0].document_id
            mock_chunk_db[did] = [c.model_dump() for c in chunks]

    pipeline._load_stored_document = MagicMock(side_effect=mock_load_doc)
    pipeline._load_stored_chunk_hashes = MagicMock(side_effect=mock_load_chunks)
    pipeline.repository.save_document = MagicMock(side_effect=mock_save_doc)
    pipeline.repository.save_chunks = MagicMock(side_effect=mock_save_chunks)

    def mock_embed(chunks):
        for c in chunks:
            c.embedding = [0.12] * settings.embedding_dimension
        return chunks

    pipeline.embedding_service.embed_chunks_batch = MagicMock(side_effect=mock_embed)

    # -------------------------------------------------------------
    # RUN 1: 10 NEW Documents
    # -------------------------------------------------------------
    pipeline.discover_candidates = MagicMock(return_value=(corpus, 0))
    run1 = pipeline.run(source="sebi", dry_run=False)

    assert run1.new == 10
    assert run1.changed == 0
    assert run1.unchanged == 0
    assert run1.embeddings_created >= 10
    assert run1.embeddings_reused == 0

    # -------------------------------------------------------------
    # RUN 2: 10 UNCHANGED Documents (100% Idempotency)
    # -------------------------------------------------------------
    pipeline.discover_candidates = MagicMock(return_value=(corpus, 0))
    run2 = pipeline.run(source="sebi", dry_run=False)

    assert run2.new == 0
    assert run2.changed == 0
    assert run2.unchanged == 10
    assert run2.embeddings_created == 0  # Zero embedding calls!
    assert run2.embeddings_reused == 0

    # -------------------------------------------------------------
    # RUN 3: 1 CHANGED, 9 UNCHANGED (Controlled Section Delta)
    # -------------------------------------------------------------
    modified_corpus = [dict(d) for d in corpus]
    # Modify document 1 by appending a new section exceeding min_chunk_tokens
    new_sec_body = (
        "## Section 1B: Enhanced Risk Surveillance and Mandatory Client Disclosures\n"
        "1. All registered investment entities shall implement algorithmic risk profiling systems. "
        "2. Periodic reports on portfolio concentration risks shall be submitted to the supervisory body. "
        "3. Any breach of risk exposure caps shall be rectified within 3 business days of notification. "
        "4. Non-compliance with these surveillance limits shall trigger administrative inspections. "
    ) * 8
    modified_corpus[0]["content"] += f"\n\n{new_sec_body}"

    pipeline.discover_candidates = MagicMock(return_value=(modified_corpus, 0))
    run3 = pipeline.run(source="sebi", dry_run=False)

    assert run3.new == 0
    assert run3.changed == 1
    assert run3.unchanged == 9
    assert run3.embeddings_created >= 1  # Only the modified document was chunked/embedded
    assert run3.embeddings_reused >= 1   # Unchanged chunk from doc 1 reused
