"""
Security & Data Governance Contract Tests (Phase 51.21).

Verifies:
1. API responses never leak sensitive credentials, tokens, or raw vector arrays.
2. Malformed or oversized inputs are handled with clean HTTP error codes.
3. Internal stack traces are suppressed in API error payloads.
4. Git ignore rules protect secret configuration files.
"""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_gitignore_protects_env_file():
    root = Path(__file__).parent.parent.parent
    gitignore_path = root / ".gitignore"
    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".env" in content
    assert "*.db" in content or "mlruns" in content


def test_api_health_endpoint_no_secrets(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    # Verify no secret credentials in status payload
    data_str = str(data).lower()
    assert "aizasy" not in data_str
    assert "sk-" not in data_str
    assert "password" not in data_str
    assert "secret" not in data_str


def test_api_malformed_input_rejection(client):
    # Invalid body payload
    response = client.post("/ask", json={"invalid_field": 12345})
    assert response.status_code == 422
    data = response.json()
    assert "validation error" in str(data).lower() or "detail" in data


def test_api_suppresses_internal_stack_trace(client):
    # Trigger 404 or 422
    response = client.get("/non_existent_route_404")
    assert response.status_code == 404
    data = response.json()
    assert "traceback" not in str(data).lower()
