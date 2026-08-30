"""
Integration Tests for LLM Providers (Phases 48 & 49).

Gated by environment flags:
RUN_GEMINI_INTEGRATION=true
RUN_OLLAMA_INTEGRATION=true
"""

import os
import pytest
from app.llm.factory import get_llm_provider
from app.retrieval.mongodb_vector import RetrievedChunk


@pytest.mark.skipif(
    os.getenv("RUN_GEMINI_INTEGRATION", "false").lower() not in ("true", "1"),
    reason="Live Gemini integration disabled. Set RUN_GEMINI_INTEGRATION=true to enable."
)
def test_live_gemini_provider():
    provider = get_llm_provider("gemini", enable_fallback=False)
    assert provider.is_available() is True

    res = provider.generate("Summarize the mandate of SEBI in one sentence.")
    assert len(res.text) > 10
    assert res.provider == "gemini"


@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_INTEGRATION", "false").lower() not in ("true", "1"),
    reason="Live Ollama integration disabled. Set RUN_OLLAMA_INTEGRATION=true to enable."
)
def test_live_ollama_provider():
    provider = get_llm_provider("ollama", enable_fallback=False)
    if not provider.is_available():
        pytest.skip("Local Ollama daemon is not reachable.")

    res = provider.generate("State the definition of an investment adviser in one sentence.")
    assert len(res.text) > 5
    assert res.provider == "ollama"
