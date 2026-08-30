"""
Unit Tests for Ollama Local LLM Provider (Phase 48).
"""

import pytest
import requests
from unittest.mock import patch, MagicMock

from app.llm.ollama_provider import OllamaProvider
from app.llm.base import (
    LLMUnavailableError,
    LLMModelNotFoundError,
    LLMTimeoutError,
    LLMProviderError
)
from app.retrieval.mongodb_vector import RetrievedChunk


def test_ollama_provider_model_info():
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2", timeout_seconds=15.0)
    info = provider.get_model_info()
    assert info["provider"] == "ollama"
    assert info["model"] == "llama3.2"
    assert info["local"] is True


def test_ollama_is_available_success():
    provider = OllamaProvider()
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert provider.is_available() is True


def test_ollama_is_available_failure():
    provider = OllamaProvider()
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError):
        assert provider.is_available() is False


def test_ollama_generate_success():
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")
    mock_payload = {
        "response": "Under SEBI regulations, fee cap is 2.5% per annum [1].",
        "prompt_eval_count": 85,
        "eval_count": 18,
        "total_duration": 1200000000
    }

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_post.return_value = mock_resp

        res = provider.generate("What is the fee limit?")

        assert "2.5%" in res.text
        assert res.provider == "ollama"
        assert res.model == "llama3.2"
        assert res.input_tokens == 85
        assert res.output_tokens == 18
        assert res.latency_ms >= 0


def test_ollama_generate_connection_error():
    provider = OllamaProvider()
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        with pytest.raises(LLMUnavailableError) as exc_info:
            provider.generate("Test prompt")
        assert "Cannot connect to Ollama" in str(exc_info.value)


def test_ollama_generate_timeout():
    provider = OllamaProvider()
    with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timed out")):
        with pytest.raises(LLMTimeoutError) as exc_info:
            provider.generate("Test prompt")
        assert "timed out" in str(exc_info.value)


def test_ollama_generate_model_not_found():
    provider = OllamaProvider(model="nonexistent-model-xyz")
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "model not found"
        mock_post.return_value = mock_resp

        with pytest.raises(LLMModelNotFoundError) as exc_info:
            provider.generate("Test prompt")
        assert "not available" in str(exc_info.value)


def test_ollama_generate_empty_response():
    provider = OllamaProvider()
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "   "}
        mock_post.return_value = mock_resp

        with pytest.raises(LLMProviderError):
            provider.generate("Test prompt")


def test_ollama_generate_answer_with_citations():
    provider = OllamaProvider(model="llama3.2")
    mock_payload = {
        "response": "Investment advisers must complete an annual audit within 6 months [1].",
        "prompt_eval_count": 100,
        "eval_count": 20
    }

    chunks = [
        RetrievedChunk(
            chunk_id="chk_ia_01",
            document_id="doc_ia_01",
            title="SEBI IA Guidelines",
            section="Audit Obligations",
            content="Annual compliance audit must be completed within 6 months.",
            score=0.88,
            source="SEBI",
            published_date="2024-01-10",
            url="https://sebi.gov.in/doc2.html"
        )
    ]

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_post.return_value = mock_resp

        res = provider.generate_answer("What is the audit deadline?", retrieved_chunks=chunks)
        assert "6 months" in res["answer"]
        assert len(res["sources"]) == 1
        assert res["sources"][0]["source_id"] == 1
        assert res["provider"] == "ollama"
