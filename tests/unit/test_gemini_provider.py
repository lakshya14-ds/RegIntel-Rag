"""
Unit Tests for Gemini LLM Provider (Phase 49).
"""

import pytest
from unittest.mock import MagicMock
from app.llm.gemini_provider import GeminiProvider
from app.llm.base import LLMUnavailableError, LLMProviderError
from app.retrieval.mongodb_vector import RetrievedChunk


def test_gemini_provider_init_and_model_info():
    provider = GeminiProvider(api_key="test_api_key", model_name="models/gemini-1.5-pro")
    assert provider.is_available() is True
    info = provider.get_model_info()
    assert info["provider"] == "gemini"
    assert info["model"] == "models/gemini-1.5-pro"
    assert info["local"] is False


def test_gemini_provider_generate_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Grounded regulatory answer [1]."
    mock_response.usage_metadata.prompt_token_count = 120
    mock_response.usage_metadata.candidates_token_count = 25

    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="fake_key", client=mock_client)
    res = provider.generate("What is the fee limit?")

    assert res.text == "Grounded regulatory answer [1]."
    assert res.provider == "gemini"
    assert res.input_tokens == 120
    assert res.output_tokens == 25
    assert res.latency_ms >= 0


def test_gemini_provider_empty_prompt_error():
    provider = GeminiProvider(api_key="fake_key")
    with pytest.raises(ValueError):
        provider.generate("")


def test_gemini_provider_empty_response_error():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = ""
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="fake_key", client=mock_client)
    with pytest.raises(LLMUnavailableError):
        provider.generate("Test prompt", max_retries=1)


def test_gemini_provider_generate_answer():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Investment Advisers must maintain records for 8 years [1]."
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="fake_key", client=mock_client)

    chunks = [
        RetrievedChunk(
            chunk_id="chk_01",
            document_id="doc_01",
            title="IA Regulations",
            section="Record Maintenance",
            content="Books of accounts and records must be maintained for 8 years.",
            score=0.92,
            source="SEBI",
            published_date="2024-05-15",
            url="https://sebi.gov.in/doc1.html"
        )
    ]

    res = provider.generate_answer("What are the record keeping rules?", retrieved_chunks=chunks)
    assert "8 years" in res["answer"]
    assert len(res["sources"]) == 1
    assert res["sources"][0]["source_id"] == 1
    assert res["provider"] == "gemini"
