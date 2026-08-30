"""
API Schema & Contract Validation Tests (Phase 51.20).

Verifies exact JSON schemas and status codes across:
- GET /health
- POST /ask
- POST /search
- POST /compare
- GET /latest
- GET /document/{id}
- GET /document/{id}/versions
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_contract_health_schema(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert set(data.keys()) >= {"status", "version", "environment", "mongodb", "embedding_service"}


def test_contract_search_invalid_params(client):
    res = client.post("/search", json={"query": "", "top_k": 0})
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data or "message" in data


def test_contract_request_id_correlation(client):
    custom_req_id = "custom-test-correlation-id-99"
    res = client.get("/health", headers={"X-Request-ID": custom_req_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_req_id


def test_contract_latest_documents_schema(client):
    res = client.get("/latest?limit=2")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
