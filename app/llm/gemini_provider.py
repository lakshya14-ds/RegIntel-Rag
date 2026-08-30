"""
Gemini Generation Provider implementing BaseLLMProvider interface (Phase 49).
"""

import os
import re
import time
import logging
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types

from app.config import settings
from app.llm.base import BaseLLMProvider, LLMProviderError, LLMUnavailableError
from app.llm.models import LLMResponse
from app.retrieval.mongodb_vector import RetrievedChunk
from app.rag.prompts import build_rag_prompt, build_correction_prompt
from app.rag.context import build_evidence_context
from app.rag.citations import CitationManager, SourceCitation

logger = logging.getLogger("regintel.llm.gemini")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini generation backend with adaptive backoff, citation validation,
    and structured LLMResponse returns.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        client: Optional[Any] = None
    ):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.gemini_generation_model or "models/gemini-flash-lite-latest"
        self._client: Optional[Any] = client

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise LLMUnavailableError("GEMINI_API_KEY is not configured in environment.")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @client.setter
    def client(self, value: Any):
        self._client = value

    def _call_gemini(self, prompt: str, **kwargs) -> str:
        """Backward compatibility helper for direct text generation."""
        resp = self.generate(prompt, **kwargs)
        return resp.text

    def is_available(self) -> bool:
        """Verifies if Gemini API key is configured."""
        return bool(self.api_key or self._client is not None)

    def get_model_info(self) -> Dict[str, Any]:
        """Returns metadata for Gemini provider."""
        return {
            "provider": "gemini",
            "model": self.model_name,
            "local": False
        }

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        max_retries: int = 5,
        backoff_base: float = 2.0
    ) -> LLMResponse:
        """
        Executes Gemini generation with exponential backoff on rate limits / server errors.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        start_time = time.perf_counter()
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents
                )
                latency_ms = (time.perf_counter() - start_time) * 1000.0

                raw_text = response.text if response and hasattr(response, "text") and response.text else ""
                if not raw_text.strip():
                    raise LLMProviderError("Gemini returned an empty response.")

                # Extract token usage if provided
                input_tokens = None
                output_tokens = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
                    output_tokens = getattr(response.usage_metadata, "candidates_token_count", None)

                return LLMResponse(
                    text=raw_text.strip(),
                    provider="gemini",
                    model=self.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=round(latency_ms, 2),
                    raw_metadata={}
                )

            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
                    match_sec = re.search(r"retry\s+in\s+(\d+)", err_str)
                    sleep_sec = float(match_sec.group(1)) + 1.0 if match_sec else (20.0 * attempt)
                else:
                    sleep_sec = backoff_base ** attempt

                logger.warning(
                    f"Gemini generation attempt {attempt}/{max_retries} failed: {type(e).__name__} - {e}. "
                    f"Retrying in {sleep_sec:.1f}s..."
                )
                time.sleep(sleep_sec)

        raise LLMUnavailableError(f"Gemini generation failed after {max_retries} retries: {last_error}") from last_error

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[RetrievedChunk],
        enable_citation_regeneration: bool = True
    ) -> Dict[str, Any]:
        """
        Generates a grounded regulatory answer with validated citations.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        if not retrieved_chunks:
            return {
                "answer": "I could not find sufficient evidence in the indexed regulatory sources.",
                "sources": [],
                "provider": "gemini",
                "model": self.model_name,
                "latency_ms": 0.0
            }

        evidence_text = build_evidence_context(retrieved_chunks)
        prompt = build_rag_prompt(evidence_text=evidence_text, question=question.strip())

        # 1. Primary generation call
        llm_resp = self.generate(prompt)
        answer_text = llm_resp.text

        # 2. Validate citations
        citations, is_valid, invalid_ids = CitationManager.validate_answer_citations(answer_text, retrieved_chunks)

        # 3. Controlled single regeneration if invalid citations detected
        if not is_valid and enable_citation_regeneration:
            logger.info(f"Invalid citation IDs {invalid_ids} detected. Attempting single correction regeneration...")
            try:
                correction_prompt = build_correction_prompt(
                    evidence_text=evidence_text,
                    question=question.strip(),
                    previous_answer=answer_text,
                    invalid_citations=invalid_ids
                )
                corr_resp = self.generate(correction_prompt)
                corrected_text = corr_resp.text
                citations_corr, is_valid_corr, invalid_ids_corr = CitationManager.validate_answer_citations(corrected_text, retrieved_chunks)
                if is_valid_corr or len(invalid_ids_corr) < len(invalid_ids):
                    answer_text = corrected_text
                    citations = citations_corr
                else:
                    answer_text = CitationManager.sanitize_invalid_citations(answer_text, max_valid_id=len(retrieved_chunks))
            except Exception as e:
                logger.warning(f"Correction regeneration failed ({e}). Sanitizing original response.")
                answer_text = CitationManager.sanitize_invalid_citations(answer_text, max_valid_id=len(retrieved_chunks))

        return {
            "answer": answer_text,
            "sources": [c.model_dump() for c in citations],
            "provider": "gemini",
            "model": self.model_name,
            "latency_ms": llm_resp.latency_ms,
            "input_tokens": llm_resp.input_tokens,
            "output_tokens": llm_resp.output_tokens
        }
