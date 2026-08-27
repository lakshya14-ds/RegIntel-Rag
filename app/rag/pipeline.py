"""
End-to-End RegIntel RAG Pipeline.

Coordinates:
Question -> Query Embedding & Keyword Tokenization -> Hybrid Retrieval (Vector + BM25)
         -> BGE Cross-Encoder Reranking -> Citation Mapping -> Gemini Flash Generation
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
from app.rag.generator import GeminiGenerator
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
    sufficient_evidence: bool = True

    def print_formatted(self):
        """Prints the answer and citation sources clearly formatted."""
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"

        def _safe(txt: str) -> str:
            return txt.encode(encoding, errors="replace").decode(encoding)

        print("\n" + "=" * 60)
        print("QUESTION:")
        print(_safe(self.question))
        print("=" * 60)

        print(f"\n[Retrieval Mode: {self.retrieval_mode.upper()} | Reranker: {'Enabled' if self.reranker_used else 'Disabled'}]")

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
    Production-grade Regulatory Intelligence RAG Pipeline with Hybrid Search and Cross-Encoder Reranking.
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
        generator: Optional[GeminiGenerator] = None,
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
        self.generator = generator or GeminiGenerator()

    def retrieve_candidates(
        self,
        question: str,
        mode: Optional[str] = None,
        candidate_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        """Retrieves raw candidate chunks based on configured retrieval mode."""
        active_mode = (mode or self.retrieval_mode).lower()
        k = candidate_k or self.candidate_pool

        if active_mode == "vector":
            return self.vector_retriever.retrieve(query_text=question, limit=k, filter_dict=filter_dict)
        elif active_mode == "bm25":
            return self.bm25_retriever.search(query=question, top_k=k, filter_dict=filter_dict)
        else:
            # Hybrid
            return self.hybrid_retriever.search(query=question, top_k=k, candidate_k=k, filter_dict=filter_dict)

    def answer(
        self,
        question: str,
        mode: Optional[str] = None,
        enable_reranker: Optional[bool] = None,
        top_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        min_score_threshold: Optional[float] = None
    ) -> RAGResponse:
        """
        Executes complete RAG workflow:
        Query -> Retrieval -> Candidate Pool -> Reranking -> Grounding Check -> Generation -> Citation Check
        """
        if not question or not question.strip():
            return RAGResponse(
                question="",
                answer="Question cannot be empty.",
                sufficient_evidence=False
            )

        active_mode = mode or self.retrieval_mode
        use_rerank = enable_reranker if enable_reranker is not None else self.enable_reranker
        final_k = top_k or self.top_k
        threshold = min_score_threshold if min_score_threshold is not None else self.min_score_threshold

        logger.info(f"Processing RAG query: '{question}' (mode={active_mode}, reranker={use_rerank}, top_k={final_k})")

        # 1. Retrieve candidates from selected channel(s)
        candidates: List[RetrievedChunk] = self.retrieve_candidates(
            question=question.strip(),
            mode=active_mode,
            candidate_k=self.candidate_pool,
            filter_dict=filter_dict
        )

        if not candidates:
            logger.info("Zero candidates retrieved. Skipping LLM generation.")
            return RAGResponse(
                question=question,
                answer="I could not find sufficient evidence in the indexed regulatory sources.",
                sources=[],
                retrieved_chunks_count=0,
                top_score=0.0,
                retrieval_mode=active_mode,
                reranker_used=False,
                sufficient_evidence=False
            )

        # 2. Rerank candidates
        if use_rerank and self.reranker.enabled:
            ranked_chunks = self.reranker.rerank(query=question, candidates=candidates, top_k=final_k)
            reranker_active = True
        else:
            ranked_chunks = candidates[:final_k]
            reranker_active = False

        top_score = ranked_chunks[0].score if ranked_chunks else 0.0

        # 3. Grounding check
        if top_score < threshold:
            logger.info(f"Insufficient relevance score ({top_score:.4f} < {threshold}). Skipping generation.")
            return RAGResponse(
                question=question,
                answer="I could not find sufficient evidence in the indexed regulatory sources.",
                sources=[],
                retrieved_chunks_count=len(ranked_chunks),
                top_score=top_score,
                retrieval_mode=active_mode,
                reranker_used=reranker_active,
                sufficient_evidence=False
            )

        # 4. Generate grounded answer via Gemini
        gen_result = self.generator.generate_answer(
            question=question.strip(),
            retrieved_chunks=ranked_chunks
        )

        sources = [SourceCitation.model_validate(s) for s in gen_result.get("sources", [])]

        return RAGResponse(
            question=question,
            answer=gen_result.get("answer", ""),
            sources=sources,
            retrieved_chunks_count=len(ranked_chunks),
            top_score=top_score,
            retrieval_mode=active_mode,
            reranker_used=reranker_active,
            sufficient_evidence=True
        )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RegIntel RAG Pipeline CLI.")
    parser.add_argument("query", nargs="?", type=str, default=None, help="Regulatory question to answer.")
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
        sample_q = "What are the requirements for investment advisers?"
        print(f"\nRunning default sample query in {args.mode.upper()} mode:")
        response = pipeline.answer(sample_q)
        response.print_formatted()


if __name__ == "__main__":
    main()
