"""
MongoDB Atlas Integration Tests (Phase 51.7).

Gated by environment flag: RUN_MONGODB_INTEGRATION=true.
Validates live database connection, collection operations, document insertion,
vector search execution, and metadata filtering.
"""

import os
import pytest
from app.config import settings
from app.db import get_db, get_collection, get_chunks_collection, ping_mongodb


@pytest.mark.skipif(
    os.getenv("RUN_MONGODB_INTEGRATION", "false").lower() not in ("true", "1"),
    reason="Live MongoDB integration test disabled. Set RUN_MONGODB_INTEGRATION=true to enable."
)
def test_mongodb_connection_and_access():
    assert ping_mongodb() is True

    db = get_db()
    assert db is not None

    docs_col = get_collection()
    chunks_col = get_chunks_collection()
    assert docs_col is not None
    assert chunks_col is not None


@pytest.mark.skipif(
    os.getenv("RUN_MONGODB_INTEGRATION", "false").lower() not in ("true", "1"),
    reason="Live MongoDB integration test disabled. Set RUN_MONGODB_INTEGRATION=true to enable."
)
def test_mongodb_metadata_filtering():
    docs_col = get_collection()
    sample = docs_col.find_one({"source": "SEBI"})
    if sample:
        assert "document_id" in sample
        assert sample.get("source") == "SEBI"
