import pytest
from app.ingestion.cleaner import TextCleaner
from app.ingestion.metadata import MetadataExtractor
from app.ingestion.chunker import DocumentChunker

def test_cleaner_removes_extra_whitespace():
    raw_text = "SEBI    Circular \n\n\n  No. 123   "
    cleaned = TextCleaner.clean_text(raw_text)
    assert cleaned == "SEBI Circular \n\n No. 123"

def test_metadata_extraction():
    text = "Subject: SEBI/HO/CFD/PoD-1/P/CIR/2023/123 dated January 15, 2024"
    circular = MetadataExtractor.extract_circular_number(text)
    assert circular is not None
    assert "SEBI" in circular

def test_document_chunker():
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    sample_text = "This is a sample document for testing the chunker functionality. " * 10
    chunks = chunker.chunk_document(sample_text, metadata={"source": "test", "title": "test_doc"})
    assert len(chunks) > 0
    assert "text" in chunks[0]
    assert "metadata" in chunks[0]
