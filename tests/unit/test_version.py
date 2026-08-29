"""Unit tests for application version exposure (Phase 35.8)."""

from fastapi.testclient import TestClient
from app.config import settings
from app.main import app

client = TestClient(app)


def test_regintel_version_config():
    assert settings.regintel_version is not None
    assert len(settings.regintel_version) > 0


def test_health_endpoint_exposes_version():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert data["version"] == settings.regintel_version
    assert "status" in data
