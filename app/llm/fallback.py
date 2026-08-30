"""
Fallback LLM Provider Orchestrator (Phase 49).

Handles transparent, observable fallback routing between primary and secondary providers.
"""

import logging
from typing import Optional, Dict, Any, List

from app.llm.base import BaseLLMProvider, LLMUnavailableError, LLMProviderError
from app.llm.models import LLMResponse
from app.retrieval.mongodb_vector import RetrievedChunk

logger = logging.getLogger("regintel.llm.fallback")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class FallbackLLMProvider(BaseLLMProvider):
    """
    Wraps a primary LLM provider and a fallback LLM provider.
    If primary fails and fallback is enabled, routes to fallback and annotates response with diagnostic telemetry.
    """

    def __init__(
        self,
        primary_provider: BaseLLMProvider,
        fallback_provider: BaseLLMProvider,
        fallback_enabled: bool = False
    ):
        self.primary = primary_provider
        self.fallback = fallback_provider
        self.fallback_enabled = fallback_enabled

    def is_available(self) -> bool:
        """Returns True if primary is available, or if fallback is enabled and available."""
        if self.primary.is_available():
            return True
        if self.fallback_enabled and self.fallback.is_available():
            return True
        return False

    def get_model_info(self) -> Dict[str, Any]:
        """Returns aggregated metadata of primary and fallback providers."""
        primary_info = self.primary.get_model_info()
        fallback_info = self.fallback.get_model_info()
        return {
            "provider": primary_info.get("provider"),
            "model": primary_info.get("model"),
            "local": primary_info.get("local", False),
            "fallback_enabled": self.fallback_enabled,
            "fallback_provider": fallback_info.get("provider"),
            "fallback_model": fallback_info.get("model")
        }

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Attempts primary generation; falls back to secondary provider if enabled and primary fails.
        """
        primary_name = self.primary.get_model_info().get("provider", "primary")
        fallback_name = self.fallback.get_model_info().get("provider", "fallback")

        try:
            resp = self.primary.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            resp.fallback_used = False
            resp.primary_provider = primary_name
            return resp

        except Exception as primary_err:
            if not self.fallback_enabled:
                logger.error(f"Primary provider '{primary_name}' failed and fallback is disabled: {primary_err}")
                raise primary_err

            logger.warning(
                f"Primary LLM provider '{primary_name}' failed ({type(primary_err).__name__}: {primary_err}). "
                f"Attempting fallback to '{fallback_name}'..."
            )

            try:
                fallback_resp = self.fallback.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                fallback_resp.fallback_used = True
                fallback_resp.primary_provider = primary_name
                fallback_resp.fallback_provider = fallback_name
                return fallback_resp

            except Exception as fallback_err:
                logger.error(
                    f"Both primary ('{primary_name}') and fallback ('{fallback_name}') providers failed. "
                    f"Primary: {primary_err} | Fallback: {fallback_err}"
                )
                raise LLMUnavailableError(
                    f"Both primary LLM ('{primary_name}') and fallback LLM ('{fallback_name}') failed to generate a response. "
                    f"Primary error: {primary_err} | Fallback error: {fallback_err}"
                ) from fallback_err

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[RetrievedChunk],
        enable_citation_regeneration: bool = True
    ) -> Dict[str, Any]:
        """
        Generates grounded regulatory answer with fallback support.
        """
        primary_name = self.primary.get_model_info().get("provider", "primary")
        fallback_name = self.fallback.get_model_info().get("provider", "fallback")

        try:
            result = self.primary.generate_answer(
                question=question,
                retrieved_chunks=retrieved_chunks,
                enable_citation_regeneration=enable_citation_regeneration
            )
            result["fallback_used"] = False
            result["primary_provider"] = primary_name
            return result

        except Exception as primary_err:
            if not self.fallback_enabled:
                logger.error(f"Primary provider '{primary_name}' failed and fallback is disabled: {primary_err}")
                raise primary_err

            logger.warning(
                f"Primary LLM provider '{primary_name}' failed during answer generation ({primary_err}). "
                f"Attempting fallback to '{fallback_name}'..."
            )

            try:
                result = self.fallback.generate_answer(
                    question=question,
                    retrieved_chunks=retrieved_chunks,
                    enable_citation_regeneration=enable_citation_regeneration
                )
                result["fallback_used"] = True
                result["primary_provider"] = primary_name
                result["fallback_provider"] = fallback_name
                return result

            except Exception as fallback_err:
                logger.error(
                    f"Both primary ('{primary_name}') and fallback ('{fallback_name}') providers failed. "
                    f"Primary: {primary_err} | Fallback: {fallback_err}"
                )
                raise LLMUnavailableError(
                    f"Both primary LLM ('{primary_name}') and fallback LLM ('{fallback_name}') failed. "
                    f"Primary: {primary_err} | Fallback: {fallback_err}"
                ) from fallback_err
