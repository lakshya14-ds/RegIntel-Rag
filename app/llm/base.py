"""
Abstract Base Class and Error Definitions for LLM Providers (Phases 48 & 49).
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from app.llm.models import LLMResponse
from app.retrieval.mongodb_vector import RetrievedChunk


class LLMProviderError(Exception):
    """Base exception for all LLM provider failures."""
    pass


class LLMUnavailableError(LLMProviderError):
    """Raised when the requested LLM service cannot be reached."""
    pass


class LLMModelNotFoundError(LLMProviderError):
    """Raised when the specified model is not found or not pulled."""
    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when LLM generation exceeds the configured timeout."""
    pass


class ConfigurationError(LLMProviderError):
    """Raised when provider configuration is invalid or missing."""
    pass


class BaseLLMProvider(ABC):
    """
    Common abstraction interface for LLM text generation backends.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Executes text generation using the underlying LLM provider.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Verifies whether the LLM service/API is reachable and operational.
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Returns structured metadata regarding provider name, model identifier, and locality.
        """
        pass

    @abstractmethod
    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[RetrievedChunk],
        enable_citation_regeneration: bool = True
    ) -> Dict[str, Any]:
        """
        Generates a grounded regulatory answer with citation verification and structured sources.
        """
        pass
