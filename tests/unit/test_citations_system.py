import pytest
from app.retrieval.mongodb_vector import RetrievedChunk
from app.rag.citations import CitationManager, extract_citation_indices, SourceCitation


@pytest.fixture
def mock_chunks():
    return [
        RetrievedChunk(
            chunk_id="chk_1",
            document_id="doc_1",
            title="SEBI Master Circular 2024",
            content="Qualification details.",
            section="2. Qualifications",
            source="SEBI",
            url="https://sebi.gov.in/circ.html",
            score=0.88
        ),
        RetrievedChunk(
            chunk_id="chk_2",
            document_id="doc_1",
            title="SEBI Master Circular 2024",
            content="Record keeping requirements.",
            section="4. Records",
            source="SEBI",
            url="https://sebi.gov.in/circ.html",
            score=0.79
        )
    ]


def test_extract_citation_indices_various_formats():
    assert extract_citation_indices("Rule 1 applies [1].") == {1}
    assert extract_citation_indices("Both rules [1, 2] are active.") == {1, 2}
    assert extract_citation_indices("Range [1-2] cited.") == {1, 2}
    assert extract_citation_indices("No bracket citations here.") == set()


def test_validate_answer_citations_valid(mock_chunks):
    answer = "Investment advisers need qualifications [1] and maintain records [2]."
    citations, is_valid, invalid_ids = CitationManager.validate_answer_citations(answer, mock_chunks)

    assert is_valid is True
    assert len(invalid_ids) == 0
    assert len(citations) == 2
    assert citations[0].source_id == 1
    assert citations[1].source_id == 2


def test_validate_answer_citations_invalid_detected(mock_chunks):
    answer = "Qualifications needed [1], but fake rule cited [99]."
    citations, is_valid, invalid_ids = CitationManager.validate_answer_citations(answer, mock_chunks)

    assert is_valid is False
    assert invalid_ids == [99]
    assert len(citations) == 1
    assert citations[0].source_id == 1


def test_sanitize_invalid_citations():
    text = "Regulation requires compliance [1] and [99]."
    sanitized = CitationManager.sanitize_invalid_citations(text, max_valid_id=2)

    assert "[99]" not in sanitized
    assert "[1]" in sanitized
