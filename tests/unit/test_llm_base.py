"""
Unit Tests for Base LLM Abstraction and Error Hierarchy (Phase 49).
"""

import pytest
from app.llm.models import LLMResponse
from app.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMUnavailableError,
    LLMModelNotFoundError,
    LLMTimeoutError,
    ConfigurationError
)


def test_llm_response_structure():
    resp = LLMResponse(
        text="Investment advisers must maintain records for 8 years.",
        provider="gemini",
        model="gemini-1.5-flash",
        input_tokens=150,
        output_tokens=35,
        latency_ms=420.5
    )
    assert resp.text.startswith("Investment advisers")
    assert resp.provider == "gemini"
    assert resp.model == "gemini-1.5-flash"
    assert resp.input_tokens == 150
    assert resp.output_tokens == 35
    assert resp.latency_ms == 420.5
    assert resp.fallback_used is False


def test_error_hierarchy():
    assert issubclass(LLMUnavailableError, LLMProviderError)
    assert issubclass(LLMModelNotFoundError, LLMProviderError)
    assert issubclass(LLMTimeoutError, LLMProviderError)
    assert issubclass(ConfigurationError, LLMProviderError)
