"""
LLM Provider Factory and Router (Phase 49).

Resolves configured LLM generation providers (Gemini, Ollama) and attaches fallback routing if enabled.
"""

import logging
from typing import Optional, Dict, Any

from app.config import settings
from app.llm.base import BaseLLMProvider, ConfigurationError
from app.llm.gemini_provider import GeminiProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.fallback import FallbackLLMProvider

logger = logging.getLogger("regintel.llm.factory")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def get_llm_provider(
    provider_name: Optional[str] = None,
    enable_fallback: Optional[bool] = None,
    **kwargs
) -> BaseLLMProvider:
    """
    Instantiates and returns the configured LLM generation provider.
    Supported providers: 'gemini', 'ollama'.
    """
    raw_provider = provider_name or settings.llm_provider or "gemini"
    provider_clean = raw_provider.strip().lower()

    fallback_active = enable_fallback if enable_fallback is not None else settings.llm_fallback_enabled

    if provider_clean == "gemini":
        gemini_prov = GeminiProvider(**kwargs)
        if fallback_active:
            ollama_prov = OllamaProvider()
            logger.info("Initializing Gemini LLM Provider with Ollama fallback enabled.")
            return FallbackLLMProvider(
                primary_provider=gemini_prov,
                fallback_provider=ollama_prov,
                fallback_enabled=True
            )
        return gemini_prov

    elif provider_clean == "ollama":
        ollama_prov = OllamaProvider(**kwargs)
        if fallback_active:
            gemini_prov = GeminiProvider()
            logger.info("Initializing Ollama LLM Provider with Gemini fallback enabled.")
            return FallbackLLMProvider(
                primary_provider=ollama_prov,
                fallback_provider=gemini_prov,
                fallback_enabled=True
            )
        return ollama_prov

    else:
        logger.error(f"Unsupported LLM provider requested: '{raw_provider}'")
        raise ConfigurationError(
            f"Unsupported LLM provider: '{raw_provider}'. Supported providers are: 'gemini', 'ollama'."
        )
