"""
Unit Tests for Content Hash Calculation & Ingestion Hashing (Phase 46).
"""

import pytest
from app.ingestion.pipeline import compute_content_hash


def test_compute_content_hash_deterministic():
    text1 = "SEBI circular on investment advisers dated 2024."
    text2 = "SEBI circular on investment advisers dated 2024."
    hash1 = compute_content_hash(text1)
    hash2 = compute_content_hash(text2)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex string


def test_compute_content_hash_whitespace_insensitivity():
    text1 = "SEBI circular on\n  investment advisers   dated 2024."
    text2 = "SEBI circular on investment advisers dated 2024."
    assert compute_content_hash(text1) == compute_content_hash(text2)


def test_compute_content_hash_different_content():
    text1 = "SEBI circular on investment advisers 2020."
    text2 = "SEBI circular on investment advisers 2024."
    assert compute_content_hash(text1) != compute_content_hash(text2)
