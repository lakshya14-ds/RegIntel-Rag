"""
Gemini Live Integration Tests (Phase 51.8).

Gated by environment flag: RUN_GEMINI_INTEGRATION=true.
Validates live embedding generation and minimal answer generation with Google Gemini.
"""

import os
import pytest
from app.rag.embeddings import GeminiEmbeddingService
from app.llm.gemini_provider import GeminiProvider


@pytest.mark.skipif(
    os.getenv("RUN_GEMINI_INTEGRATION", "false").lower() not in ("true", "1"),
    reason="Live Gemini integration test disabled. Set RUN_GEMINI_INTEGRATION=true to enable."
)
def test_live_gemini_embedding():
    embedder = GeminiEmbeddingService()
    vec = embedder.generate_query_embedding("SEBI investment adviser registration norms")
    assert isinstance(vec, list)
    assert len(vec) == 768
    # Norm check (L2 normalized)
    norm = sum(x * x for x in vec) ** 0.5
    assert 0.99 <= norm <= 1.01


@pytest.mark.skipif(
    os.getenv("RUN_GEMINI_INTEGRATION", "false").lower() not in ("true", "1"),
    reason="Live Gemini integration test disabled. Set RUN_GEMINI_INTEGRATION=true to enable."
)
def test_live_gemini_generation():
    provider = GeminiProvider()
    res = provider.generate("What is SEBI? Answer in one short sentence.")
    assert res.text != ""
    assert res.provider == "gemini"
    assert res.latency_ms > 0
