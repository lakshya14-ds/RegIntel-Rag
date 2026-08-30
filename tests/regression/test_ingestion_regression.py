"""
Ingestion Idempotency & Hash Regression Tests (Phase 51.14).

Verifies:
1. Re-ingesting identical content yields identical content hashes.
2. Modifying content generates a new content hash.
3. Chunker produces deterministic chunk IDs and hashes.
"""

import hashlib
import pytest
from app.ingestion.cleaner import clean_html, clean_markdown
from app.ingestion.chunker import chunk_document
from app.ingestion.models import RegulatoryDocument, DocumentMetadata


def test_ingestion_content_hash_idempotency():
    raw_html = "<h1>SEBI Circular</h1><p>Investment advisers shall adhere to code of conduct.</p>"
    clean_1 = clean_html(raw_html)
    clean_2 = clean_html(raw_html)

    hash_1 = hashlib.sha256(clean_1.encode("utf-8")).hexdigest()
    hash_2 = hashlib.sha256(clean_2.encode("utf-8")).hexdigest()

    assert clean_1 == clean_2
    assert hash_1 == hash_2


def test_ingestion_content_change_triggers_new_hash():
    raw_v1 = "<p>Fee limit is 2.5 percent.</p>"
    raw_v2 = "<p>Fee limit is 1.5 percent.</p>"

    clean_1 = clean_html(raw_v1)
    clean_2 = clean_html(raw_v2)

    hash_1 = hashlib.sha256(clean_1.encode("utf-8")).hexdigest()
    hash_2 = hashlib.sha256(clean_2.encode("utf-8")).hexdigest()

    assert hash_1 != hash_2


def test_chunking_deterministic_hashes():
    doc = RegulatoryDocument(
        document_id="doc_test_123",
        source="SEBI",
        url="https://sebi.gov.in/test.html",
        title="Test Document",
        content="Section 1. Introduction.\n\nSection 2. Requirements.\n\nSection 3. Penalties.",
        metadata=DocumentMetadata(
            category="Investment Adviser",
            document_type="Circular",
            published_date="2024-01-01"
        )
    )

    chunks_run_1 = chunk_document(doc)
    chunks_run_2 = chunk_document(doc)

    assert len(chunks_run_1) == len(chunks_run_2)
    for c1, c2 in zip(chunks_run_1, chunks_run_2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.content == c2.content
