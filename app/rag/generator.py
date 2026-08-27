"""
Gemini Generation Service for Grounded Regulatory Answering.

Generates grounded answers from retrieved regulatory evidence using Google's GenAI SDK (Gemini Flash-Lite).
Enforces non-hallucination, citation placement, and structured response outputs.
"""

import os
import re
import json
import time
import logging
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types

from app.config import settings
from app.retrieval.mongodb_vector import RetrievedChunk
from app.rag.prompts import build_rag_prompt, build_correction_prompt
from app.rag.context import build_evidence_context
from app.rag.citations import CitationManager, SourceCitation

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

DEFAULT_GENERATION_MODEL = "models/gemini-flash-lite-latest"


class GenerationError(Exception):
    """Raised when LLM text generation fails."""
    pass


class GeminiGenerator:
    """
    Orchestrates prompt generation, API calls to Gemini Flash-Lite, and citation verification.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        client: Optional[Any] = None
    ):
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key and client is None:
            logger.warning("GEMINI_API_KEY is not configured in environment.")

        self.model_name = model_name or DEFAULT_GENERATION_MODEL
        self._client: Optional[Any] = client

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise GenerationError("GEMINI_API_KEY is missing. Cannot initialize Gemini client.")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @client.setter
    def client(self, value: Any):
        self._client = value

    def _call_gemini(self, prompt: str, max_retries: int = 5, backoff_base: float = 2.0) -> str:
        """Executes Gemini API generation with adaptive backoff for transient 503/429 errors."""
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                raw_text = response.text if response and hasattr(response, "text") and response.text else ""
                if not raw_text.strip():
                    raise GenerationError("Gemini returned an empty response.")
                return raw_text.strip()
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # If rate limited (429 or RESOURCE_EXHAUSTED), extract retry delay or use progressive sleep
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
        raise GenerationError(f"Generation failed after {max_retries} retries: {last_error}") from last_error

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[RetrievedChunk],
        enable_citation_regeneration: bool = True
    ) -> Dict[str, Any]:
        """
        Generates a grounded regulatory answer with validated citations.
        If invalid citations are detected, attempts a single controlled regeneration.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        if not retrieved_chunks:
            return {
                "answer": "I could not find sufficient evidence in the indexed regulatory sources.",
                "sources": []
            }

        evidence_text = build_evidence_context(retrieved_chunks)
        prompt = build_rag_prompt(evidence_text=evidence_text, question=question.strip())

        # 1. Primary generation call
        answer_text = self._call_gemini(prompt)

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
                corrected_text = self._call_gemini(correction_prompt)
                citations_corr, is_valid_corr, invalid_ids_corr = CitationManager.validate_answer_citations(corrected_text, retrieved_chunks)
                if is_valid_corr or len(invalid_ids_corr) < len(invalid_ids):
                    answer_text = corrected_text
                    citations = citations_corr
                else:
                    # Sanitize remaining invalid citations
                    answer_text = CitationManager.sanitize_invalid_citations(answer_text, max_valid_id=len(retrieved_chunks))
            except Exception as e:
                logger.warning(f"Correction regeneration failed ({e}). Sanitizing original response.")
                answer_text = CitationManager.sanitize_invalid_citations(answer_text, max_valid_id=len(retrieved_chunks))

        return {
            "answer": answer_text,
            "sources": [c.model_dump() for c in citations]
        }


# Default generator instance
_default_generator = GeminiGenerator()


def generate_answer(question: str, retrieved_chunks: List[RetrievedChunk]) -> Dict[str, Any]:
    return _default_generator.generate_answer(question, retrieved_chunks)
