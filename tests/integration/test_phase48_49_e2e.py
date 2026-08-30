"""
End-to-End Tests for Phase 48 and 49 (Gemini, Ollama, Fallback, Error Handling).
"""

import pytest
from unittest.mock import MagicMock, patch

from app.config import settings
from app.rag.pipeline import RAGPipeline, RAGResponse
from app.llm.base import LLMUnavailableError, ConfigurationError
from app.llm.models import LLMResponse
from app.llm.gemini_provider import GeminiProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.fallback import FallbackLLMProvider
from app.retrieval.mongodb_vector import RetrievedChunk


def sample_retrieved_chunks():
    return [
        RetrievedChunk(
            chunk_id="chk_ia_01",
            document_id="doc_ia_01",
            title="SEBI (Investment Advisers) Regulations, 2013",
            section="Regulation 19 - Maintenance of Records",
            content="An investment adviser shall maintain books of accounts and records for a minimum period of eight years.",
            score=0.95,
            source="SEBI",
            published_date="2024-01-01",
            url="https://sebi.gov.in/ia_regs.html"
        )
    ]


# TEST 1 — GEMINI PRIMARY FLOW
def test_e2e_gemini_primary():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Under SEBI regulations, investment advisers must maintain records for at least 8 years [1]."
    mock_resp.usage_metadata.prompt_token_count = 150
    mock_resp.usage_metadata.candidates_token_count = 30
    mock_client.models.generate_content.return_value = mock_resp

    gemini_provider = GeminiProvider(api_key="mock_key", client=mock_client)
    pipeline = RAGPipeline(generator=gemini_provider, enable_reranker=False)

    # Mock retrieve_candidates to return deterministic chunk
    with patch.object(pipeline, "retrieve_candidates", return_value=sample_retrieved_chunks()):
        response = pipeline.ask("What are the record keeping requirements for investment advisers?")
        assert response.sufficient_evidence is True
        assert "8 years" in response.answer
        assert len(response.sources) == 1
        assert response.sources[0].source_id == 1
        assert response.llm_provider == "gemini"
        assert response.fallback_used is False


# TEST 2 — OLLAMA LOCAL FLOW
def test_e2e_ollama_local():
    mock_payload = {
        "response": "Investment advisers must retain books of accounts for 8 years according to SEBI [1].",
        "prompt_eval_count": 120,
        "eval_count": 25,
        "total_duration": 800000000
    }

    ollama_provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")
    pipeline = RAGPipeline(generator=ollama_provider, enable_reranker=False)

    with patch.object(pipeline, "retrieve_candidates", return_value=sample_retrieved_chunks()):
        with patch("requests.post") as mock_post:
            mock_http_resp = MagicMock()
            mock_http_resp.status_code = 200
            mock_http_resp.json.return_value = mock_payload
            mock_post.return_value = mock_http_resp

            response = pipeline.ask("What are the record keeping requirements for investment advisers?")
            assert response.sufficient_evidence is True
            assert "8 years" in response.answer
            assert len(response.sources) == 1
            assert response.sources[0].source_id == 1
            assert response.llm_provider == "ollama"
            assert response.fallback_used is False


# TEST 3 — FALLBACK ENABLED (Gemini down -> Ollama succeeds)
def test_e2e_fallback_enabled():
    mock_gemini = MagicMock(spec=GeminiProvider)
    mock_gemini.get_model_info.return_value = {"provider": "gemini", "model": "gemini-1.5-flash"}
    mock_gemini.generate_answer.side_effect = LLMUnavailableError("Gemini 503 Service Unavailable")

    mock_ollama = MagicMock(spec=OllamaProvider)
    mock_ollama.get_model_info.return_value = {"provider": "ollama", "model": "llama3.2"}
    mock_ollama.generate_answer.return_value = {
        "answer": "Grounded fallback answer from local Ollama [1].",
        "sources": [{"source_id": 1, "chunk_id": "chk_ia_01", "document_id": "doc_ia_01", "title": "SEBI", "score": 0.95, "url": "", "published_date": "2024-01-01", "source": "SEBI"}],
        "provider": "ollama",
        "model": "llama3.2",
        "latency_ms": 250.0
    }

    fallback_provider = FallbackLLMProvider(
        primary_provider=mock_gemini,
        fallback_provider=mock_ollama,
        fallback_enabled=True
    )

    pipeline = RAGPipeline(generator=fallback_provider, enable_reranker=False)

    with patch.object(pipeline, "retrieve_candidates", return_value=sample_retrieved_chunks()):
        response = pipeline.ask("What are the requirements?")
        assert response.sufficient_evidence is True
        assert "fallback" in response.answer.lower()
        assert response.fallback_used is True
        assert response.primary_provider == "gemini"
        assert response.fallback_provider == "ollama"


# TEST 4 — FALLBACK DISABLED (Gemini down -> fails clearly)
def test_e2e_fallback_disabled():
    mock_gemini = MagicMock(spec=GeminiProvider)
    mock_gemini.get_model_info.return_value = {"provider": "gemini", "model": "gemini-1.5-flash"}
    mock_gemini.generate_answer.side_effect = LLMUnavailableError("Gemini 503 Service Unavailable")

    mock_ollama = MagicMock(spec=OllamaProvider)

    fallback_provider = FallbackLLMProvider(
        primary_provider=mock_gemini,
        fallback_provider=mock_ollama,
        fallback_enabled=False
    )

    pipeline = RAGPipeline(generator=fallback_provider, enable_reranker=False)

    with patch.object(pipeline, "retrieve_candidates", return_value=sample_retrieved_chunks()):
        with pytest.raises(LLMUnavailableError):
            pipeline.ask("What are the requirements?")
        mock_ollama.generate_answer.assert_not_called()


# TEST 5 — BOTH UNAVAILABLE (Gemini down + Ollama down -> clear failure, no fabrication)
def test_e2e_both_unavailable():
    mock_gemini = MagicMock(spec=GeminiProvider)
    mock_gemini.get_model_info.return_value = {"provider": "gemini", "model": "gemini-1.5-flash"}
    mock_gemini.generate_answer.side_effect = LLMUnavailableError("Gemini 503 Service Unavailable")

    mock_ollama = MagicMock(spec=OllamaProvider)
    mock_ollama.get_model_info.return_value = {"provider": "ollama", "model": "llama3.2"}
    mock_ollama.generate_answer.side_effect = LLMUnavailableError("Ollama Connection Refused: localhost:11434")

    fallback_provider = FallbackLLMProvider(
        primary_provider=mock_gemini,
        fallback_provider=mock_ollama,
        fallback_enabled=True
    )

    pipeline = RAGPipeline(generator=fallback_provider, enable_reranker=False)

    with patch.object(pipeline, "retrieve_candidates", return_value=sample_retrieved_chunks()):
        with pytest.raises(LLMUnavailableError) as exc_info:
            pipeline.ask("What are the requirements?")
        assert "Both primary LLM ('gemini') and fallback LLM ('ollama') failed" in str(exc_info.value)
