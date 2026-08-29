"""
Unit & Integration Tests for RegIntel FastAPI Endpoints.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.responses import AskResponse, SourceCitationResponse

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "mongodb" in data
    assert "embedding_service" in data
    assert data["status"] in {"ok", "degraded", "unavailable"}


def test_search_endpoint_validation():
    # Empty query fails validation
    resp = client.post("/search", json={"query": "   ", "top_k": 5})
    assert resp.status_code == 422


def test_search_endpoint_valid():
    resp = client.post("/search", json={"query": "Investment Adviser", "top_k": 3, "retrieval_mode": "bm25"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "Investment Adviser"
    assert "results" in data
    assert len(data["results"]) <= 3


def test_ask_endpoint_validation():
    # Too short question
    resp = client.post("/ask", json={"question": "hi"})
    assert resp.status_code == 422


@patch("app.api.routes_rag.get_rag_pipeline")
def test_ask_endpoint_mocked_success(mock_get_pipeline):
    mock_pipeline = MagicMock()
    mock_response = MagicMock()
    mock_response.answer = "Investment Advisers must keep records for 8 years [1]."
    mock_response.sources = [
        MagicMock(
            source_id=1,
            chunk_id="c1",
            document_id="d1",
            source="SEBI",
            title="Master Circular for IAs",
            section="Records",
            published_date="2024-05-15",
            effective_date="2024-05-15",
            url="https://sebi.gov.in/circ.html",
            score=0.95
        )
    ]
    mock_response.query_intent = MagicMock(
        query_type="factual",
        time_intent="none",
        source="SEBI",
        category="Investment Adviser",
        document_type="Circular",
        circular_number=None,
        is_comparison=False
    )
    mock_response.sufficient_evidence = True
    mock_pipeline.answer.return_value = mock_response
    mock_get_pipeline.return_value = mock_pipeline

    resp = client.post("/ask", json={"question": "What is the record retention period for IAs?", "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert "8 years" in data["answer"]
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source_id"] == 1


def test_compare_endpoint_missing_document():
    resp = client.post("/compare", json={"document_a_id": "nonexistent_a", "document_b_id": "nonexistent_b"})
    assert resp.status_code == 404


def test_document_endpoint_not_found():
    resp = client.get("/document/unknown_doc_id_12345")
    assert resp.status_code == 404


def test_latest_documents_endpoint():
    resp = client.get("/latest?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 5
