"""
Unit Tests for Fallback LLM Provider Orchestrator (Phase 49).
"""

import pytest
from unittest.mock import MagicMock

from app.llm.fallback import FallbackLLMProvider
from app.llm.models import LLMResponse
from app.llm.base import LLMUnavailableError


def test_fallback_primary_success():
    mock_primary = MagicMock()
    mock_primary.get_model_info.return_value = {"provider": "gemini", "model": "gemini-1.5-flash"}
    mock_primary.generate.return_value = LLMResponse(
        text="Primary answer",
        provider="gemini",
        model="gemini-1.5-flash"
    )

    mock_fallback = MagicMock()
    mock_fallback.get_model_info.return_value = {"provider": "ollama", "model": "llama3.2"}

    provider = FallbackLLMProvider(
        primary_provider=mock_primary,
        fallback_provider=mock_fallback,
        fallback_enabled=True
    )

    res = provider.generate("Test question")
    assert res.text == "Primary answer"
    assert res.fallback_used is False
    assert res.primary_provider == "gemini"
    mock_fallback.generate.assert_not_called()


def test_fallback_disabled_raises_primary_error():
    mock_primary = MagicMock()
    mock_primary.get_model_info.return_value = {"provider": "gemini", "model": "gemini-1.5-flash"}
    mock_primary.generate.side_effect = LLMUnavailableError("Gemini quota exceeded")

    mock_fallback = MagicMock()

    provider = FallbackLLMProvider(
        primary_provider=mock_primary,
        fallback_provider=mock_fallback,
        fallback_enabled=False
    )

    with pytest.raises(LLMUnavailableError):
        provider.generate("Test question")
    mock_fallback.generate.assert_not_called()


def test_fallback_enabled_routes_to_secondary():
    mock_primary = MagicMock()
    mock_primary.get_model_info.return_value = {"provider": "gemini", "model": "gemini-1.5-flash"}
    mock_primary.generate.side_effect = LLMUnavailableError("Gemini quota exceeded")

    mock_fallback = MagicMock()
    mock_fallback.get_model_info.return_value = {"provider": "ollama", "model": "llama3.2"}
    mock_fallback.generate.return_value = LLMResponse(
        text="Fallback local answer",
        provider="ollama",
        model="llama3.2"
    )

    provider = FallbackLLMProvider(
        primary_provider=mock_primary,
        fallback_provider=mock_fallback,
        fallback_enabled=True
    )

    res = provider.generate("Test question")
    assert res.text == "Fallback local answer"
    assert res.fallback_used is True
    assert res.primary_provider == "gemini"
    assert res.fallback_provider == "ollama"


def test_both_providers_fail():
    mock_primary = MagicMock()
    mock_primary.get_model_info.return_value = {"provider": "gemini", "model": "gemini-1.5-flash"}
    mock_primary.generate.side_effect = LLMUnavailableError("Gemini unavailable")

    mock_fallback = MagicMock()
    mock_fallback.get_model_info.return_value = {"provider": "ollama", "model": "llama3.2"}
    mock_fallback.generate.side_effect = LLMUnavailableError("Ollama daemon down")

    provider = FallbackLLMProvider(
        primary_provider=mock_primary,
        fallback_provider=mock_fallback,
        fallback_enabled=True
    )

    with pytest.raises(LLMUnavailableError) as exc_info:
        provider.generate("Test question")
    assert "Both primary LLM ('gemini') and fallback LLM ('ollama') failed" in str(exc_info.value)
