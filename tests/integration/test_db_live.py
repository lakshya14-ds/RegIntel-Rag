import pytest
from app.db import ping_mongodb, MongoDBConnectionError
from app.ingestion.repository import DocumentRepository
from app.ingestion.models import RegulatoryDocument, DocumentMetadata

@pytest.mark.integration
def test_live_mongodb_connection_and_crud():
    try:
        assert ping_mongodb() is True
    except MongoDBConnectionError as e:
        pytest.skip(f"Live MongoDB cluster unavailable: {e}")

    repo = DocumentRepository()
    
    # Test index creation
    repo.create_metadata_indexes()

    # Test write and read
    meta = DocumentMetadata(
        document_type="Circular",
        category="Investment Adviser",
        circular_number="SEBI/TEST/2026/01",
        published_date="2026-08-26"
    )
    test_doc = RegulatoryDocument(
        document_id="integration_test_doc_001",
        url="https://sebi.gov.in/test_circular.html",
        title="Integration Test Circular",
        source="SEBI",
        content="Test content for live database verification.",
        metadata=meta
    )

    doc_id = repo.save_document(test_doc)
    assert doc_id == "integration_test_doc_001"
    assert repo.document_exists("integration_test_doc_001") is True

    fetched = repo.get_document_by_id("integration_test_doc_001")
    assert fetched is not None
    assert fetched["title"] == "Integration Test Circular"
