"""
Performance & Latency Benchmark Tests (Phase 51.22).

Lightweight local micro-benchmarks measuring latency profiles across:
1. BM25 sparse keyword retrieval
2. Hybrid RRF score fusion
3. Full RAG pipeline execution
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from app.retrieval.bm25 import BM25Retriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.mongodb_vector import RetrievedChunk
from app.ingestion.models import DocumentChunk
from app.rag.pipeline import RAGPipeline


@pytest.fixture
def sample_corpus():
    return [
        DocumentChunk(
            chunk_id=f"chk_{i}",
            document_id=f"doc_{i % 5}",
            chunk_index=i,
            title=f"Circular {i}",
            section=f"Section {i}",
            content=f"Regulatory clause content regarding investment compliance requirement {i}.",
            token_count=25,
            source="SEBI",
            published_date="2024-05-24",
            url=f"https://sebi.gov.in/doc{i}.html"
        )
        for i in range(20)
    ]


@pytest.fixture
def sample_retrieved_chunks():
    return [
        RetrievedChunk(
            chunk_id=f"chk_{i}",
            document_id=f"doc_{i % 5}",
            title=f"Circular {i}",
            section=f"Section {i}",
            content=f"Regulatory clause content regarding investment compliance requirement {i}.",
            score=0.85 - (i * 0.01),
            source="SEBI",
            published_date="2024-05-24",
            url=f"https://sebi.gov.in/doc{i}.html"
        )
        for i in range(20)
    ]


def test_bm25_search_latency(sample_corpus):
    bm25 = BM25Retriever()
    bm25.build_index(sample_corpus)

    t0 = time.perf_counter()
    results = bm25.search("investment compliance requirement", top_k=5)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert len(results) <= 5
    assert elapsed_ms < 50.0  # Under 50ms for in-memory corpus


def test_hybrid_fusion_latency(sample_retrieved_chunks):
    hybrid = HybridRetriever(rrf_k=60)

    t0 = time.perf_counter()
    fused = hybrid._fuse_rrf(vector_results=sample_retrieved_chunks[:10], bm25_results=sample_retrieved_chunks[5:15])
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert len(fused) > 0
    assert elapsed_ms < 15.0  # Under 15ms for fusion logic


def test_rag_pipeline_mocked_latency(sample_retrieved_chunks):
    pipeline = RAGPipeline(enable_reranker=False)

    with patch.object(pipeline, "retrieve_candidates", return_value=sample_retrieved_chunks[:5]):
        with patch.object(pipeline.generator, "generate_answer", return_value={
            "answer": "Compliant [1].",
            "sources": [{"source_id": 1, "chunk_id": "chk_0", "document_id": "doc_0", "title": "Circular 0", "score": 0.9, "url": "", "published_date": "2024-01-01", "source": "SEBI"}]
        }):
            t0 = time.perf_counter()
            res = pipeline.ask("What is compliance requirement 0?")
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            assert res.sufficient_evidence is True
            assert elapsed_ms < 50.0  # Mocked RAG execution under 50ms
