"""
Unit Tests for LLM Provider Factory and Router (Phase 49).
"""

import pytest
from app.config import settings
from app.llm.factory import get_llm_provider
from app.llm.gemini_provider import GeminiProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.fallback import FallbackLLMProvider
from app.llm.base import ConfigurationError


def test_factory_select_gemini():
    prov = get_llm_provider("gemini", enable_fallback=False)
    assert isinstance(prov, GeminiProvider)
    assert prov.get_model_info()["provider"] == "gemini"
    # Ensure embedding settings are untouched
    assert settings.embedding_provider == "gemini"


def test_factory_select_ollama():
    prov = get_llm_provider("ollama", enable_fallback=False)
    assert isinstance(prov, OllamaProvider)
    assert prov.get_model_info()["provider"] == "ollama"
    # Ensure embedding settings are untouched
    assert settings.embedding_provider == "gemini"


def test_factory_select_invalid_provider():
    with pytest.raises(ConfigurationError) as exc_info:
        get_llm_provider("unsupported_ai_vendor")
    assert "Unsupported LLM provider" in str(exc_info.value)


def test_factory_with_fallback_enabled():
    prov = get_llm_provider("gemini", enable_fallback=True)
    assert isinstance(prov, FallbackLLMProvider)
    info = prov.get_model_info()
    assert info["provider"] == "gemini"
    assert info["fallback_enabled"] is True
    assert info["fallback_provider"] == "ollama"
