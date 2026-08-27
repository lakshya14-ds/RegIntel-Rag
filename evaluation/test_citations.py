"""
Citation and Grounding Validation Test Script.

Validates citation integrity, bracketed index mapping, and out-of-bounds detection.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval.mongodb_vector import RetrievedChunk
from app.rag.citations import CitationManager, SourceCitation


def test_citation_integrity():
    chunks = [
        RetrievedChunk(
            chunk_id="chk_1",
            document_id="doc_1",
            title="SEBI Master Circular for IA",
            content="Qualification requirements: Postgraduate in finance.",
            section="2. Qualifications",
            source="SEBI",
            url="https://sebi.gov.in/ia.html",
            score=0.88
        ),
        RetrievedChunk(
            chunk_id="chk_2",
            document_id="doc_1",
            title="SEBI Master Circular for IA",
            content="Fee cap is specified under Regulation 15A.",
            section="3. Fees",
            source="SEBI",
            url="https://sebi.gov.in/ia.html",
            score=0.81
        )
    ]

    print("\n" + "=" * 55)
    print("Citation System Verification")
    print("=" * 55)

    # Test 1: Valid citations
    ans1 = "Investment advisers need postgraduate degrees [1] and are subject to fee caps [2]."
    cites1, valid1, inv1 = CitationManager.validate_answer_citations(ans1, chunks)
    print(f"Test 1 (Valid IDs [1, 2]): valid={valid1}, invalid_ids={inv1}, citations_count={len(cites1)}")
    assert valid1 is True

    # Test 2: Invalid citation [99]
    ans2 = "Fee cap is regulated [2] and bonus rule applies [99]."
    cites2, valid2, inv2 = CitationManager.validate_answer_citations(ans2, chunks)
    print(f"Test 2 (Invalid ID [99]): valid={valid2}, invalid_ids={inv2}, citations_count={len(cites2)}")
    assert valid2 is False
    assert inv2 == [99]

    # Test 3: Sanitize invalid citations
    sanitized = CitationManager.sanitize_invalid_citations(ans2, max_valid_id=len(chunks))
    print(f"Sanitized answer: '{sanitized}'")
    assert "[99]" not in sanitized
    assert "[2]" in sanitized

    print("\nAll Citation Integrity Tests Passed Successfully!\n")


if __name__ == "__main__":
    test_citation_integrity()
