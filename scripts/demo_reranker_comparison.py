"""
Side-by-Side Reranker Demonstration Script (Phase 36-38 Final Demonstration).

Runs identical regulatory queries with:
1. Hybrid Retrieval Baseline (ENABLE_RERANKER=false)
2. Hybrid + BGE Neural Cross-Encoder Reranking (ENABLE_RERANKER=true)

Displays side-by-side ranking changes, score comparisons, and citation mapping.

Usage:
    python scripts/demo_reranker_comparison.py
"""

import os
import sys

# Ensure root directory is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from typing import List

from app.config import settings
from app.rag.pipeline import RAGPipeline, RAGResponse

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")


def run_demo(query: str = "What are the latest SEBI requirements for investment advisers regarding fees and client agreements?"):
    print("\n" + "=" * 80)
    print("REGINTEL RAG — NEURAL RERANKER SIDE-BY-SIDE DEMONSTRATION")
    print("=" * 80)
    print(f"QUERY: '{query}'\n")

    pipeline = RAGPipeline()

    # 1. Run Baseline: Hybrid Alone
    print(">>> [1/2] Executing Hybrid Retrieval Baseline (ENABLE_RERANKER=False)...")
    res_hybrid: RAGResponse = pipeline.answer(query, enable_reranker=False, top_k=5)

    # 2. Run Target: Hybrid + Cross-Encoder Reranker
    print(">>> [2/2] Executing Hybrid + BGE Cross-Encoder Reranker (ENABLE_RERANKER=True)...")
    res_reranked: RAGResponse = pipeline.answer(query, enable_reranker=True, top_k=5)

    # 3. Side-by-Side Comparison Display
    print("\n" + "=" * 80)
    print(f"{'RANK':<5} | {'HYBRID RETRIEVAL BASELINE':<34} | {'HYBRID + BGE CROSS-ENCODER':<34}")
    print("-" * 80)

    h_sources = res_hybrid.sources
    r_sources = res_reranked.sources

    max_len = max(len(h_sources), len(r_sources), 5)
    for i in range(max_len):
        h_info = f"[{h_sources[i].source_id}] {h_sources[i].title[:22]}... (S:{h_sources[i].score:.3f})" if i < len(h_sources) else "N/A"
        r_info = f"[{r_sources[i].source_id}] {r_sources[i].title[:22]}... (S:{r_sources[i].score:.3f})" if i < len(r_sources) else "N/A"
        print(f"#{i+1:<4} | {h_info:<34} | {r_info:<34}")

    print("=" * 80)

    # 4. Show Grounded Answer & Citations
    print("\n>>> GROUNDED ANSWER (WITH CITATIONS):")
    print("-" * 80)
    print(res_reranked.answer)
    print("-" * 80)

    print("\n>>> VERIFIED CITATION MAPPINGS:")
    for s in res_reranked.sources:
        print(f"  [{s.source_id}] -> Chunk: {s.chunk_id} | Title: {s.title} | Section: {s.section}")

    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "What are the latest SEBI requirements for investment advisers regarding fees and client agreements?"
    run_demo(q)
