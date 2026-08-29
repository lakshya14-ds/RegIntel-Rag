"""Integration tests for Docker backend health endpoint and readiness (Phase 34.7 & 35.7)."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_docker_healthcheck_endpoint_status():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded", "unavailable")
    assert "version" in data
    assert "environment" in data


def test_docker_backend_route_readiness():
    resp = client.get("/latest?limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
