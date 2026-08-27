import os
import pytest
from unittest.mock import patch, MagicMock
from app.config import Settings, ConfigurationError
from app.db import MongoDBManager, MongoDBConnectionError

def test_settings_validation_missing_uri():
    with pytest.raises(ConfigurationError):
        Settings(mongodb_uri="")

def test_settings_load_valid():
    s = Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_db="test_db",
        mongodb_collection="test_coll"
    )
    assert s.mongodb_uri == "mongodb://localhost:27017"
    assert s.mongodb_db == "test_db"
    assert s.mongodb_collection == "test_coll"

def test_mongodb_ping_success():
    with patch("app.db.MongoClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client_cls.return_value = mock_client

        mgr = MongoDBManager(uri="mongodb://localhost:27017")
        assert mgr.ping() is True
        mock_client.admin.command.assert_called_with("ping")

def test_mongodb_ping_failure():
    with patch("app.db.MongoClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = Exception("Connection timeout")
        mock_client_cls.return_value = mock_client

        mgr = MongoDBManager(uri="mongodb://localhost:27017")
        with pytest.raises(MongoDBConnectionError):
            mgr.ping()
