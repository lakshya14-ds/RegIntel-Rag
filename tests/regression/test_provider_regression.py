"""
LLM Provider Routing & Fallback Regression Tests (Phase 51.18).

Verifies:
1. Gemini-only routing when primary succeeds.
2. Ollama-only routing when configured as primary.
3. Transparent fallback to Ollama when Gemini fails and fallback is enabled.
4. Exception propagation when Gemini fails and fallback is disabled.
"""

import pytest
from unittest.mock import MagicMock
from app.llm.fallback import FallbackLLMProvider
from app.llm.base import LLMUnavailableError
from app.llm.models import LLMResponse


def test_provider_primary_success():
    mock_gemini = MagicMock()
    mock_ollama = MagicMock()

    mock_gemini.get_model_info.return_value = {"provider": "gemini", "model": "gemini-1.5-flash"}
    mock_ollama.get_model_info.return_value = {"provider": "ollama", "model": "llama3.2"}

    mock_gemini.generate.return_value = LLMResponse(
        text="Primary Gemini response.",
        provider="gemini",
        model="gemini-1.5-flash",
        latency_ms=120.0
    )

    router = FallbackLLMProvider(primary_provider=mock_gemini, fallback_provider=mock_ollama, fallback_enabled=True)
    res = router.generate("test prompt")

    assert res.provider == "gemini"
    assert res.fallback_used is False
    mock_gemini.generate.assert_called_once()
    mock_ollama.generate.assert_not_called()


def test_provider_fallback_on_primary_failure():
    mock_gemini = MagicMock()
    mock_ollama = MagicMock()

    mock_gemini.get_model_info.return_value = {"provider": "gemini", "model": "gemini-1.5-flash"}
    mock_ollama.get_model_info.return_value = {"provider": "ollama", "model": "llama3.2"}

    mock_gemini.generate.side_effect = LLMUnavailableError("Gemini API rate limit exceeded")
    mock_ollama.generate.return_value = LLMResponse(
        text="Fallback Ollama response.",
        provider="ollama",
        model="llama3.2",
        latency_ms=450.0
    )

    router = FallbackLLMProvider(primary_provider=mock_gemini, fallback_provider=mock_ollama, fallback_enabled=True)
    res = router.generate("test prompt")

    assert res.provider == "ollama"
    assert res.fallback_used is True
    assert res.primary_provider == "gemini"
    assert res.fallback_provider == "ollama"


def test_provider_error_when_fallback_disabled():
    mock_gemini = MagicMock()
    mock_ollama = MagicMock()

    mock_gemini.get_model_info.return_value = {"provider": "gemini", "model": "gemini-1.5-flash"}
    mock_ollama.get_model_info.return_value = {"provider": "ollama", "model": "llama3.2"}

    mock_gemini.generate.side_effect = LLMUnavailableError("Gemini API rate limit exceeded")

    router = FallbackLLMProvider(primary_provider=mock_gemini, fallback_provider=mock_ollama, fallback_enabled=False)
    with pytest.raises(LLMUnavailableError):
        router.generate("test prompt")
