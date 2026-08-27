import pytest
from unittest.mock import MagicMock

from app.retrieval.mongodb_vector import RetrievedChunk
from app.rag.prompts import build_rag_prompt, REGINTEL_SYSTEM_PROMPT
from app.rag.context import build_evidence_context
from app.rag.citations import validate_citations, extract_citation_indices, SourceCitation
from app.rag.generator import GeminiGenerator
from app.rag.pipeline import RAGPipeline, RAGResponse


@pytest.fixture
def mock_retrieved_chunks():
    return [
        RetrievedChunk(
            chunk_id="chk_001",
            document_id="doc_001",
            title="SEBI Master Circular for Investment Advisers",
            content="Investment Advisers must maintain minimum net worth of INR 50 Lakhs.",
            section="2. Eligibility",
            source="SEBI",
            category="Investment Adviser",
            published_date="2024-05-24",
            url="https://sebi.gov.in/circ1.html",
            score=0.82
        ),
        RetrievedChunk(
            chunk_id="chk_002",
            document_id="doc_001",
            title="SEBI Master Circular for Investment Advisers",
            content="Records must be maintained for 8 years.",
            section="4. Records",
            source="SEBI",
            category="Investment Adviser",
            published_date="2024-05-24",
            url="https://sebi.gov.in/circ1.html",
            score=0.76
        )
    ]


def test_build_rag_prompt():
    evidence = "SOURCE [1] Title: SEBI Circular\nContent: Some regulation content"
    question = "What is the rule?"
    prompt = build_rag_prompt(evidence, question)

    assert "RegIntel" in prompt
    assert "EVIDENCE:" in prompt
    assert question in prompt
    assert "Do not invent" in prompt


def test_build_evidence_context(mock_retrieved_chunks):
    context = build_evidence_context(mock_retrieved_chunks)
    assert "SOURCE [1]" in context
    assert "SOURCE [2]" in context
    assert "2. Eligibility" in context
    assert "INR 50 Lakhs" in context
    assert "embedding" not in context.lower()


def test_extract_citation_indices():
    text = "The net worth requirement is 50L [1] and records are kept for 8 years [2]. Extra info [1, 2]."
    indices = extract_citation_indices(text)
    assert indices == {1, 2}

    no_cite_text = "No citations here."
    assert extract_citation_indices(no_cite_text) == set()


def test_validate_citations(mock_retrieved_chunks):
    answer = "Investment advisers must have 50L net worth [1] and comply with non-existent rule [99]."
    citations = validate_citations(answer, mock_retrieved_chunks)

    assert len(citations) == 1
    assert citations[0].source_id == 1
    assert citations[0].title == "SEBI Master Circular for Investment Advisers"
    assert citations[0].score == 0.82


def test_rag_pipeline_insufficient_evidence(mock_retrieved_chunks):
    mock_retriever = MagicMock()
    # Return low score chunk (< 0.35 threshold)
    low_score_chunk = mock_retrieved_chunks[0].model_copy(update={"score": 0.10})
    mock_retriever.retrieve.return_value = [low_score_chunk]

    pipeline = RAGPipeline(
        retrieval_mode="vector",
        enable_reranker=False,
        vector_retriever=mock_retriever,
        min_score_threshold=0.35
    )
    response = pipeline.answer("Unknown question?")

    assert response.sufficient_evidence is False
    assert "could not find sufficient evidence" in response.answer
    assert len(response.sources) == 0


def test_rag_pipeline_successful_generation(mock_retrieved_chunks):
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = mock_retrieved_chunks

    mock_generator = MagicMock()
    mock_generator.generate_answer.return_value = {
        "answer": "Investment advisers require 50L net worth [1] and 8 years record keeping [2].",
        "sources": [
            {
                "source_id": 1,
                "chunk_id": "chk_001",
                "document_id": "doc_001",
                "source": "SEBI",
                "title": "SEBI Master Circular for Investment Advisers",
                "section": "2. Eligibility",
                "published_date": "2024-05-24",
                "effective_date": "N/A",
                "url": "https://sebi.gov.in/circ1.html",
                "score": 0.82
            },
            {
                "source_id": 2,
                "chunk_id": "chk_002",
                "document_id": "doc_001",
                "source": "SEBI",
                "title": "SEBI Master Circular for Investment Advisers",
                "section": "4. Records",
                "published_date": "2024-05-24",
                "effective_date": "N/A",
                "url": "https://sebi.gov.in/circ1.html",
                "score": 0.76
            }
        ]
    }

    pipeline = RAGPipeline(
        retrieval_mode="vector",
        enable_reranker=False,
        vector_retriever=mock_retriever,
        generator=mock_generator
    )
    response = pipeline.answer("What are the IA requirements?")

    assert response.sufficient_evidence is True
    assert "50L net worth" in response.answer
    assert len(response.sources) == 2
    assert response.top_score == 0.82
