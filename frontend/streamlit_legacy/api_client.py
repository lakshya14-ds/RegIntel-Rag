"""
API Client for RegIntel Streamlit Frontend.

Wraps all HTTP communication with the FastAPI backend.
"""

import os
import logging
from typing import Dict, Any, Optional, List
import requests

logger = logging.getLogger("regintel.frontend")

FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000").rstrip("/")


class RegIntelAPIClient:
    """HTTP client communicating with the RegIntel FastAPI backend with host failover support."""

    def __init__(self, base_url: Optional[str] = None, timeout: int = 45):
        raw_url = (base_url or FASTAPI_BASE_URL).rstrip("/")
        self.base_url = raw_url
        self.timeout = timeout

    def _get_candidate_urls(self, path: str) -> List[str]:
        primary = f"{self.base_url}/{path.lstrip('/')}"
        candidates = [primary]
        if "localhost" in self.base_url:
            candidates.append(f"{self.base_url.replace('localhost', '127.0.0.1')}/{path.lstrip('/')}")
        elif "127.0.0.1" in self.base_url:
            candidates.append(f"{self.base_url.replace('127.0.0.1', 'localhost')}/{path.lstrip('/')}")
        return candidates

    def health_check(self) -> Dict[str, Any]:
        """Calls GET /health."""
        for url in self._get_candidate_urls("health"):
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    return resp.json()
                return {"status": "degraded", "mongodb": False, "embedding_service": False}
            except Exception as e:
                logger.debug(f"Health check failed for {url}: {e}")
                continue
        return {"status": "unavailable", "mongodb": False, "embedding_service": False}

    def ask_question(
        self,
        question: str,
        top_k: int = 5,
        retrieval_mode: str = "hybrid",
        category: Optional[str] = None,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calls POST /ask."""
        payload = {
            "question": question.strip(),
            "top_k": top_k,
            "retrieval_mode": retrieval_mode,
            "category": category,
            "source": source
        }
        last_exc = None
        for url in self._get_candidate_urls("ask"):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_exc = e
                continue
        if last_exc:
            raise last_exc
        raise requests.ConnectionError("Could not connect to /ask")

    def compare_documents(self, doc_a_id: str, doc_b_id: str) -> Dict[str, Any]:
        """Calls POST /compare."""
        payload = {
            "document_a_id": doc_a_id.strip(),
            "document_b_id": doc_b_id.strip()
        }
        last_exc = None
        for url in self._get_candidate_urls("compare"):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_exc = e
                continue
        if last_exc:
            raise last_exc
        raise requests.ConnectionError("Could not connect to /compare")

    def get_document(self, document_id: str) -> Dict[str, Any]:
        """Calls GET /document/{document_id}."""
        last_exc = None
        for url in self._get_candidate_urls(f"document/{document_id.strip()}"):
            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_exc = e
                continue
        if last_exc:
            raise last_exc
        raise requests.ConnectionError(f"Could not fetch document {document_id}")

    def get_document_versions(self, document_id: str) -> Dict[str, Any]:
        """Calls GET /document/{document_id}/versions."""
        last_exc = None
        for url in self._get_candidate_urls(f"document/{document_id.strip()}/versions"):
            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_exc = e
                continue
        if last_exc:
            raise last_exc
        raise requests.ConnectionError(f"Could not fetch versions for {document_id}")

    def get_latest(
        self,
        source: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Calls GET /latest."""
        params: Dict[str, Any] = {"limit": limit}
        if source:
            params["source"] = source
        if category:
            params["category"] = category
        last_exc = None
        for url in self._get_candidate_urls("latest"):
            try:
                resp = requests.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_exc = e
                continue
        if last_exc:
            raise last_exc
        raise requests.ConnectionError("Could not fetch latest documents")

    def search_documents(
        self,
        query: str,
        top_k: int = 10,
        retrieval_mode: str = "hybrid",
        category: Optional[str] = None,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calls POST /search."""
        payload = {
            "query": query.strip(),
            "top_k": top_k,
            "retrieval_mode": retrieval_mode,
            "category": category,
            "source": source
        }
        last_exc = None
        for url in self._get_candidate_urls("search"):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_exc = e
                continue
        if last_exc:
            raise last_exc
        raise requests.ConnectionError("Could not execute search")
