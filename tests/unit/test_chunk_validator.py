import pytest
from app.ingestion.models import DocumentChunk, RegulatoryDocument, DocumentMetadata
from app.ingestion.chunk_validator import ChunkValidator, validate_chunks, ChunkQualityReport


@pytest.fixture
def sample_valid_chunks():
    return [
        DocumentChunk(
            chunk_id="doc_valid_chunk_0000",
            document_id="doc_valid",
            chunk_index=0,
            content="Valid regulatory chunk content covering compliance norms.",
            title="SEBI Master Circular",
            section="1. Background",
            source="SEBI",
            document_type="Circular",
            category="Mutual Funds",
            circular_number="SEBI/2024/01",
            published_date="2024-01-01",
            effective_date=None,
            url="https://sebi.gov.in/valid.html",
            token_count=100
        ),
        DocumentChunk(
            chunk_id="doc_valid_chunk_0001",
            document_id="doc_valid",
            chunk_index=1,
            content="Second chunk covering reporting deadlines and fee structures.",
            title="SEBI Master Circular",
            section="2. Reporting",
            source="SEBI",
            document_type="Circular",
            category="Mutual Funds",
            circular_number="SEBI/2024/01",
            published_date="2024-01-01",
            effective_date=None,
            url="https://sebi.gov.in/valid.html",
            token_count=120
        )
    ]


def test_validator_pass(sample_valid_chunks):
    report = validate_chunks(sample_valid_chunks)
    assert report.status == "PASS"
    assert report.total_chunks == 2
    assert report.documents_processed == 1
    assert report.empty_chunks == 0
    assert report.duplicate_chunks == 0
    assert report.avg_tokens_per_chunk == 110.0


def test_validator_duplicate_detection(sample_valid_chunks):
    # Duplicate the first chunk with a new chunk_id
    duplicate_chunk = sample_valid_chunks[0].model_copy(update={"chunk_id": "doc_valid_chunk_9999", "chunk_index": 2})
    all_chunks = sample_valid_chunks + [duplicate_chunk]
    
    report = validate_chunks(all_chunks)
    assert report.total_chunks == 3
    assert report.duplicate_chunks == 1


def test_validator_detects_empty_chunk():
    empty_chunk = DocumentChunk.model_construct(
        chunk_id="doc_bad_chunk_0000",
        document_id="doc_bad",
        chunk_index=0,
        content="   ",
        title="Bad Doc",
        source="SEBI",
        url="https://sebi.gov.in/bad.html",
        token_count=0
    )
    report = validate_chunks([empty_chunk])
    assert report.status == "FAIL"
    assert report.empty_chunks == 1


def test_validator_content_loss_warning(sample_valid_chunks):
    # Original document is huge (1000 tokens), but chunks only account for 220 tokens
    orig_content = "Extensive compliance requirement details across mutual fund operations. " * 150
    orig_doc = RegulatoryDocument(
        document_id="doc_valid",
        url="https://sebi.gov.in/valid.html",
        title="SEBI Master Circular",
        source="SEBI",
        content=orig_content,
        metadata=DocumentMetadata(document_type="Circular", category="Mutual Funds")
    )
    report = validate_chunks(sample_valid_chunks, original_docs={"doc_valid": orig_doc})
    assert report.content_loss_warnings >= 1
    assert report.status in ["WARNING", "FAIL"]
