"""
Citation Validation Regression Tests (Phase 51.17).

Verifies:
1. Valid citations [1], [2] are preserved and mapped to retrieved chunks.
2. Hallucinated / out-of-range citations (e.g. [99]) are detected and invalidated.
3. Citation sanitizer strips invalid tags.
"""

import pytest
from app.rag.citations import CitationManager
from app.retrieval.mongodb_vector import RetrievedChunk


def test_citation_extraction_and_mapping():
    chunks = [
        RetrievedChunk(chunk_id="c1", document_id="d1", title="T1", content="Fee norm", score=0.9, source="SEBI", published_date="2024-01-01", url=""),
        RetrievedChunk(chunk_id="c2", document_id="d2", title="T2", content="Audit norm", score=0.8, source="SEBI", published_date="2024-01-01", url="")
    ]

    llm_output = "Fees are capped at 2.5% [1]. Annual audit is mandatory [2]."
    sources, is_valid, invalid_ids = CitationManager.validate_answer_citations(llm_output, chunks)

    assert is_valid is True
    assert len(sources) == 2
    assert sources[0].source_id == 1
    assert sources[0].chunk_id == "c1"
    assert sources[1].source_id == 2
    assert sources[1].chunk_id == "c2"


def test_citation_out_of_range_detected_and_sanitized():
    chunks = [
        RetrievedChunk(chunk_id="c1", document_id="d1", title="T1", content="Fee norm", score=0.9, source="SEBI", published_date="2024-01-01", url="")
    ]

    # Model hallucinates citation [99]
    llm_output = "Fees are capped at 2.5% [1] and penalty is 1 Crore [99]."
    sources, is_valid, invalid_ids = CitationManager.validate_answer_citations(llm_output, chunks)

    assert is_valid is False
    assert 99 in invalid_ids
    assert len(sources) == 1
    assert sources[0].source_id == 1

    sanitized = CitationManager.sanitize_invalid_citations(llm_output, max_valid_id=len(chunks))
    assert "[1]" in sanitized
    assert "[99]" not in sanitized
