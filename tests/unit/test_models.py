import pytest
from pydantic import ValidationError
from app.ingestion.models import (
    RawDocument,
    RegulatoryDocument,
    DocumentMetadata,
    DocumentChunk,
    to_mongo,
    from_mongo
)

def test_raw_document_valid():
    raw = RawDocument(
        document_id="abc12345",
        url="https://sebi.gov.in/circular.html",
        title="Sample Circular",
        content="This is the circular content body.",
        source="SEBI"
    )
    assert raw.document_id == "abc12345"
    assert raw.source == "SEBI"

def test_raw_document_invalid_url():
    with pytest.raises(ValidationError):
        RawDocument(
            document_id="abc12345",
            url="not_a_valid_url",
            title="Sample",
            content="Valid content",
            source="SEBI"
        )

def test_raw_document_empty_content():
    with pytest.raises(ValidationError):
        RawDocument(
            document_id="abc12345",
            url="https://sebi.gov.in",
            title="Sample",
            content="   ",
            source="SEBI"
        )

def test_document_metadata_date_validation():
    meta = DocumentMetadata(
        published_date="2024-05-24",
        effective_date="2024-06-01",
        category="Investment Adviser"
    )
    assert meta.published_date == "2024-05-24"

    with pytest.raises(ValidationError):
        DocumentMetadata(published_date="24/05/2024")  # Non-ISO date should fail

def test_regulatory_document_sync_metadata():
    meta = DocumentMetadata(
        document_type="Circular",
        category="Mutual Funds",
        circular_number="SEBI/HO/IMD/2024/01",
        published_date="2024-06-27"
    )
    doc = RegulatoryDocument(
        document_id="doc123",
        url="https://sebi.gov.in/doc.html",
        title="MF Circular",
        source="SEBI",
        content="Important mutual fund update...",
        metadata=meta
    )
    assert doc.category == "Mutual Funds"
    assert doc.circular_number == "SEBI/HO/IMD/2024/01"
    assert doc.document_type == "Circular"

def test_serialization_to_from_mongo():
    meta = DocumentMetadata(category="Market Intermediaries")
    doc = RegulatoryDocument(
        document_id="doc999",
        url="https://sebi.gov.in/doc999.html",
        source="SEBI",
        content="Content text...",
        metadata=meta
    )
    mongo_dict = to_mongo(doc)
    assert isinstance(mongo_dict, dict)
    assert mongo_dict["document_id"] == "doc999"

    restored = from_mongo(RegulatoryDocument, mongo_dict)
    assert restored.document_id == "doc999"
    assert restored.metadata.category == "Market Intermediaries"
