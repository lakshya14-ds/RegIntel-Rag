"""
Local Cross-Encoder Reranking Evaluation Script.

Demonstrates reranking of hybrid candidate pools using BAAI/bge-reranker-v2-m3.
"""

import sys
import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import LocalReranker

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def test_reranking_demo():
    sample_query = "What are the qualification requirements and fee limits for investment advisers?"
    
    hybrid = HybridRetriever(candidate_pool=15)
    reranker = LocalReranker()

    print("\n" + "=" * 60)
    print(f"Reranking Evaluation on Query: '{sample_query}'")
    print("=" * 60)

    # 1. Retrieve hybrid pool
    candidates = hybrid.search(sample_query, top_k=10, candidate_k=15)
    print(f"\nRetrieved {len(candidates)} hybrid candidates.")

    # 2. Rerank top 5
    reranked = reranker.rerank(sample_query, candidates, top_k=5)
    print("\nTop 5 After Local Reranking:")
    print("-" * 50)
    for rank, c in enumerate(reranked, start=1):
        print(f"Rank {rank} | Reranker Score: {c.reranker_score} | Hybrid Score: {c.hybrid_score}")
        print(f"  Title   : {c.title}")
        print(f"  Section : {c.section}")
        print(f"  URL     : {c.url}")
        print()


if __name__ == "__main__":
    test_reranking_demo()
