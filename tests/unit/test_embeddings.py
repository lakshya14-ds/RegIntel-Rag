import math
import pytest
from unittest.mock import MagicMock

from app.ingestion.models import DocumentChunk
from app.rag.embeddings import (
    GeminiEmbeddingService,
    normalize_embedding,
    validate_embedding,
    EmbeddingError
)


def test_normalize_embedding_unit_vector():
    vec = [3.0, 4.0]
    normalized = normalize_embedding(vec)
    assert len(normalized) == 2
    assert pytest.approx(normalized[0]) == 0.6
    assert pytest.approx(normalized[1]) == 0.8
    # Norm should be exactly 1.0
    norm = math.sqrt(sum(x * x for x in normalized))
    assert pytest.approx(norm) == 1.0


def test_normalize_embedding_zero_vector_raises():
    with pytest.raises(EmbeddingError):
        normalize_embedding([0.0, 0.0, 0.0])

    with pytest.raises(EmbeddingError):
        normalize_embedding([])


def test_validate_embedding_valid():
    # Construct a 768-dim normalized vector
    vec = [1.0 / math.sqrt(768)] * 768
    assert validate_embedding(vec, expected_dim=768) is True


def test_validate_embedding_invalid_dimensions():
    vec = [0.1] * 512
    assert validate_embedding(vec, expected_dim=768) is False


def test_validate_embedding_not_normalized():
    vec = [1.0] * 768
    assert validate_embedding(vec, expected_dim=768) is False


def test_validate_embedding_nan_or_inf():
    vec = [1.0 / math.sqrt(768)] * 768
    vec[0] = float("nan")
    assert validate_embedding(vec, expected_dim=768) is False

    vec[0] = float("inf")
    assert validate_embedding(vec, expected_dim=768) is False


def test_gemini_embedding_service_config():
    service = GeminiEmbeddingService(
        api_key="mock_key",
        model_name="gemini-embedding-001",
        output_dimensionality=768
    )
    assert service.model_name == "gemini-embedding-001"
    assert service.output_dimensionality == 768


def test_embed_document_with_mock():
    mock_values = [0.1] * 768
    mock_response = MagicMock()
    mock_response.embeddings = [MagicMock(values=mock_values)]
    
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = mock_response

    service = GeminiEmbeddingService(api_key="test_key", client=mock_client)
    vector = service.embed_document("Sample regulatory text")
    
    assert len(vector) == 768
    assert validate_embedding(vector, expected_dim=768) is True
    
    # Verify task_type passed was RETRIEVAL_DOCUMENT
    args, kwargs = mock_client.models.embed_content.call_args
    config = kwargs.get("config")
    assert config.task_type == "RETRIEVAL_DOCUMENT"
    assert config.output_dimensionality == 768


def test_embed_query_with_mock():
    mock_values = [0.1] * 768
    mock_response = MagicMock()
    mock_response.embeddings = [MagicMock(values=mock_values)]
    
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = mock_response

    service = GeminiEmbeddingService(api_key="test_key", client=mock_client)
    vector = service.embed_query("What are the IA eligibility requirements?")
    
    assert len(vector) == 768
    assert validate_embedding(vector, expected_dim=768) is True
    
    # Verify task_type passed was RETRIEVAL_QUERY
    args, kwargs = mock_client.models.embed_content.call_args
    config = kwargs.get("config")
    assert config.task_type == "RETRIEVAL_QUERY"


def test_embed_chunk_reuses_existing_embedding():
    mock_client = MagicMock()
    service = GeminiEmbeddingService(api_key="test_key", client=mock_client)
    existing_vector = [1.0 / math.sqrt(768)] * 768
    
    chunk = DocumentChunk(
        chunk_id="chunk_cached_01",
        document_id="doc_cached",
        chunk_index=0,
        content="Cached content",
        title="Title",
        source="SEBI",
        url="https://sebi.gov.in/cached.html",
        token_count=50,
        embedding=existing_vector,
        embedding_model="gemini-embedding-001",
        embedding_dimensions=768
    )
    
    result = service.embed_chunk(chunk)
    # Should not make any API calls since valid embedding exists
    mock_client.models.embed_content.assert_not_called()
    assert result.embedding == existing_vector
