"""
Unit Tests for Frontend API Client.
"""

import pytest
import requests
from unittest.mock import MagicMock, patch

from frontend.api_client import RegIntelAPIClient


@patch("frontend.api_client.requests.get")
def test_client_health_check(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "mongodb": True, "embedding_service": True}
    mock_get.return_value = mock_resp

    client = RegIntelAPIClient(base_url="http://localhost:8000")
    h = client.health_check()
    assert h["status"] == "ok"
    assert h["mongodb"] is True


@patch("frontend.api_client.requests.post")
def test_client_ask_question(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "answer": "Test answer",
        "sources": [],
        "sufficient_evidence": True
    }
    mock_post.return_value = mock_resp

    client = RegIntelAPIClient(base_url="http://localhost:8000")
    res = client.ask_question("What is the record keeping period?")
    assert res["answer"] == "Test answer"
    mock_post.assert_called_once()


@patch("frontend.api_client.requests.get")
def test_client_get_latest(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"document_id": "doc1", "title": "Circular 1"}]
    mock_get.return_value = mock_resp

    client = RegIntelAPIClient(base_url="http://localhost:8000")
    docs = client.get_latest(limit=5)
    assert len(docs) == 1
    assert docs[0]["document_id"] == "doc1"
