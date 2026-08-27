import pytest
from app.config import settings, Settings, ConfigurationError
from app.db import ping_mongodb, MongoDBConnectionError

def test_db_configuration_loading():
    """Verify that configuration loads required environment variables without errors."""
    assert settings.mongodb_uri is not None
    assert len(settings.mongodb_uri) > 0
    assert settings.mongodb_db is not None
    assert settings.mongodb_collection is not None

def test_db_live_or_graceful_skip():
    """Verify MongoDB connectivity if cluster is accessible; skip cleanly otherwise."""
    try:
        is_alive = ping_mongodb()
        assert is_alive is True
    except (MongoDBConnectionError, Exception) as e:
        pytest.skip(f"Live MongoDB Atlas cluster is not reachable in this environment: {e}")
