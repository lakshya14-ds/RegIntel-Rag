"""
Vector Retrieval Smoke Testing and Evaluation Script.

Evaluates semantic retrieval quality across standard regulatory questions,
compares top-k and candidate configurations, and logs failure modes to retrieval_failures.json.
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval.mongodb_vector import MongoDBVectorRetriever, RetrievedChunk

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

QUESTIONS_FILE = PROJECT_ROOT / "evaluation" / "retrieval_questions.json"
FAILURES_FILE = PROJECT_ROOT / "evaluation" / "retrieval_failures.json"


def safe_print(text: str):
    """Safely prints strings to Windows consoles without charmap encoding crashes."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding))


def run_retrieval_tests(
    top_k: int = 5,
    num_candidates: int = 100,
    min_acceptable_score: float = 0.40,
    limit_queries: Optional[int] = None
) -> Dict[str, Any]:
    """
    Executes vector retrieval over the evaluation query set and inspects quality.
    """
    if not QUESTIONS_FILE.exists():
        raise FileNotFoundError(f"Evaluation questions file not found: {QUESTIONS_FILE}")

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if limit_queries and limit_queries > 0:
        questions = questions[:limit_queries]

    retriever = MongoDBVectorRetriever(default_top_k=top_k, default_num_candidates=num_candidates)
    
    print("\n" + "=" * 60)
    print(f"Vector Retrieval Smoke Test (top_k={top_k}, numCandidates={num_candidates})")
    print("=" * 60)

    total_queries = len(questions)
    failures: List[Dict[str, Any]] = []
    top1_scores: List[float] = []

    for q_item in questions:
        qid = q_item.get("id")
        cat = q_item.get("category", "General")
        question_text = q_item.get("question", "")

        print(f"\n[Query #{qid}] ({cat})")
        safe_print(f"Question: {question_text}")
        print("-" * 50)

        try:
            results: List[RetrievedChunk] = retriever.retrieve(question_text, limit=top_k, num_candidates=num_candidates)
        except Exception as e:
            logger.error(f"Retrieval failed for question '{question_text}': {e}")
            failures.append({
                "question": question_text,
                "category": cat,
                "failure_type": "retrieval_exception",
                "error": str(e),
                "top_results": []
            })
            continue

        if not results:
            print("  [!] No matching chunks retrieved.")
            failures.append({
                "question": question_text,
                "category": cat,
                "failure_type": "empty_results",
                "top_results": []
            })
            continue

        top1_scores.append(results[0].score)

        for rank, chunk in enumerate(results, start=1):
            print(f"Rank {rank} | Score: {chunk.score:.4f}")
            safe_print(f"  Title   : {chunk.title or 'Untitled'}")
            safe_print(f"  Section : {chunk.section or 'General'}")
            print(f"  Category: {chunk.category or 'None'} | Date: {chunk.published_date or 'N/A'}")
            preview = chunk.content.replace("\n", " ")[:140]
            safe_print(f"  Content : {preview}...")
            print(f"  URL     : {chunk.url}")
            print()

        # Check for potential failure modes
        top_score = results[0].score
        if top_score < min_acceptable_score:
            failures.append({
                "question": question_text,
                "category": cat,
                "failure_type": "low_similarity_score",
                "top_score": top_score,
                "top_results": [
                    {"title": r.title, "section": r.section, "score": r.score, "chunk_id": r.chunk_id}
                    for r in results[:3]
                ]
            })

    # Save failures
    FAILURES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FAILURES_FILE, "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2, ensure_ascii=False)

    avg_top1 = sum(top1_scores) / len(top1_scores) if top1_scores else 0.0
    print("\n" + "=" * 60)
    print("Retrieval Test Summary")
    print("-" * 60)
    print(f"Total queries evaluated : {total_queries}")
    print(f"Queries with results    : {len(top1_scores)}")
    print(f"Average Top-1 Score     : {avg_top1:.4f}")
    print(f"Flagged failure queries : {len(failures)}")
    print(f"Failures recorded in    : {FAILURES_FILE.name}")
    print("=" * 60 + "\n")

    return {
        "total_queries": total_queries,
        "avg_top1_score": avg_top1,
        "failures_count": len(failures)
    }


def compare_retrieval_configurations():
    """Compares different top_k and numCandidates configurations."""
    print("\n--- Comparing Retrieval Configurations (Top 3 Queries) ---")
    configs = [
        {"top_k": 3, "num_candidates": 50},
        {"top_k": 5, "num_candidates": 100},
        {"top_k": 10, "num_candidates": 200},
    ]

    for cfg in configs:
        k = cfg["top_k"]
        c = cfg["num_candidates"]
        print(f"\nTesting Config: top_k={k}, numCandidates={c}")
        run_retrieval_tests(top_k=k, num_candidates=c, limit_queries=3)


if __name__ == "__main__":
    run_retrieval_tests(limit_queries=5)
