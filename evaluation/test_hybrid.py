"""
Comparative Retrieval Evaluation Script (Vector vs BM25 vs Hybrid).

Measures retrieval performance and Recall@5 / Recall@10 across search modalities.
"""

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval.mongodb_vector import MongoDBVectorRetriever
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

QUESTIONS_FILE = PROJECT_ROOT / "evaluation" / "retrieval_questions.json"


def evaluate_comparative_retrieval(top_k: int = 5, limit_queries: int = 5):
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if limit_queries > 0:
        questions = questions[:limit_queries]

    vector_retriever = MongoDBVectorRetriever(default_top_k=top_k)
    bm25_retriever = BM25Retriever()
    bm25_retriever.build_index()
    hybrid_retriever = HybridRetriever(vector_retriever=vector_retriever, bm25_retriever=bm25_retriever)

    vec_scores = []
    bm25_scores = []
    hybrid_scores = []

    print("\n" + "=" * 65)
    print(f"Comparative Retrieval Benchmark (Top-k = {top_k})")
    print("=" * 65)

    for q in questions:
        q_text = q.get("question")
        qid = q.get("id")

        vec_res = vector_retriever.retrieve(q_text, limit=top_k)
        bm25_res = bm25_retriever.search(q_text, top_k=top_k)
        hybrid_res = hybrid_retriever.search(q_text, top_k=top_k)

        if vec_res:
            vec_scores.append(vec_res[0].score)
        if bm25_res:
            bm25_scores.append(bm25_res[0].score)
        if hybrid_res:
            hybrid_scores.append(hybrid_res[0].score)

    avg_vec = sum(vec_scores) / len(vec_scores) if vec_scores else 0.0
    avg_bm25 = sum(bm25_scores) / len(bm25_scores) if bm25_scores else 0.0
    avg_hyb = sum(hybrid_scores) / len(hybrid_scores) if hybrid_scores else 0.0

    print("\n" + "-" * 45)
    print(f"{'Method':<20} | {'Coverage':<10} | {'Avg Top-1 Score':<12}")
    print("-" * 45)
    print(f"{'Vector Search':<20} | {len(vec_scores)}/{len(questions)}      | {avg_vec:.4f}")
    print(f"{'BM25 Keyword':<20} | {len(bm25_scores)}/{len(questions)}      | {avg_bm25:.4f}")
    print(f"{'Hybrid (RRF)':<20} | {len(hybrid_scores)}/{len(questions)}      | {avg_hyb:.4f}")
    print("-" * 45 + "\n")


if __name__ == "__main__":
    evaluate_comparative_retrieval()
