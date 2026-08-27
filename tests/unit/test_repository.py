import pytest
from unittest.mock import MagicMock
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.ingestion.repository import DocumentRepository

def test_document_repository_save_and_exists():
    mock_collection = MagicMock()
    mock_collection.count_documents.return_value = 1
    mock_collection.find_one.return_value = {
        "document_id": "test_doc_123",
        "title": "Test Title",
        "content": "Test content",
        "source": "SEBI"
    }

    repo = DocumentRepository(collection=mock_collection)
    
    meta = DocumentMetadata(category="Mutual Funds")
    doc = RegulatoryDocument(
        document_id="test_doc_123",
        url="https://sebi.gov.in/test.html",
        title="Test Title",
        source="SEBI",
        content="Test content",
        metadata=meta
    )

    # Test Save (upsert)
    doc_id = repo.save_document(doc)
    assert doc_id == "test_doc_123"
    assert mock_collection.update_one.called

    # Test Exists
    exists = repo.document_exists("test_doc_123")
    assert exists is True
    mock_collection.count_documents.assert_called_with({"document_id": "test_doc_123"}, limit=1)

    # Test Get by ID
    fetched = repo.get_document_by_id("test_doc_123")
    assert fetched is not None
    assert fetched["document_id"] == "test_doc_123"

def test_document_repository_create_indexes():
    mock_collection = MagicMock()
    mock_collection.create_index.return_value = "idx_name"

    repo = DocumentRepository(collection=mock_collection)
    indexes = repo.create_metadata_indexes()
    assert len(indexes) >= 7
    assert mock_collection.create_index.called
