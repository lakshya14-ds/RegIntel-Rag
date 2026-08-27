import pytest
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.ingestion.chunker import (
    RegulatoryChunker,
    ChunkerConfig,
    count_tokens,
    chunk_document,
    chunk_documents,
    build_embedding_text
)


@pytest.fixture
def base_metadata():
    return DocumentMetadata(
        document_type="Circular",
        category="Mutual Funds",
        circular_number="SEBI/HO/IMD/2024/01",
        published_date="2024-05-15"
    )


def test_token_counter():
    text = "Securities and Exchange Board of India regulation circular."
    toks = count_tokens(text)
    assert toks > 5
    assert count_tokens("") == 0


def test_chunking_small_document(base_metadata):
    doc = RegulatoryDocument(
        document_id="doc_small_001",
        url="https://sebi.gov.in/circular_small.html",
        title="Small SEBI Notification",
        source="SEBI",
        content="This is a short single paragraph regulatory notice regarding mutual fund deadlines.",
        metadata=base_metadata
    )
    chunks = chunk_document(doc)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.document_id == "doc_small_001"
    assert chunk.chunk_id == "doc_small_001_chunk_0000"
    assert chunk.chunk_index == 0
    assert chunk.token_count > 0
    assert "mutual fund deadlines" in chunk.content
    assert chunk.embedding is None


def test_chunking_preserves_sections(base_metadata):
    content = """## 1. Background
SEBI issued guidelines regarding Investment Advisers under regulation 2024.

## 2. Eligibility Requirements
All entities seeking registration must maintain minimum net worth of INR 50 Lakhs.

## 3. Effective Date
This circular shall come into force from June 1, 2024."""

    doc = RegulatoryDocument(
        document_id="doc_sections_002",
        url="https://sebi.gov.in/circular_sections.html",
        title="SEBI Master Circular",
        source="SEBI",
        content=content,
        metadata=base_metadata
    )
    chunks = chunk_document(doc)
    assert len(chunks) >= 1
    
    # Check that section titles are captured in section metadata or embedding_text
    sections = [c.section for c in chunks if c.section]
    assert any("Eligibility Requirements" in s or "Background" in s for s in sections)
    
    # Verify embedding text enrichment
    first_chunk = chunks[0]
    assert "Title: SEBI Master Circular" in first_chunk.embedding_text
    assert "Source: SEBI" in first_chunk.embedding_text


def test_chunking_deterministic_ids(base_metadata):
    doc = RegulatoryDocument(
        document_id="doc_det_003",
        url="https://sebi.gov.in/det_test.html",
        title="Deterministic ID Test",
        source="SEBI",
        content="Paragraph one.\n\nParagraph two.\n\nParagraph three.",
        metadata=base_metadata
    )
    chunks1 = chunk_document(doc)
    chunks2 = chunk_document(doc)
    
    assert len(chunks1) == len(chunks2)
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.chunk_index == c2.chunk_index
        assert c1.token_count == c2.token_count


def test_chunking_large_document_respects_max_tokens(base_metadata):
    # Construct a large document with 3000+ words
    long_paragraph = "SEBI regulatory clause requires full compliance with portfolio disclosure norms. " * 300
    content = f"## 1. Major Clause\n\n{long_paragraph}"

    doc = RegulatoryDocument(
        document_id="doc_large_004",
        url="https://sebi.gov.in/large_doc.html",
        title="Large Regulatory Document",
        source="SEBI",
        content=content,
        metadata=base_metadata
    )
    config = ChunkerConfig(target_chunk_tokens=500, max_chunk_tokens=600, min_chunk_tokens=100, overlap_tokens=50)
    chunks = chunk_document(doc, config=config)

    assert len(chunks) > 1
    for c in chunks:
        assert c.token_count <= 650  # Strictly bounded around max_tokens
        assert len(c.content.strip()) > 0
        assert c.chunk_id.startswith("doc_large_004_chunk_")


def test_chunking_no_empty_chunks(base_metadata):
    content = "\n\n\n   \n\n## Header Only\n\n\n\nActual regulatory content goes here.\n\n"
    doc = RegulatoryDocument(
        document_id="doc_empty_check",
        url="https://sebi.gov.in/empty.html",
        title="Empty Check",
        source="SEBI",
        content=content,
        metadata=base_metadata
    )
    chunks = chunk_document(doc)
    for c in chunks:
        assert len(c.content.strip()) > 0
        assert c.token_count > 0


def test_chunk_documents_batch(base_metadata):
    doc1 = RegulatoryDocument(
        document_id="doc_batch_1",
        url="https://sebi.gov.in/doc1.html",
        title="Doc 1",
        source="SEBI",
        content="Content for document 1",
        metadata=base_metadata
    )
    doc2 = RegulatoryDocument(
        document_id="doc_batch_2",
        url="https://sebi.gov.in/doc2.html",
        title="Doc 2",
        source="SEBI",
        content="Content for document 2",
        metadata=base_metadata
    )
    batch_chunks = chunk_documents([doc1, doc2])
    assert len(batch_chunks) >= 2
    doc_ids = {c.document_id for c in batch_chunks}
    assert doc_ids == {"doc_batch_1", "doc_batch_2"}
