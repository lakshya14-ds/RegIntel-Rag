"""
LLM Generation Service for Grounded Regulatory Answering.

Preserves backward compatibility with legacy GeminiGenerator while delegating
to the pluggable BaseLLMProvider architecture (app.llm).
"""

import logging
from typing import Optional, Dict, Any, List

from app.llm.base import BaseLLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.factory import get_llm_provider
from app.retrieval.mongodb_vector import RetrievedChunk

logger = logging.getLogger(__name__)

# Legacy Alias
GeminiGenerator = GeminiProvider
GenerationError = Exception

# Default generator instance
_default_generator: BaseLLMProvider = get_llm_provider()


def generate_answer(question: str, retrieved_chunks: List[RetrievedChunk]) -> Dict[str, Any]:
    """Generates a grounded regulatory answer using the configured active LLM provider."""
    return _default_generator.generate_answer(question, retrieved_chunks)
