import pytest
from app.ingestion.models import DocumentChunk
from app.retrieval.bm25 import BM25Retriever, tokenize_regulatory_text


def test_tokenize_regulatory_text():
    raw_text = "Circular No. SEBI/HO/MIRSD/MIRSD-PoD-2/P/CIR/2024/56 applies to Regulation 15A and Clause 4.2."
    tokens = tokenize_regulatory_text(raw_text)

    assert "sebi/ho/mirsd/mirsd-pod-2/p/cir/2024/56" in tokens
    assert "15a" in tokens
    assert "4.2" in tokens
    assert "regulation" in tokens


def test_bm25_retriever_indexing_and_search():
    chunks = [
        DocumentChunk(
            chunk_id="chk_ia_01",
            document_id="doc_ia",
            chunk_index=0,
            token_count=20,
            title="Master Circular for Investment Advisers",
            content="Eligibility criteria for registered investment advisers under SEBI.",
            section="2. Eligibility",
            circular_number="SEBI/HO/MIRSD/2024/56",
            source="SEBI",
            category="Investment Adviser",
            url="https://sebi.gov.in/ia.html"
        ),
        DocumentChunk(
            chunk_id="chk_mf_01",
            document_id="doc_mf",
            chunk_index=0,
            token_count=25,
            title="Mutual Funds Overseas Investments",
            content="Framework for overseas investment by Mutual Funds in debt securities.",
            section="1. Framework",
            circular_number="SEBI/HO/IMD/2023/11",
            source="SEBI",
            category="Mutual Funds",
            url="https://sebi.gov.in/mf.html"
        )
    ]

    retriever = BM25Retriever()
    retriever.build_index(chunks)

    # Search for IA circular number
    results = retriever.search("SEBI/HO/MIRSD/2024/56", top_k=2)
    assert len(results) > 0
    assert results[0].chunk_id == "chk_ia_01"
    assert results[0].score > 0.0

    # Search for MF keyword
    mf_results = retriever.search("overseas mutual funds", top_k=2)
    assert len(mf_results) > 0
    assert mf_results[0].chunk_id == "chk_mf_01"


def test_bm25_retriever_empty_query():
    retriever = BM25Retriever()
    assert retriever.search("") == []
    assert retriever.search("   ") == []
