import uuid
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.requests import AskRequest, SearchRequest, CompareRequest
from app.schemas.responses import (
    AskResponse,
    SourceCitationResponse,
    QueryIntentResponse,
    SearchResponse,
    SearchItemResponse,
    CompareResponse,
    DocumentMetadataResponse,
    SectionChangeResponse,
    EvidenceSourceResponse
)
from app.rag.pipeline import RAGPipeline
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.mongodb_vector import MongoDBVectorRetriever
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.reranker import LocalReranker
from app.change_detection.document_comparator import DocumentComparator
from app.observability.langfuse_tracer import langfuse_tracer
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
def ask_regulatory_question(req: AskRequest, request: Request = None) -> AskResponse:
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
        
        # Extract or generate correlation Request ID
        req_id = None
        if request and hasattr(request, "headers"):
            req_id = request.headers.get("X-Request-ID")
        if not req_id:
            req_id = f"req-{uuid.uuid4().hex[:12]}"

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
            filter_dict=filter_dict if filter_dict else None,
            request_id=req_id
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
                "request_id": req_id,
                "retrieval_mode": req.retrieval_mode,
                "retrieved_count": len(rag_res.sources),
                "sufficient_evidence": rag_res.sufficient_evidence,
                "provider": rag_res.llm_provider,
                "model": rag_res.llm_model,
                "fallback_used": rag_res.fallback_used
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
def search_documents(req: SearchRequest, request: Request = None) -> SearchResponse:
    """
    Direct candidate retrieval without LLM answer generation.
    Supports 'hybrid', 'vector', 'bm25', and 'hybrid_reranked'.
    """
    req_id = None
    if request and hasattr(request, "headers"):
        req_id = request.headers.get("X-Request-ID")
    if not req_id:
        req_id = f"search-{uuid.uuid4().hex[:12]}"

    mode = req.retrieval_mode or "hybrid"
    limit = req.top_k or 10

    with langfuse_tracer.start_trace(
        name="regintel.search",
        request_id=req_id,
        metadata={"query": req.query[:150], "retrieval_mode": mode, "top_k": limit}
    ) as trace:
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
def compare_documents(req: CompareRequest, request: Request = None) -> CompareResponse:
    """
    Direct structural and semantic comparison between two regulatory documents:
    - Resolves chronology (Older vs. Newer) with confidence scoring
    - Aligns sections via 4-tier structural matching
    - Classifies changes (ADDED, REMOVED, MODIFIED, UNCHANGED)
    - Synthesizes section compliance impact summaries using LLM
    - Maps exact evidence sources (old_source, new_source)
    """
    req_id = None
    if request and hasattr(request, "headers"):
        req_id = request.headers.get("X-Request-ID")
    if not req_id:
        req_id = f"comp-{uuid.uuid4().hex[:12]}"

    with langfuse_tracer.start_trace(
        name="regintel.compare",
        request_id=req_id,
        metadata={"document_a_id": req.document_a_id, "document_b_id": req.document_b_id}
    ) as trace:
        try:
            comparator = get_document_comparator()
            report = comparator.compare_documents(
                document_a_id=req.document_a_id,
                document_b_id=req.document_b_id,
                generate_summaries=True
            )

            if report.status == "ERROR":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND if "not found" in (report.message or "").lower() else status.HTTP_400_BAD_REQUEST,
                    detail=report.message or "Comparison failed."
                )

            def _to_meta_resp(d: dict, fallback_id: str) -> DocumentMetadataResponse:
                return DocumentMetadataResponse(
                    document_id=d.get("document_id", fallback_id),
                    title=d.get("title"),
                    source=d.get("source", "SEBI"),
                    category=d.get("category"),
                    document_type=d.get("document_type"),
                    circular_number=d.get("circular_number"),
                    published_date=d.get("published_date"),
                    effective_date=d.get("effective_date"),
                    status=d.get("status", "unknown"),
                    url=d.get("url", ""),
                    content_hash=d.get("content_hash")
                )

            older_meta = _to_meta_resp(report.older_document, req.document_a_id)
            newer_meta = _to_meta_resp(report.newer_document, req.document_b_id)

            changes_out: List[SectionChangeResponse] = []
            for idx, ch in enumerate(report.changes, start=1):
                old_src_resp = None
                if ch.old_source:
                    old_src_resp = EvidenceSourceResponse(
                        document_id=ch.old_source.document_id,
                        section_id=ch.old_source.section_id,
                        heading=ch.old_source.heading,
                        section_number=ch.old_source.section_number,
                        url=ch.old_source.url,
                        published_date=ch.old_source.published_date
                    )

                new_src_resp = None
                if ch.new_source:
                    new_src_resp = EvidenceSourceResponse(
                        document_id=ch.new_source.document_id,
                        section_id=ch.new_source.section_id,
                        heading=ch.new_source.heading,
                        section_number=ch.new_source.section_number,
                        url=ch.new_source.url,
                        published_date=ch.new_source.published_date
                    )

                changes_out.append(SectionChangeResponse(
                    section_index=idx,
                    section=ch.section,
                    heading=ch.heading,
                    change_type=ch.change_type,
                    substantive_change=ch.substantive_change,
                    category=ch.modification_category or "GENERAL",
                    modification_category=ch.modification_category,
                    previous_text=ch.previous_text,
                    current_text=ch.current_text,
                    summary=ch.summary or "",
                    old_requirement=ch.old_requirement,
                    new_requirement=ch.new_requirement,
                    compliance_impact=ch.impact,
                    impact=ch.impact,
                    similarity_score=1.0 if ch.change_type == "UNCHANGED" else 0.0,
                    evidence=ch.evidence,
                    old_source=old_src_resp,
                    new_source=new_src_resp
                ))

            counts = report.summary_counts
            return CompareResponse(
                status=report.status,
                message=report.message,
                document_a=older_meta,
                document_b=newer_meta,
                older_document=older_meta,
                newer_document=newer_meta,
                document_order_confidence=report.document_order_confidence,
                version_relationship=report.version_relationship,
                relationship_confidence=report.relationship_confidence,
                summary=report.executive_summary,
                executive_summary=report.executive_summary,
                key_changes=report.key_changes,
                total_changes=len(changes_out),
                added_count=counts.get("added", 0),
                removed_count=counts.get("removed", 0),
                modified_count=counts.get("modified", 0),
                unchanged_count=counts.get("unchanged", 0),
                summary_counts=counts,
                statistics=report.statistics,
                changes=changes_out,
                cached=report.cached
            )

        except HTTPException:
            raise
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
        except Exception as e:
            logger.error(f"Error in /compare: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to execute document comparison."
            )
