"""
Unit Tests for Connector REST API Endpoints (Phases 66–69).

Tests:
- GET /api/connectors
- GET /api/connectors/sources
- GET /api/connectors/health
- GET /api/connectors/runs
- POST /api/connectors/{authority}/run
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_connectors(client: TestClient):
    resp = client.get("/api/connectors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    codes = [d["code"] for d in data]
    assert "SEBI" in codes
    assert "RBI" in codes
    assert "IRDAI" in codes
    assert "PFRDA" in codes
    assert "IFSCA" in codes


def test_get_connector_sources(client: TestClient):
    resp = client.get("/api/connectors/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 5

    # Filter by authority
    rbi_resp = client.get("/api/connectors/sources?authority=RBI")
    assert rbi_resp.status_code == 200
    rbi_data = rbi_resp.json()
    assert all(d["authority"] == "RBI" for d in rbi_data)


def test_get_connector_health(client: TestClient):
    resp = client.get("/api/connectors/health")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    auth_names = [d["authority"] for d in data]
    for auth in ["SEBI", "RBI", "IRDAI", "PFRDA", "IFSCA"]:
        assert auth in auth_names


def test_get_connector_runs(client: TestClient):
    resp = client.get("/api/connectors/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_trigger_connector_run(client: TestClient):
    resp = client.post(
        "/api/connectors/RBI/run",
        json={"limit": 2, "dry_run": True, "force": False}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["authority"] == "RBI"
    assert data["status"] == "RUNNING"
    assert data["run_id"].startswith("RUN_RBI_")


def test_trigger_invalid_connector(client: TestClient):
    resp = client.post(
        "/api/connectors/INVALID_AUTH/run",
        json={"limit": 2}
    )
    assert resp.status_code == 404
