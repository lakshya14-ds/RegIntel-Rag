"""
RAG, Search, and Comparison API Routes for RegIntel FastAPI.
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, status

from app.schemas.requests import AskRequest, SearchRequest, CompareRequest
from app.schemas.responses import (
    AskResponse,
    SourceCitationResponse,
    QueryIntentResponse,
    SearchResponse,
    SearchItemResponse,
    CompareResponse,
    DocumentMetadataResponse,
    SectionChangeResponse
)
from app.rag.pipeline import RAGPipeline
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.mongodb_vector import MongoDBVectorRetriever
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.reranker import LocalReranker
from app.change_detection.document_comparator import DocumentComparator
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["RAG & Intelligence"])

# Lazy singleton service instances
_rag_pipeline: Optional[RAGPipeline] = None
_hybrid_retriever: Optional[HybridRetriever] = None
_document_comparator: Optional[DocumentComparator] = None


def get_rag_pipeline() -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline(enable_reranker=True)
    return _rag_pipeline


def get_hybrid_retriever() -> HybridRetriever:
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever()
    return _hybrid_retriever


def get_document_comparator() -> DocumentComparator:
    global _document_comparator
    if _document_comparator is None:
        _document_comparator = DocumentComparator()
    return _document_comparator


@router.post("/ask", response_model=AskResponse, summary="Ask Regulatory Intelligence Query")
def ask_regulatory_question(req: AskRequest) -> AskResponse:
    """
    Executes end-to-end grounded Regulatory RAG:
    - Query understanding & intent parsing
    - Hybrid vector + BM25 retrieval
    - Local cross-encoder neural reranking
    - Grounded Gemini answer generation
    - Deterministic source citation validation
    """
    try:
        pipeline = get_rag_pipeline()
        
        # Build optional metadata filter
        filter_dict = {}
        if req.category:
            filter_dict["category"] = req.category
        if req.source:
            filter_dict["source"] = req.source

        rag_res = pipeline.answer(
            question=req.question,
            candidate_k=req.top_k or 5,
            retrieval_mode=req.retrieval_mode or "hybrid",
            filter_dict=filter_dict if filter_dict else None
        )

        sources_out: List[SourceCitationResponse] = [
            SourceCitationResponse(
                source_id=s.source_id,
                chunk_id=s.chunk_id,
                document_id=s.document_id,
                source=s.source,
                title=s.title,
                section=s.section or "General",
                published_date=s.published_date or "N/A",
                effective_date=s.effective_date or "N/A",
                url=s.url,
                score=round(s.score, 4)
            )
            for s in rag_res.sources
        ]

        intent_out = None
        if rag_res.query_intent:
            qi = rag_res.query_intent
            intent_out = QueryIntentResponse(
                query_type=getattr(qi, "query_type", "general_search"),
                time_intent=getattr(qi, "time_intent", "none"),
                source=getattr(qi, "source", None),
                category=getattr(qi, "category", None),
                document_type=getattr(qi, "document_type", None),
                circular_number=getattr(qi, "circular_number", None),
                is_comparison=getattr(qi, "is_comparison", False)
            )

        debug_payload = None
        if settings.debug_mode:
            debug_payload = {
                "retrieval_mode": req.retrieval_mode,
                "retrieved_count": len(rag_res.sources),
                "sufficient_evidence": rag_res.sufficient_evidence
            }

        return AskResponse(
            answer=rag_res.answer,
            sources=sources_out,
            query_intent=intent_out,
            sufficient_evidence=rag_res.sufficient_evidence,
            debug_info=debug_payload
        )

    except ValueError as ve:
        logger.warning(f"Validation error in /ask: {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error executing /ask: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate regulatory response due to an internal server error."
        )


@router.post("/search", response_model=SearchResponse, summary="Multi-Method Document Search")
def search_documents(req: SearchRequest) -> SearchResponse:
    """
    Direct candidate retrieval without LLM answer generation.
    Supports 'hybrid', 'vector', 'bm25', and 'hybrid_reranked'.
    """
    try:
        filter_dict = {}
        if req.category:
            filter_dict["category"] = req.category
        if req.source:
            filter_dict["source"] = req.source

        retriever = get_hybrid_retriever()
        mode = req.retrieval_mode or "hybrid"
        limit = req.top_k or 10

        if mode == "vector":
            candidates = retriever.vector_retriever.retrieve(
                query_text=req.query,
                limit=limit,
                filter_dict=filter_dict if filter_dict else None
            )
        elif mode == "bm25":
            candidates = retriever.bm25_retriever.search(
                query=req.query,
                top_k=limit,
                filter_dict=filter_dict if filter_dict else None
            )
        elif mode == "hybrid_reranked":
            candidates = retriever.search(
                query=req.query,
                top_k=limit,
                candidate_k=limit * 2,
                filter_dict=filter_dict if filter_dict else None
            )
            reranker = LocalReranker()
            candidates = reranker.rerank(query=req.query, candidates=candidates, top_k=limit)
        else:  # hybrid
            candidates = retriever.search(
                query=req.query,
                top_k=limit,
                candidate_k=limit * 2,
                filter_dict=filter_dict if filter_dict else None
            )

        results: List[SearchItemResponse] = []
        for rank, c in enumerate(candidates, start=1):
            content_snippet = c.content[:280] + ("..." if len(c.content) > 280 else "")
            score_val = getattr(c, "reranker_score", None)
            if score_val is None:
                score_val = getattr(c, "hybrid_score", None)
            if score_val is None:
                score_val = getattr(c, "score", 0.0)

            results.append(SearchItemResponse(
                rank=rank,
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                title=c.title,
                section=c.section or "General",
                source=c.source or "SEBI",
                category=c.category,
                document_type=c.document_type,
                published_date=c.published_date,
                effective_date=c.effective_date,
                url=c.url,
                score=round(float(score_val), 4),
                content_snippet=content_snippet
            ))

        return SearchResponse(
            query=req.query,
            retrieval_mode=mode,
            total_results=len(results),
            results=results
        )

    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in /search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve regulatory search results."
        )


@router.post("/compare", response_model=CompareResponse, summary="Compare Two Regulatory Documents")
def compare_documents(req: CompareRequest) -> CompareResponse:
    """
    Direct structural comparison between two regulatory documents:
    - Aligns sections via heading normalization
    - Classifies changes (ADDED, REMOVED, MODIFIED, UNCHANGED)
    - Synthesizes section compliance impact summaries using LLM
    """
    try:
        comparator = get_document_comparator()
        report = comparator.compare(
            doc_a_id=req.document_a_id,
            doc_b_id=req.document_b_id,
            generate_summaries=True
        )

        doc_a_dict = report.get("document_a", {})
        doc_b_dict = report.get("document_b", {})

        doc_a_meta = DocumentMetadataResponse(
            document_id=doc_a_dict.get("document_id", req.document_a_id),
            title=doc_a_dict.get("title"),
            source=doc_a_dict.get("source", "SEBI"),
            category=doc_a_dict.get("category"),
            document_type=doc_a_dict.get("document_type"),
            circular_number=doc_a_dict.get("circular_number"),
            published_date=doc_a_dict.get("published_date"),
            effective_date=doc_a_dict.get("effective_date"),
            status=doc_a_dict.get("status", "unknown"),
            url=doc_a_dict.get("url", "")
        )

        doc_b_meta = DocumentMetadataResponse(
            document_id=doc_b_dict.get("document_id", req.document_b_id),
            title=doc_b_dict.get("title"),
            source=doc_b_dict.get("source", "SEBI"),
            category=doc_b_dict.get("category"),
            document_type=doc_b_dict.get("document_type"),
            circular_number=doc_b_dict.get("circular_number"),
            published_date=doc_b_dict.get("published_date"),
            effective_date=doc_b_dict.get("effective_date"),
            status=doc_b_dict.get("status", "unknown"),
            url=doc_b_dict.get("url", "")
        )

        counts = report.get("change_counts", {})
        changes_out: List[SectionChangeResponse] = []
        for ch in report.get("section_changes", []):
            changes_out.append(SectionChangeResponse(
                section_index=ch.get("section_index", 0),
                heading=ch.get("heading", ""),
                change_type=ch.get("change_type", "MODIFIED"),
                category=ch.get("category", "GENERAL"),
                summary=ch.get("summary", ""),
                compliance_impact=ch.get("compliance_impact"),
                similarity_score=ch.get("similarity_score"),
                evidence=ch.get("evidence")
            ))

        return CompareResponse(
            document_a=doc_a_meta,
            document_b=doc_b_meta,
            summary=report.get("summary", ""),
            total_changes=report.get("total_sections_analyzed", len(changes_out)),
            added_count=counts.get("ADDED", 0),
            removed_count=counts.get("REMOVED", 0),
            modified_count=counts.get("MODIFIED", 0),
            unchanged_count=counts.get("UNCHANGED", 0),
            changes=changes_out
        )

    except FileNotFoundError as fe:
        logger.warning(f"Document not found in /compare: {fe}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in /compare: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute document comparison."
        )
