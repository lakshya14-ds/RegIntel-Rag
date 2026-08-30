"""
Unit Tests for Chunk-Level Hashing (Phase 46).
"""

import pytest
from app.ingestion.pipeline import compute_content_hash
from app.ingestion.models import DocumentChunk


def test_chunk_content_hash_calculation():
    chunk_text = "Section 4.2: Investment advisers shall maintain client records for 5 years."
    c_hash = compute_content_hash(chunk_text)
    assert len(c_hash) == 64
    assert c_hash == compute_content_hash("Section 4.2: Investment advisers shall maintain client records for 5 years.")


def test_chunk_content_hash_sensitivity():
    chunk_text1 = "Section 4.2: Fee limit shall not exceed 2.5% of AUA."
    chunk_text2 = "Section 4.2: Fee limit shall not exceed 1.25% of AUA."
    hash1 = compute_content_hash(chunk_text1)
    hash2 = compute_content_hash(chunk_text2)
    assert hash1 != hash2
