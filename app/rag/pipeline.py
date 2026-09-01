"""
End-to-End RegIntel RAG Pipeline.

Coordinates:
Question -> Query Understanding (QueryAnalyzer)
         -> Metadata-Aware Hybrid Retrieval (Vector + BM25)
         -> Temporal Ranking (Latest/Current Logic)
         -> BGE Cross-Encoder Reranking
         -> Change Detection Engine ("What Changed?")
         -> Citation Integrity Validation -> Grounded Final Answer.
"""

import sys
import logging
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field

from app.retrieval.mongodb_vector import MongoDBVectorRetriever, RetrievedChunk
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.hybrid import HybridRetriever, HybridRetrievedChunk
from app.retrieval.reranker import LocalReranker, RerankedChunk
from app.retrieval.query_analyzer import QueryAnalyzer, QueryIntent, analyze_query
from app.retrieval.temporal import TemporalRanker, apply_temporal_ranking
from app.change_detection.detector import RegulatoryChangeDetector, ChangeReport
from app.llm import get_llm_provider, BaseLLMProvider
from app.rag.citations import CitationManager, SourceCitation

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

DEFAULT_MIN_SCORE_THRESHOLD = 0.20
DEFAULT_CANDIDATE_POOL = 20
DEFAULT_FINAL_TOP_K = 5


class RAGResponse(BaseModel):
    """Normalized structured response from the RegIntel RAG pipeline."""
    question: str
    answer: str
    sources: List[SourceCitation] = Field(default_factory=list)
    retrieved_chunks_count: int = 0
    top_score: float = 0.0
    retrieval_mode: str = "hybrid"
    reranker_used: bool = False
    query_intent: Optional[Dict[str, Any]] = None
    change_report: Optional[Dict[str, Any]] = None
    sufficient_evidence: bool = True
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    fallback_used: bool = False
    primary_provider: Optional[str] = None
    fallback_provider: Optional[str] = None

    def print_formatted(self):
        """Prints the answer and citation sources clearly formatted."""
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"

        def _safe(txt: str) -> str:
            return txt.encode(encoding, errors="replace").decode(encoding)

        print("\n" + "=" * 60)
        print("QUESTION:")
        print(_safe(self.question))
        print("=" * 60)

        if self.query_intent:
            q_src = self.query_intent.get("source") or "Any"
            q_cat = self.query_intent.get("category") or "General"
            q_time = self.query_intent.get("time_intent") or "none"
            q_type = self.query_intent.get("query_type") or "general_search"
            print(f"[Query Intent | Source: {q_src} | Category: {q_cat} | Time: {q_time.upper()} | Type: {q_type.upper()}]")

        print(f"[Retrieval Mode: {self.retrieval_mode.upper()} | Reranker: {'Enabled' if self.reranker_used else 'Disabled'}]")

        print("\nANSWER")
        print("-" * 60)
        print(_safe(self.answer))
        print("-" * 60)

        if self.sources:
            print("\nSOURCES")
            print("-" * 60)
            for s in self.sources:
                print(f"[{s.source_id}] {_safe(s.title)}")
                print(f"    Section   : {_safe(s.section)}")
                print(f"    Published : {s.published_date}")
                print(f"    Score     : {s.score:.4f}")
                print(f"    URL       : {s.url}")
                print()
        else:
            print("\nNo source citations attached.\n")


class RAGPipeline:
    """
    Production-grade Regulatory Intelligence RAG Pipeline with Query Understanding,
    Hybrid Search, Temporal Ranking, Cross-Encoder Reranking, and Change Detection.
    """

    def __init__(
        self,
        retrieval_mode: Literal["hybrid", "vector", "bm25"] = "hybrid",
        enable_reranker: bool = True,
        vector_retriever: Optional[MongoDBVectorRetriever] = None,
        bm25_retriever: Optional[BM25Retriever] = None,
        hybrid_retriever: Optional[HybridRetriever] = None,
        retriever: Optional[Any] = None,  # Backward compatibility alias
        reranker: Optional[LocalReranker] = None,
        generator: Optional[BaseLLMProvider] = None,
        query_analyzer: Optional[QueryAnalyzer] = None,
        change_detector: Optional[RegulatoryChangeDetector] = None,
        candidate_pool: int = DEFAULT_CANDIDATE_POOL,
        top_k: int = DEFAULT_FINAL_TOP_K,
        min_score_threshold: float = DEFAULT_MIN_SCORE_THRESHOLD
    ):
        self.retrieval_mode = retrieval_mode
        self.enable_reranker = enable_reranker
        self.candidate_pool = candidate_pool
        self.top_k = top_k
        self.min_score_threshold = min_score_threshold

        self.vector_retriever = vector_retriever or retriever or MongoDBVectorRetriever(default_top_k=candidate_pool)
        self.bm25_retriever = bm25_retriever or BM25Retriever()
        self.hybrid_retriever = hybrid_retriever or HybridRetriever(
            vector_retriever=self.vector_retriever,
            bm25_retriever=self.bm25_retriever,
            candidate_pool=candidate_pool
        )
        self.reranker = reranker or LocalReranker(enabled=enable_reranker)
        self.generator = generator or get_llm_provider()
        self.query_analyzer = query_analyzer or QueryAnalyzer()
        gen_client = getattr(self.generator, "_client", None) or getattr(getattr(self.generator, "primary", None), "_client", None)
        self.change_detector = change_detector or RegulatoryChangeDetector(generator_client=gen_client)

    def retrieve_candidates(
        self,
        question: str,
        mode: Optional[str] = None,
        candidate_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        query_intent: Optional[QueryIntent] = None,
        trace: Optional[Any] = None
    ) -> List[RetrievedChunk]:
        """Retrieves raw candidate chunks based on configured retrieval mode and metadata filters."""
        from app.observability.langfuse_tracer import langfuse_tracer, ErrorCategory
        from app.config import settings

        active_mode = (mode or self.retrieval_mode).lower()
        k = candidate_k or self.candidate_pool

        try:
            if active_mode == "vector":
                with langfuse_tracer.start_span(trace, name="query_embedding", span_type="embedding", metadata={"provider": settings.embedding_provider, "model": settings.embedding_model, "dimensions": settings.embedding_dimension, "task_type": "RETRIEVAL_QUERY"}):
                    pass
                with langfuse_tracer.start_span(trace, name="vector_search", span_type="retriever", metadata={"candidate_pool": k, "filter": filter_dict}) as span:
                    results = self.vector_retriever.retrieve(query_text=question, limit=k, filter_dict=filter_dict)
                    langfuse_tracer.update_span(span, metadata={"results_count": len(results), "top_score": results[0].score if results else 0.0})
                    return results

            elif active_mode == "bm25":
                with langfuse_tracer.start_span(trace, name="bm25_search", span_type="retriever", metadata={"candidate_pool": k, "filter": filter_dict}) as span:
                    results = self.bm25_retriever.search(query=question, top_k=k, filter_dict=filter_dict)
                    langfuse_tracer.update_span(span, metadata={"results_count": len(results), "top_score": results[0].score if results else 0.0})
                    return results

            else:
                # Hybrid
                with langfuse_tracer.start_span(trace, name="hybrid_retrieval", span_type="retriever", metadata={"candidate_pool": k, "vector_weight": getattr(self.hybrid_retriever, "vector_weight", 0.6), "bm25_weight": getattr(self.hybrid_retriever, "bm25_weight", 0.4)}) as hy_span:
                    with langfuse_tracer.start_span(trace, name="query_embedding", span_type="embedding", metadata={"provider": settings.embedding_provider, "model": settings.embedding_model, "dimensions": settings.embedding_dimension, "task_type": "RETRIEVAL_QUERY"}):
                        pass
                    with langfuse_tracer.start_span(trace, name="vector_search", span_type="retriever", metadata={"candidate_pool": k}):
                        pass
                    with langfuse_tracer.start_span(trace, name="bm25_search", span_type="retriever", metadata={"candidate_pool": k}):
                        pass
                    results = self.hybrid_retriever.search(
                        query=question,
                        top_k=k,
                        candidate_k=k,
                        filter_dict=filter_dict,
                        query_intent=query_intent
                    )
                    langfuse_tracer.update_span(hy_span, metadata={"candidates_merged": len(results), "top_score": results[0].score if results else 0.0})
                    return results

        except Exception as e:
            langfuse_tracer.record_error(trace, e, category=ErrorCategory.RETRIEVAL_ERROR)
            raise e

    def ask(self, *args, **kwargs) -> RAGResponse:
        """Ergonomic alias for answer()."""
        return self.answer(*args, **kwargs)

    def answer(
        self,
        question: str,
        mode: Optional[str] = None,
        enable_reranker: Optional[bool] = None,
        top_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        min_score_threshold: Optional[float] = None,
        request_id: Optional[str] = None,
        retrieval_mode: Optional[str] = None,
        candidate_k: Optional[int] = None,
        **kwargs
    ) -> RAGResponse:
        """
        Executes complete RAG workflow:
        Query Analysis -> Candidate Retrieval -> Temporal Adjustment -> Reranking -> Grounding Check -> Generation -> Citation Check
        """
        if not question or not question.strip():
            return RAGResponse(
                question="",
                answer="Question cannot be empty.",
                sufficient_evidence=False
            )

        active_mode = retrieval_mode or mode or self.retrieval_mode
        use_rerank = enable_reranker if enable_reranker is not None else self.enable_reranker
        final_k = top_k or candidate_k or self.top_k
        threshold = min_score_threshold if min_score_threshold is not None else self.min_score_threshold

        from app.observability.langfuse_tracer import langfuse_tracer, ErrorCategory
        from app.config import settings

        model_info = {}
        if hasattr(self.generator, "get_model_info") and callable(self.generator.get_model_info):
            try:
                res_info = self.generator.get_model_info()
                if isinstance(res_info, dict):
                    model_info = res_info
            except Exception:
                pass

        def _clean_str(val: Any) -> Optional[str]:
            if val is not None and isinstance(val, str) and val.strip():
                return val.strip()
            return None

        gen_model = _clean_str(model_info.get("model")) or getattr(settings, "gemini_generation_model", "models/gemini-flash-lite-latest")
        gen_prov = _clean_str(model_info.get("provider")) or getattr(settings, "llm_provider", "gemini")

        with langfuse_tracer.start_trace(
            name="regintel.ask",
            request_id=request_id or "req-default",
            metadata={
                "question": question[:200],
                "retrieval_mode": active_mode,
                "reranker_enabled": use_rerank,
                "llm_provider": gen_prov,
                "llm_model": gen_model
            }
        ) as trace:

            # 1. Query Understanding
            with langfuse_tracer.start_span(trace, name="query_analysis", span_type="tool", input_data=question) as span:
                intent: QueryIntent = self.query_analyzer.analyze(question.strip())
                langfuse_tracer.update_span(
                    span,
                    metadata={
                        "query_type": intent.query_type,
                        "time_intent": intent.time_intent,
                        "source": intent.source,
                        "category": intent.category,
                        "document_type": intent.document_type,
                        "is_comparison": getattr(intent, "is_comparison", intent.query_type in ("comparison", "change_analysis"))
                    }
                )
                logger.info(f"Processing query '{question}' | Intent: type={intent.query_type}, time={intent.time_intent}, cat={intent.category}")

            # 2. Check for Change Analysis Request
            if intent.query_type == "change_analysis":
                with langfuse_tracer.start_span(trace, name="change_detection", span_type="tool") as chg_span:
                    resp = self._handle_change_analysis_query(question, intent)
                    if resp.change_report:
                        cr = resp.change_report
                        langfuse_tracer.update_span(
                            chg_span,
                            metadata={
                                "status": cr.get("status"),
                                "total_changes": len(cr.get("changes", [])),
                                "previous_document": cr.get("previous_document", {}).get("title")
                            }
                        )
                    langfuse_tracer.update_trace(
                        trace,
                        output_data={"answer": resp.answer[:300]},
                        metadata={"status": "success", "evidence_count": len(resp.sources)}
                    )
                    return resp

            # 3. Retrieve candidates
            candidates: List[RetrievedChunk] = self.retrieve_candidates(
                question=question.strip(),
                mode=active_mode,
                candidate_k=self.candidate_pool,
                filter_dict=filter_dict,
                query_intent=intent,
                trace=trace
            )

            if not candidates:
                logger.info("Zero candidates retrieved. Skipping LLM generation.")
                langfuse_tracer.update_trace(
                    trace,
                    output_data={"answer": "I could not find sufficient evidence in the indexed regulatory sources."},
                    metadata={"status": "no_evidence", "candidates_count": 0}
                )
                return RAGResponse(
                    question=question,
                    answer="I could not find sufficient evidence in the indexed regulatory sources.",
                    sources=[],
                    retrieved_chunks_count=0,
                    top_score=0.0,
                    retrieval_mode=active_mode,
                    reranker_used=False,
                    query_intent=intent.model_dump(),
                    sufficient_evidence=False,
                    llm_provider=gen_prov,
                    llm_model=gen_model
                )

            # 4. Apply temporal ranking adjustments
            if intent.time_intent != "none":
                with langfuse_tracer.start_span(trace, name="temporal_resolution", span_type="tool", metadata={"time_intent": intent.time_intent}) as temp_span:
                    candidates = apply_temporal_ranking(intent, candidates)
                    langfuse_tracer.update_span(temp_span, metadata={"adjusted_candidates_count": len(candidates)})

            # 5. Rerank candidates
            if use_rerank and self.reranker.enabled:
                with langfuse_tracer.start_span(
                    trace,
                    name="reranker",
                    span_type="tool",
                    metadata={
                        "model": getattr(self.reranker, "model_name", "bge-reranker"),
                        "device": getattr(self.reranker, "device", "cpu"),
                        "input_candidates": len(candidates),
                        "top_k": final_k
                    }
                ) as span:
                    ranked_chunks = self.reranker.rerank(query=question, candidates=candidates, top_k=final_k)
                    reranker_active = True
                    langfuse_tracer.update_span(span, metadata={"output_candidates": len(ranked_chunks), "top_rerank_score": ranked_chunks[0].score if ranked_chunks else 0.0})
            else:
                ranked_chunks = candidates[:final_k]
                reranker_active = False

            top_score = ranked_chunks[0].score if ranked_chunks else 0.0
            eval_score = max(
                top_score,
                getattr(ranked_chunks[0], "hybrid_score", 0.0) or 0.0,
                getattr(ranked_chunks[0], "vector_score", 0.0) or 0.0,
                getattr(ranked_chunks[0], "bm25_score", 0.0) or 0.0
            ) if ranked_chunks else 0.0

            # 6. Grounding check
            if eval_score < threshold:
                logger.info(f"Insufficient relevance score ({eval_score:.4f} < {threshold}). Skipping generation.")
                langfuse_tracer.update_trace(
                    trace,
                    output_data={"answer": "I could not find sufficient evidence in the indexed regulatory sources."},
                    metadata={"status": "low_confidence", "top_score": top_score, "threshold": threshold}
                )
                return RAGResponse(
                    question=question,
                    answer="I could not find sufficient evidence in the indexed regulatory sources.",
                    sources=[],
                    retrieved_chunks_count=len(ranked_chunks),
                    top_score=top_score,
                    retrieval_mode=active_mode,
                    reranker_used=reranker_active,
                    query_intent=intent.model_dump(),
                    sufficient_evidence=False,
                    llm_provider=gen_prov,
                    llm_model=gen_model
                )

            # 7. Context Builder
            with langfuse_tracer.start_span(
                trace,
                name="context_builder",
                span_type="tool",
                metadata={
                    "evidence_chunks_count": len(ranked_chunks),
                    "approx_total_tokens": sum(len(c.content.split()) for c in ranked_chunks)
                }
            ):
                pass

            # 8. Generate grounded answer via LLM Provider
            with langfuse_tracer.record_generation(
                trace,
                name="llm_generation",
                model=gen_model,
                input_prompt=question,
                metadata={
                    "provider": gen_prov,
                    "fallback_enabled": getattr(settings, "llm_fallback_enabled", False)
                }
            ) as gen_span:
                try:
                    gen_result = self.generator.generate_answer(
                        question=question.strip(),
                        retrieved_chunks=ranked_chunks
                    )
                except Exception as gen_err:
                    langfuse_tracer.record_error(gen_span, gen_err, category=ErrorCategory.LLM_ERROR)
                    langfuse_tracer.record_error(trace, gen_err, category=ErrorCategory.LLM_ERROR)
                    raise gen_err

                langfuse_tracer.update_span(
                    gen_span,
                    metadata={
                        "input_tokens": gen_result.get("input_tokens"),
                        "output_tokens": gen_result.get("output_tokens"),
                        "latency_ms": gen_result.get("latency_ms"),
                        "fallback_used": gen_result.get("fallback_used", False)
                    }
                )

            # 9. Citation Validation Span
            sources = [SourceCitation.model_validate(s) for s in gen_result.get("sources", [])]
            with langfuse_tracer.start_span(
                trace,
                name="citation_validation",
                span_type="tool",
                metadata={
                    "citations_found": len(sources),
                    "valid_citations": len([s for s in sources if s.score > 0]),
                    "invalid_citations": 0
                }
            ):
                pass

            resp_provider = _clean_str(gen_result.get("provider")) or gen_prov
            resp_model = _clean_str(gen_result.get("model")) or gen_model
            fallback_used = bool(gen_result.get("fallback_used", False))

            langfuse_tracer.update_trace(
                trace,
                output_data={"answer_preview": gen_result.get("answer", "")[:200]},
                metadata={
                    "status": "success",
                    "provider": resp_provider,
                    "model": resp_model,
                    "fallback_used": fallback_used,
                    "retrieval_mode": active_mode,
                    "evidence_count": len(ranked_chunks),
                    "citation_integrity": 1.0 if sources else 0.0
                }
            )

            return RAGResponse(
                question=question,
                answer=gen_result.get("answer", ""),
                sources=sources,
                retrieved_chunks_count=len(ranked_chunks),
                top_score=top_score,
                retrieval_mode=active_mode,
                reranker_used=reranker_active,
                query_intent=intent.model_dump(),
                sufficient_evidence=True,
                llm_provider=resp_provider,
                llm_model=resp_model,
                fallback_used=fallback_used,
                primary_provider=_clean_str(gen_result.get("primary_provider")),
                fallback_provider=_clean_str(gen_result.get("fallback_provider"))
            )

    def _handle_change_analysis_query(self, question: str, intent: QueryIntent) -> RAGResponse:
        """Handles change analysis queries by finding matching document and running change detector."""
        all_docs = self.change_detector.load_all_documents()
        if not all_docs:
            return RAGResponse(
                question=question,
                answer="No indexed regulatory documents available for comparative change analysis.",
                query_intent=intent.model_dump(),
                sufficient_evidence=False
            )

        # Filter by category/source if available
        matched_docs = all_docs
        if intent.category:
            matched_docs = [d for d in all_docs if d.category == intent.category]
        if not matched_docs:
            matched_docs = all_docs

        # Select most recent document as current
        from app.retrieval.temporal import parse_date_safe
        matched_docs.sort(
            key=lambda d: parse_date_safe(d.published_date) or parse_date_safe(d.effective_date) or parse_date_safe("1900-01-01"),
            reverse=True
        )
        current_doc = matched_docs[0]

        report: ChangeReport = self.change_detector.analyze_documents(current_doc, candidate_docs=all_docs)

        if report.status != "SUCCESS":
            return RAGResponse(
                question=question,
                answer=f"Could not perform change analysis: {report.message}",
                query_intent=intent.model_dump(),
                change_report=report.model_dump(),
                sufficient_evidence=False
            )

        # Format report into grounded answer text
        answer_parts = [
            f"**Regulatory Change Analysis: {current_doc.title}**\n",
            report.executive_summary,
            "\n### Key Section Changes:"
        ]

        sources: List[SourceCitation] = []
        source_idx = 0

        # Add current document source
        source_idx += 1
        sources.append(SourceCitation(
            source_id=source_idx,
            chunk_id=current_doc.document_id,
            document_id=current_doc.document_id,
            source=current_doc.source,
            title=current_doc.title or "Current Document",
            published_date=current_doc.published_date or "N/A",
            url=current_doc.url,
            score=1.0
        ))

        # Add previous document source if present
        if report.previous_document:
            source_idx += 1
            sources.append(SourceCitation(
                source_id=source_idx,
                chunk_id=report.previous_document.get("document_id", "prev"),
                document_id=report.previous_document.get("document_id", "prev"),
                source=current_doc.source,
                title=report.previous_document.get("title", "Previous Document"),
                published_date=report.previous_document.get("published_date", "N/A"),
                url=report.previous_document.get("url", ""),
                score=0.9
            ))

        for c in report.changes:
            if c.change_type != "UNCHANGED":
                answer_parts.append(f"\n* **[{c.change_type}] {c.title}**: {c.summary} [1]")
                if c.impact:
                    answer_parts.append(f"  * *Impact*: {c.impact}")

        answer_text = "\n".join(answer_parts)

        return RAGResponse(
            question=question,
            answer=answer_text,
            sources=sources,
            retrieved_chunks_count=report.total_sections_compared,
            top_score=1.0,
            query_intent=intent.model_dump(),
            change_report=report.model_dump(),
            sufficient_evidence=True
        )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RegIntel RAG Pipeline CLI.")
    parser.add_argument("query", nargs="?", type=str, default=None, help="Regulatory question or change analysis request.")
    parser.add_argument("--mode", choices=["hybrid", "vector", "bm25"], default="hybrid", help="Retrieval mode.")
    parser.add_argument("--no-rerank", action="store_true", help="Disable local cross-encoder reranker.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of final chunks to supply to LLM.")
    args = parser.parse_args()

    pipeline = RAGPipeline(
        retrieval_mode=args.mode,
        enable_reranker=not args.no_rerank,
        top_k=args.top_k
    )

    if args.query:
        response = pipeline.answer(args.query)
        response.print_formatted()
    else:
        sample_q = "What are the latest SEBI requirements for investment advisers?"
        print(f"\nRunning sample query: > {sample_q}")
        response = pipeline.answer(sample_q)
        response.print_formatted()


if __name__ == "__main__":
    main()
