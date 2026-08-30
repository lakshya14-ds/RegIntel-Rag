"""
End-to-End RAG Workflow Test (Phase 51.11).

Tests the complete flow:
Query -> API -> Query Analysis -> Dense Embedding -> Vector/BM25 Search ->
Hybrid Merging -> BGE Cross-Encoder Reranking -> Context Construction ->
LLM Generation -> Citation Verification -> Final Grounded Response.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.retrieval.mongodb_vector import RetrievedChunk


@pytest.fixture
def api_client():
    return TestClient(app)


def test_e2e_rag_ask_full_workflow(api_client):
    mock_candidates = [
        RetrievedChunk(
            chunk_id="sebi_ia_chunk_001",
            document_id="sebi_ia_master_circular_2024",
            title="SEBI Master Circular for Investment Advisers",
            section="Qualification and Certification Requirements",
            content="An individual investment adviser or principal officer must have a postgraduate degree and NISM certification.",
            score=0.92,
            source="SEBI",
            category="Investment Adviser",
            document_type="Master Circular",
            published_date="2024-05-24",
            effective_date="2024-05-24",
            url="https://www.sebi.gov.in/legal/master-circulars/may-2024/ia.html"
        ),
        RetrievedChunk(
            chunk_id="sebi_ia_chunk_002",
            document_id="sebi_ia_master_circular_2024",
            title="SEBI Master Circular for Investment Advisers",
            section="Maintenance of Records",
            content="Investment advisers shall maintain records of client agreements and risk profiles for a minimum of 8 years.",
            score=0.88,
            source="SEBI",
            category="Investment Adviser",
            document_type="Master Circular",
            published_date="2024-05-24",
            effective_date="2024-05-24",
            url="https://www.sebi.gov.in/legal/master-circulars/may-2024/ia.html"
        )
    ]

    with patch("app.rag.pipeline.RAGPipeline.retrieve_candidates", return_value=mock_candidates):
        with patch("app.llm.gemini_provider.GeminiProvider.generate") as mock_gen:
            mock_gen.return_value = MagicMock(
                text="Investment advisers must hold NISM certification [1] and maintain client records for 8 years [2].",
                provider="gemini",
                model="models/gemini-flash-lite-latest",
                latency_ms=350.0,
                input_tokens=180,
                output_tokens=35
            )

            payload = {
                "question": "What are the qualification and record keeping requirements for Investment Advisers?",
                "retrieval_mode": "hybrid",
                "top_k": 5
            }

            response = api_client.post("/ask", json=payload, headers={"X-Request-ID": "e2e-test-req-001"})

            assert response.status_code == 200
            data = response.json()

            # Verify response schema & content
            assert "answer" in data
            assert "NISM certification" in data["answer"]
            assert data["sufficient_evidence"] is True
            assert len(data["sources"]) == 2
            assert data["sources"][0]["chunk_id"] == "sebi_ia_chunk_001"
            assert data["sources"][1]["chunk_id"] == "sebi_ia_chunk_002"
            assert response.headers.get("X-Request-ID") == "e2e-test-req-001"
