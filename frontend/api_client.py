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
    """HTTP client communicating with the RegIntel FastAPI backend."""

    def __init__(self, base_url: Optional[str] = None, timeout: int = 45):
        self.base_url = (base_url or FASTAPI_BASE_URL).rstrip("/")
        self.timeout = timeout

    def health_check(self) -> Dict[str, Any]:
        """Calls GET /health."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            if resp.status_code == 200:
                return resp.json()
            return {"status": "degraded", "mongodb": False, "embedding_service": False}
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
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
        resp = requests.post(f"{self.base_url}/ask", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def compare_documents(self, doc_a_id: str, doc_b_id: str) -> Dict[str, Any]:
        """Calls POST /compare."""
        payload = {
            "document_a_id": doc_a_id.strip(),
            "document_b_id": doc_b_id.strip()
        }
        resp = requests.post(f"{self.base_url}/compare", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_document(self, document_id: str) -> Dict[str, Any]:
        """Calls GET /document/{document_id}."""
        resp = requests.get(f"{self.base_url}/document/{document_id.strip()}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_document_versions(self, document_id: str) -> Dict[str, Any]:
        """Calls GET /document/{document_id}/versions."""
        resp = requests.get(f"{self.base_url}/document/{document_id.strip()}/versions", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

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
        resp = requests.get(f"{self.base_url}/latest", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

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
        resp = requests.post(f"{self.base_url}/search", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
