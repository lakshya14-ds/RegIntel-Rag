"""
Ollama Live Integration Tests (Phase 51.9).

Gated by environment flag: RUN_OLLAMA_INTEGRATION=true.
Validates live communication with local Ollama daemon and configured model.
"""

import os
import pytest
from app.llm.ollama_provider import OllamaProvider


@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_INTEGRATION", "false").lower() not in ("true", "1"),
    reason="Live Ollama integration test disabled. Set RUN_OLLAMA_INTEGRATION=true to enable."
)
def test_live_ollama_generation():
    provider = OllamaProvider()
    if not provider.is_available():
        pytest.skip("Local Ollama daemon is not reachable on configured URL.")

    res = provider.generate("Explain SEBI in 5 words.")
    assert res.text != ""
    assert res.provider == "ollama"
    assert res.latency_ms > 0
