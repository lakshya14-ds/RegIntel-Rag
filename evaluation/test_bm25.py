"""
BM25 Keyword Retrieval Evaluation Script.

Evaluates BM25 lexical search accuracy across exact circular numbers,
regulations, section headers, and domain terminology.
"""

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval.bm25 import BM25Retriever
from app.retrieval.mongodb_vector import RetrievedChunk

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

QUESTIONS_FILE = PROJECT_ROOT / "evaluation" / "retrieval_questions.json"
FAILURES_FILE = PROJECT_ROOT / "evaluation" / "retrieval_failures.json"


def safe_print(text: str):
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding))


def run_bm25_tests(top_k: int = 5, limit_queries: int = 5) -> Dict[str, Any]:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if limit_queries > 0:
        questions = questions[:limit_queries]

    retriever = BM25Retriever()
    retriever.build_index()

    print("\n" + "=" * 60)
    print(f"BM25 Keyword Retrieval Test (top_k={top_k})")
    print("=" * 60)

    top1_scores = []
    for q in questions:
        qid = q.get("id")
        cat = q.get("category")
        q_text = q.get("question")

        print(f"\n[Query #{qid}] ({cat})")
        safe_print(f"Question: {q_text}")
        print("-" * 50)

        results = retriever.search(q_text, top_k=top_k)
        if not results:
            print("  [!] No BM25 matches found.")
            continue

        top1_scores.append(results[0].score)
        for rank, c in enumerate(results, start=1):
            print(f"Rank {rank} | BM25 Score: {c.score:.4f}")
            safe_print(f"  Title   : {c.title or 'Untitled'}")
            safe_print(f"  Section : {c.section or 'General'}")
            preview = c.content.replace("\n", " ")[:120]
            safe_print(f"  Content : {preview}...")
            print()

    avg_score = sum(top1_scores) / len(top1_scores) if top1_scores else 0.0
    print("\n" + "=" * 60)
    print("BM25 Evaluation Summary")
    print("-" * 60)
    print(f"Total evaluated: {len(questions)} | Successful: {len(top1_scores)} | Avg Top-1 Score: {avg_score:.4f}")
    print("=" * 60 + "\n")

    return {"total": len(questions), "successful": len(top1_scores), "avg_top1": avg_score}


if __name__ == "__main__":
    run_bm25_tests()
