"""
Ollama Local LLM Generation Provider (Phase 48).

Executes local offline generation via Ollama's HTTP REST API without sending prompts to cloud services.
"""

import time
import logging
import requests
from typing import Optional, Dict, Any, List

from app.config import settings
from app.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMUnavailableError,
    LLMModelNotFoundError,
    LLMTimeoutError
)
from app.llm.models import LLMResponse
from app.retrieval.mongodb_vector import RetrievedChunk
from app.rag.prompts import build_rag_prompt, build_correction_prompt
from app.rag.context import build_evidence_context
from app.rag.citations import CitationManager, SourceCitation

logger = logging.getLogger("regintel.llm.ollama")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class OllamaProvider(BaseLLMProvider):
    """
    Ollama local LLM provider communicating over HTTP REST API.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None
    ):
        self.base_url = (base_url or settings.ollama_base_url or "http://localhost:11434").rstrip("/")
        self.model = model or settings.ollama_model or "llama3.2"
        self.timeout_seconds = timeout_seconds or settings.ollama_timeout_seconds or 30.0

    def is_available(self) -> bool:
        """
        Pings Ollama /api/tags endpoint to verify daemon is running and reachable.
        """
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def get_installed_models(self) -> List[str]:
        """Fetches list of model tags available in the local Ollama runtime."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def get_model_info(self) -> Dict[str, Any]:
        """Returns structured metadata for the Ollama provider."""
        return {
            "provider": "ollama",
            "model": self.model,
            "local": True
        }

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generates text using the local Ollama instance via /api/generate.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        url = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        if system_prompt:
            payload["system"] = system_prompt
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        start_time = time.perf_counter()

        try:
            response = requests.post(url, json=payload, timeout=self.timeout_seconds)
        except requests.exceptions.Timeout as te:
            logger.error(f"Ollama request timed out after {self.timeout_seconds}s: {te}")
            raise LLMTimeoutError(f"Ollama request timed out after {self.timeout_seconds}s.") from te
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"Cannot connect to Ollama at {self.base_url}: {ce}")
            raise LLMUnavailableError(
                f"Cannot connect to Ollama at {self.base_url}. Ensure the Ollama daemon is running locally."
            ) from ce
        except requests.exceptions.RequestException as re_err:
            logger.error(f"Ollama HTTP error: {re_err}")
            raise LLMProviderError(f"Ollama communication error: {re_err}") from re_err

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if response.status_code == 404:
            logger.error(f"Ollama model '{self.model}' not found on host {self.base_url}.")
            raise LLMModelNotFoundError(
                f"Configured Ollama model '{self.model}' is not available. "
                f"Pull the model locally ('ollama pull {self.model}') and retry."
            )
        elif response.status_code != 200:
            logger.error(f"Ollama API returned status {response.status_code}: {response.text}")
            raise LLMProviderError(f"Ollama API returned error {response.status_code}: {response.text}")

        try:
            data = response.json()
        except Exception as je:
            raise LLMProviderError(f"Malformed JSON response from Ollama: {je}") from je

        raw_text = data.get("response", "")
        if not raw_text.strip():
            raise LLMProviderError("Ollama returned an empty response.")

        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")

        return LLMResponse(
            text=raw_text.strip(),
            provider="ollama",
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(latency_ms, 2),
            raw_metadata={"total_duration": data.get("total_duration")}
        )

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[RetrievedChunk],
        enable_citation_regeneration: bool = True
    ) -> Dict[str, Any]:
        """
        Generates a grounded regulatory answer with citation verification using Ollama.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        if not retrieved_chunks:
            return {
                "answer": "I could not find sufficient evidence in the indexed regulatory sources.",
                "sources": [],
                "provider": "ollama",
                "model": self.model,
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
            logger.info(f"Invalid citation IDs {invalid_ids} detected in Ollama response. Attempting correction regeneration...")
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
                logger.warning(f"Correction regeneration failed on Ollama ({e}). Sanitizing original response.")
                answer_text = CitationManager.sanitize_invalid_citations(answer_text, max_valid_id=len(retrieved_chunks))

        return {
            "answer": answer_text,
            "sources": [c.model_dump() for c in citations],
            "provider": "ollama",
            "model": self.model,
            "latency_ms": llm_resp.latency_ms,
            "input_tokens": llm_resp.input_tokens,
            "output_tokens": llm_resp.output_tokens
        }
