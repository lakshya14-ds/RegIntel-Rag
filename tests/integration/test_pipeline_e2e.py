import os
import pytest
from app.config import settings
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.ingestion.chunker import chunk_document
from app.ingestion.chunk_validator import validate_chunks
from app.rag.embeddings import GeminiEmbeddingService, validate_embedding


@pytest.fixture
def sample_sebi_document():
    content = """## Master Circular for Investment Advisers (IAs)

SEBI/HO/MIRSD/MIRSD-PoD-2/P/CIR/2024/56
May 24, 2024

### 1. Introduction and Applicability
This Master Circular consolidates all operational and compliance instructions issued to registered Investment Advisers (IAs) up to May 2024. All Registered Investment Advisers and BASL shall comply with these guidelines.

### 2. Registration and Qualification Norms
An individual investment adviser or a principal officer of a non-individual investment adviser shall have at all times a professional qualification or postgraduate degree in finance, accountancy, or capital markets, along with valid NISM certifications.

### 3. Client Agreement and Fee Mechanism
Investment Advisers shall enter into an investment advisory agreement with clients detailing terms, risk profiling mechanisms, and fee schedules. The fee charged by the Investment Adviser shall not exceed the regulatory caps specified in Regulation 15A.

### 4. Record Keeping and Audit
Every Investment Adviser shall maintain books of accounts, agreements, and advice records for a minimum period of eight years. An annual compliance audit shall be conducted within six months of the end of the financial year."""

    return RegulatoryDocument(
        document_id="sebi_integration_test_doc_001",
        url="https://sebi.gov.in/legal/circulars/may-2024/master-circular-for-investment-advisers-ias-_83556.html",
        title="Master Circular for Investment Advisers (IAs)",
        source="SEBI",
        document_type="Master Circular",
        category="Investment Adviser",
        circular_number="SEBI/HO/MIRSD/MIRSD-PoD-2/P/CIR/2024/56",
        published_date="2024-05-24",
        effective_date=None,
        section=None,
        content=content,
        metadata=DocumentMetadata(
            document_type="Master Circular",
            category="Investment Adviser",
            circular_number="SEBI/HO/MIRSD/MIRSD-PoD-2/P/CIR/2024/56",
            published_date="2024-05-24"
        )
    )


def test_end_to_end_chunk_and_validate(sample_sebi_document):
    # 1. Structure-aware chunking
    chunks = chunk_document(sample_sebi_document)
    assert len(chunks) >= 1
    
    # Check section preservation and deterministic IDs
    assert all(c.chunk_id.startswith("sebi_integration_test_doc_001_chunk_") for c in chunks)
    assert all(c.token_count > 0 for c in chunks)
    assert all(c.source == "SEBI" for c in chunks)
    
    # 2. Chunk Quality Validation
    report = validate_chunks(chunks, original_docs={sample_sebi_document.document_id: sample_sebi_document})
    assert report.status == "PASS"
    assert report.empty_chunks == 0
    assert report.duplicate_chunks == 0


@pytest.mark.skipif(not settings.gemini_api_key, reason="GEMINI_API_KEY is not set")
def test_end_to_end_gemini_embedding_generation(sample_sebi_document):
    # 1. Chunk document
    chunks = chunk_document(sample_sebi_document)
    assert len(chunks) >= 1

    # 2. Generate Gemini Embeddings
    service = GeminiEmbeddingService()
    summary = service.embed_chunks(chunks)

    assert summary.successful == len(chunks)
    assert summary.failed == 0

    # 3. Validate generated vectors
    for c in chunks:
        assert c.embedding is not None
        assert len(c.embedding) == 768
        assert c.embedding_model == "gemini-embedding-001"
        assert c.embedding_dimensions == 768
        assert validate_embedding(c.embedding, expected_dim=768) is True
