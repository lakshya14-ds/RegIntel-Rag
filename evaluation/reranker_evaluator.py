"""
Dedicated Neural Cross-Encoder Reranker Evaluator for RegIntel RAG (Phase 38).

Executes comprehensive evaluation of BAAI/bge-reranker-v2-m3:
1. Comparative analysis: Hybrid vs Hybrid + Reranker (same questions)
2. Metric calculation: Recall@3, Recall@5, Recall@10, Candidate Recall@20, MRR
3. Latency profiling: Hybrid retrieval vs Reranker inference vs Total
4. Candidate pool size ablation: 10 vs 20 vs 30 candidates
5. Top-k size ablation: 3 vs 5 vs 10 chunks
6. Per-query ranking shift analysis & Failure classification
7. Persists structured JSON/MD reports to evaluation/results/reranker/
"""

import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings
from app.retrieval.mongodb_vector import MongoDBVectorRetriever
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import LocalReranker
from app.retrieval.query_analyzer import QueryAnalyzer
from evaluation.metrics import compute_recall_at_k, compute_reciprocal_rank, compute_precision_at_k

logger = logging.getLogger("regintel.evaluation.reranker")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

EVAL_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVAL_DIR / "dataset" / "retrieval_questions.json"
RESULTS_BASE_DIR = EVAL_DIR / "results" / "reranker"
RESULTS_BASE_DIR.mkdir(parents=True, exist_ok=True)


class RerankerEvaluator:
    """
    Evaluates and profiles the BGE cross-encoder reranker against the standard hybrid baseline.
    """

    def __init__(
        self,
        dataset_path: Optional[Path] = None,
        candidate_pool: int = 20,
        enable_reranker: bool = True
    ):
        self.dataset_path = dataset_path or DATASET_PATH
        self.candidate_pool = candidate_pool

        self.vector_retriever = MongoDBVectorRetriever(default_top_k=candidate_pool)
        self.bm25_retriever = BM25Retriever()
        self.hybrid_retriever = HybridRetriever(
            vector_retriever=self.vector_retriever,
            bm25_retriever=self.bm25_retriever,
            candidate_pool=candidate_pool
        )
        self.reranker = LocalReranker(enabled=enable_reranker)
        self.query_analyzer = QueryAnalyzer()

    def load_dataset(self) -> List[Dict[str, Any]]:
        """Loads benchmark retrieval questions."""
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_configuration(
        self,
        queries: List[Dict[str, Any]],
        candidate_k: int = 20,
        final_top_k: int = 5,
        use_reranker: bool = True
    ) -> Dict[str, Any]:
        """
        Runs evaluation for a specific candidate_pool and top_k configuration,
        measuring Recall@3, Recall@5, Recall@10, Candidate Recall@20, MRR, and latencies.
        """
        eval_cases = []
        recalls_3, recalls_5, recalls_10 = [], [], []
        candidate_recalls = []
        reciprocal_ranks = []
        precisions_5 = []

        retrieval_latencies = []
        reranker_latencies = []
        total_latencies = []

        for item in queries:
            qid = item.get("id", "N/A")
            qtext = item["question"]
            expected_chunks = item.get("expected_chunks", []) or item.get("relevant_chunk_ids", [])
            expected_docs = item.get("expected_documents", []) or item.get("relevant_document_ids", [])

            # 1. Query Analysis & Filter building
            intent = self.query_analyzer.analyze(qtext)
            filter_dict = None
            if intent.category:
                filter_dict = {"metadata.category": intent.category}

            # 2. Hybrid candidate retrieval (cached to avoid duplicate API calls across ablations)
            cache_key = f"{qtext}__30__{intent.category}"
            if not hasattr(self, "_candidate_cache"):
                self._candidate_cache = {}

            if cache_key not in self._candidate_cache:
                t0 = time.time()
                full_cands = self.hybrid_retriever.search(
                    query=qtext,
                    top_k=30,
                    candidate_k=30,
                    filter_dict=filter_dict,
                    query_intent=intent
                )
                t_retrieval = time.time() - t0
                self._candidate_cache[cache_key] = (full_cands, t_retrieval)
            else:
                full_cands, t_retrieval = self._candidate_cache[cache_key]

            candidates = full_cands[:candidate_k]
            retrieval_latencies.append(t_retrieval * 1000.0)

            # Measure Candidate Recall
            cand_retrieved_chunks = [c.chunk_id for c in candidates]
            cand_retrieved_docs = [c.document_id for c in candidates]
            cand_rec = compute_recall_at_k(cand_retrieved_chunks, expected_chunks, k=candidate_k)
            if cand_rec == 0.0 and expected_docs:
                cand_rec = compute_recall_at_k(cand_retrieved_docs, expected_docs, k=candidate_k)
            candidate_recalls.append(cand_rec)

            # 3. Neural Reranking (Cached for identical candidate pools across ablations)
            if not hasattr(self, "_reranker_cache"):
                self._reranker_cache = {}

            rerank_cache_key = f"{qtext}__{candidate_k}"
            if use_reranker and self.reranker.enabled:
                if rerank_cache_key not in self._reranker_cache:
                    t1 = time.time()
                    full_ranked = self.reranker.rerank(query=qtext, candidates=candidates, top_k=candidate_k)
                    t_rerank = time.time() - t1
                    self._reranker_cache[rerank_cache_key] = (full_ranked, t_rerank)
                else:
                    full_ranked, t_rerank = self._reranker_cache[rerank_cache_key]
                ranked = full_ranked[:final_top_k]
            else:
                t_rerank = 0.0
                ranked = candidates[:final_top_k]

            reranker_latencies.append(t_rerank * 1000.0)

            t_total = t_retrieval + t_rerank
            total_latencies.append(t_total * 1000.0)

            retrieved_chunks = [c.chunk_id for c in ranked]
            retrieved_docs = [c.document_id for c in ranked]

            # Compute metric scores
            r3 = compute_recall_at_k(retrieved_chunks, expected_chunks, k=3)
            r5 = compute_recall_at_k(retrieved_chunks, expected_chunks, k=5)
            r10 = compute_recall_at_k(retrieved_chunks, expected_chunks, k=10)
            mrr = compute_reciprocal_rank(retrieved_chunks, expected_chunks)
            p5 = compute_precision_at_k(retrieved_chunks, expected_chunks, k=5)

            # Document-level fallback if chunk-level is 0
            if r5 == 0.0 and expected_docs:
                r3 = compute_recall_at_k(retrieved_docs, expected_docs, k=3)
                r5 = compute_recall_at_k(retrieved_docs, expected_docs, k=5)
                r10 = compute_recall_at_k(retrieved_docs, expected_docs, k=10)
                mrr = compute_reciprocal_rank(retrieved_docs, expected_docs)
                p5 = compute_precision_at_k(retrieved_docs, expected_docs, k=5)

            recalls_3.append(r3)
            recalls_5.append(r5)
            recalls_10.append(r10)
            reciprocal_ranks.append(mrr)
            precisions_5.append(p5)

            # Find first relevant rank
            first_rank = None
            for idx, c in enumerate(ranked):
                if c.chunk_id in expected_chunks or c.document_id in expected_docs:
                    first_rank = idx + 1
                    break

            eval_cases.append({
                "question_id": qid,
                "question": qtext,
                "category": item.get("category", "General"),
                "expected_chunks": expected_chunks,
                "expected_docs": expected_docs,
                "retrieved_ids": retrieved_chunks,
                "first_relevant_rank": first_rank,
                "recall_at_3": round(r3, 4),
                "recall_at_5": round(r5, 4),
                "recall_at_10": round(r10, 4),
                "mrr": round(mrr, 4),
                "candidate_recall": round(cand_rec, 4),
                "retrieval_ms": round(t_retrieval * 1000.0, 2),
                "reranker_ms": round(t_rerank * 1000.0, 2)
            })

        n = len(queries)
        sorted_total = sorted(total_latencies)
        p95_idx = int(0.95 * len(sorted_total))
        p95_lat = sorted_total[p95_idx] if sorted_total else 0.0

        return {
            "candidate_k": candidate_k,
            "final_top_k": final_top_k,
            "use_reranker": use_reranker,
            "total_queries": n,
            "metrics": {
                "recall_at_3": round(sum(recalls_3) / n, 4) if n else 0.0,
                "recall_at_5": round(sum(recalls_5) / n, 4) if n else 0.0,
                "recall_at_10": round(sum(recalls_10) / n, 4) if n else 0.0,
                "candidate_recall_at_k": round(sum(candidate_recalls) / n, 4) if n else 0.0,
                "mrr": round(sum(reciprocal_ranks) / n, 4) if n else 0.0,
                "precision_at_5": round(sum(precisions_5) / n, 4) if n else 0.0
            },
            "latencies_ms": {
                "avg_retrieval_latency_ms": round(sum(retrieval_latencies) / n, 2) if n else 0.0,
                "avg_reranker_latency_ms": round(sum(reranker_latencies) / n, 2) if n else 0.0,
                "avg_total_latency_ms": round(sum(total_latencies) / n, 2) if n else 0.0,
                "p95_total_latency_ms": round(p95_lat, 2)
            },
            "cases": eval_cases
        }

    def run_comprehensive_study(self) -> Dict[str, Any]:
        """
        Executes the complete Phase 38 study:
        - Configuration A: Hybrid (top 5)
        - Configuration B: Hybrid + Reranker (20 -> top 5)
        - Candidate size ablation: 10 vs 20 vs 30 candidates
        - Top-k ablation: 3 vs 5 vs 10 chunks
        - Per-query comparison & Failure analysis
        """
        queries = self.load_dataset()
        logger.info(f"Loaded {len(queries)} retrieval questions for reranker study.")

        ts = datetime.utcnow().strftime("%Y_%m_%d_%H%M%S")
        run_dir = RESULTS_BASE_DIR / f"run_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)

        print("\n" + "=" * 65)
        print("RUNNING RERANKER EVALUATION & ABLATION BENCHMARKS")
        print("=" * 65)

        # 1. Baseline Configuration A: Hybrid alone (top 5)
        print("\n>>> [1/4] Evaluating Baseline: Hybrid Retrieval (Top 5)...")
        hybrid_res = self.evaluate_configuration(queries, candidate_k=5, final_top_k=5, use_reranker=False)

        # 2. Target Configuration B: Hybrid + BGE Reranker (20 -> top 5)
        print("\n>>> [2/4] Evaluating Target: Hybrid + BGE Reranker (20 -> Top 5)...")
        reranked_res = self.evaluate_configuration(queries, candidate_k=20, final_top_k=5, use_reranker=True)

        # 3. Candidate Pool Size Ablation (10 vs 20 vs 30)
        print("\n>>> [3/4] Running Candidate Pool Size Ablation (10 vs 20 vs 30)...")
        ablation_cands = {}
        for cand_size in [10, 20, 30]:
            print(f"  - Testing Candidate Pool = {cand_size}...")
            res_c = self.evaluate_configuration(queries, candidate_k=cand_size, final_top_k=5, use_reranker=True)
            ablation_cands[f"candidates_{cand_size}"] = {
                "recall_at_5": res_c["metrics"]["recall_at_5"],
                "candidate_recall": res_c["metrics"]["candidate_recall_at_k"],
                "mrr": res_c["metrics"]["mrr"],
                "avg_reranker_latency_ms": res_c["latencies_ms"]["avg_reranker_latency_ms"],
                "avg_total_latency_ms": res_c["latencies_ms"]["avg_total_latency_ms"]
            }

        # 4. Top-K Size Ablation (3 vs 5 vs 10)
        print("\n>>> [4/4] Running Top-K Output Size Ablation (k = 3 vs 5 vs 10)...")
        ablation_topk = {}
        for k_val in [3, 5, 10]:
            print(f"  - Testing Top-K = {k_val}...")
            res_k = self.evaluate_configuration(queries, candidate_k=20, final_top_k=k_val, use_reranker=True)
            ablation_topk[f"top_k_{k_val}"] = {
                "recall": res_k["metrics"][f"recall_at_{k_val}" if k_val in (3, 5, 10) else "recall_at_5"],
                "mrr": res_k["metrics"]["mrr"],
                "avg_total_latency_ms": res_k["latencies_ms"]["avg_total_latency_ms"]
            }

        # 5. Per-Query Ranking Shift & Failure Classification
        per_query_comparison = []
        failures = []
        improved_count = 0
        worsened_count = 0
        neutral_count = 0

        for h_case, r_case in zip(hybrid_res["cases"], reranked_res["cases"]):
            h_rank = h_case["first_relevant_rank"]
            r_rank = r_case["first_relevant_rank"]

            status = "neutral"
            if h_rank is None and r_rank is not None:
                status = "improved"
                improved_count += 1
            elif h_rank is not None and r_rank is None:
                status = "worsened"
                worsened_count += 1
            elif h_rank is not None and r_rank is not None:
                if r_rank < h_rank:
                    status = "improved"
                    improved_count += 1
                elif r_rank > h_rank:
                    status = "worsened"
                    worsened_count += 1
                else:
                    neutral_count += 1
            else:
                neutral_count += 1

            pq_item = {
                "question_id": h_case["question_id"],
                "question": h_case["question"],
                "category": h_case["category"],
                "hybrid_first_relevant_rank": h_rank,
                "reranked_first_relevant_rank": r_rank,
                "hybrid_recall_at_5": h_case["recall_at_5"],
                "reranked_recall_at_5": r_case["recall_at_5"],
                "candidate_recall": r_case["candidate_recall"],
                "status": status
            }
            per_query_comparison.append(pq_item)

            # Failure Analysis Classification
            if r_case["recall_at_5"] == 0.0:
                if r_case["candidate_recall"] == 0.0:
                    failure_type = "missing_candidate"
                    reason = "Relevant document was not present in the hybrid 20-candidate pool."
                elif h_case["recall_at_5"] > 0.0 and r_case["recall_at_5"] == 0.0:
                    failure_type = "reranker_misranking"
                    reason = "Hybrid retrieved relevant chunk in top 5, but reranker pushed it down below rank 5."
                elif "circular" in h_case["question"].lower() or "/" in h_case["question"]:
                    failure_type = "exact_term_issue"
                    reason = "Exact circular number or regulation clause mismatch."
                else:
                    failure_type = "semantic_confusion"
                    reason = "Reranker prioritized semantically overlapping but non-authoritative clauses."

                failures.append({
                    "question_id": h_case["question_id"],
                    "question": h_case["question"],
                    "category": h_case["category"],
                    "failure_type": failure_type,
                    "reason": reason,
                    "hybrid_rank": h_rank,
                    "reranked_rank": r_rank
                })

        full_study_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": settings.reranker_model,
            "device": self.reranker._determine_device(),
            "total_questions": len(queries),
            "baseline_hybrid": hybrid_res["metrics"],
            "hybrid_reranked": reranked_res["metrics"],
            "latencies": reranked_res["latencies_ms"],
            "candidate_ablation": ablation_cands,
            "topk_ablation": ablation_topk,
            "ranking_shift": {
                "improved_queries": improved_count,
                "worsened_queries": worsened_count,
                "neutral_queries": neutral_count,
                "net_gain": improved_count - worsened_count
            },
            "failures_count": len(failures)
        }

        # 6. Save JSON & Markdown Artifacts
        with open(run_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump({
                "model": settings.reranker_model,
                "device": self.reranker._determine_device(),
                "dataset_size": len(queries),
                "timestamp": datetime.utcnow().isoformat()
            }, f, indent=2)

        with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(full_study_report, f, indent=2)
        with open(RESULTS_BASE_DIR / "summary.json", "w", encoding="utf-8") as f:
            json.dump(full_study_report, f, indent=2)

        with open(run_dir / "per_query.json", "w", encoding="utf-8") as f:
            json.dump(per_query_comparison, f, indent=2)
        with open(RESULTS_BASE_DIR / "per_query.json", "w", encoding="utf-8") as f:
            json.dump(per_query_comparison, f, indent=2)

        with open(run_dir / "failures.json", "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2)
        with open(RESULTS_BASE_DIR / "failures.json", "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2)
        with open(EVAL_DIR / "results" / "reranker_failures.json", "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2)

        # Generate Markdown summary
        md_summary = self._generate_markdown_summary(full_study_report, ablation_cands, ablation_topk)
        with open(run_dir / "summary.md", "w", encoding="utf-8") as f:
            f.write(md_summary)
        with open(RESULTS_BASE_DIR / "summary.md", "w", encoding="utf-8") as f:
            f.write(md_summary)

        # 7. Log to MLflow
        try:
            from app.observability.mlflow_tracker import mlflow_tracker
            mlflow_tracker.log_retrieval_evaluation(
                method="hybrid_reranked",
                top_k=5,
                metrics={
                    "recall_at_3": reranked_res["metrics"]["recall_at_3"],
                    "recall_at_5": reranked_res["metrics"]["recall_at_5"],
                    "recall_at_10": reranked_res["metrics"]["recall_at_10"],
                    "candidate_recall_at_20": reranked_res["metrics"]["candidate_recall_at_k"],
                    "mrr": reranked_res["metrics"]["mrr"],
                    "precision_at_5": reranked_res["metrics"]["precision_at_5"],
                    "avg_reranker_latency_ms": reranked_res["latencies_ms"]["avg_reranker_latency_ms"],
                    "avg_total_latency_ms": reranked_res["latencies_ms"]["avg_total_latency_ms"]
                },
                dataset_size=len(queries),
                parameters={
                    "reranker_model": settings.reranker_model,
                    "reranker_device": self.reranker._determine_device(),
                    "candidate_pool": 20
                },
                results_file=run_dir / "summary.json"
            )
        except Exception as e:
            logger.warning(f"MLflow logging notice: {e}")

        print("\n" + "=" * 65)
        print("RERANKER BENCHMARK COMPLETED SUCCESSFULLY")
        print(f"Results Directory : {run_dir}")
        print("=" * 65 + "\n")

        return full_study_report

    def _generate_markdown_summary(
        self,
        report: Dict[str, Any],
        cands_ablation: Dict[str, Any],
        topk_ablation: Dict[str, Any]
    ) -> str:
        base = report["baseline_hybrid"]
        rerank = report["hybrid_reranked"]
        lat = report["latencies"]
        shift = report["ranking_shift"]

        return f"""# Neural Cross-Encoder Reranker Evaluation Report

**Model**: `{report['model']}` | **Device**: `{report['device'].upper()}` | **Evaluated Questions**: `{report['total_questions']}`

---

## 1. Hybrid vs Hybrid + Reranker Performance

| Retrieval Method | Recall@3 | Recall@5 | Recall@10 | MRR | Precision@5 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Hybrid Baseline** | {base['recall_at_3']:.4f} | {base['recall_at_5']:.4f} | {base['recall_at_10']:.4f} | {base['mrr']:.4f} | {base['precision_at_5']:.4f} |
| **Hybrid + BGE Reranker** | **{rerank['recall_at_3']:.4f}** | **{rerank['recall_at_5']:.4f}** | **{rerank['recall_at_10']:.4f}** | **{rerank['mrr']:.4f}** | **{rerank['precision_at_5']:.4f}** |

- **Candidate Pool Recall@20**: `{rerank['candidate_recall_at_k']:.4f}`
- **Ranking Shift**: `{shift['improved_queries']}` queries improved, `{shift['worsened_queries']}` worsened, `{shift['neutral_queries']}` unchanged (Net Gain: **+{shift['net_gain']}**).

---

## 2. Latency Breakdown

| Stage | Average Latency |
| :--- | :---: |
| **Hybrid Candidate Retrieval** | `{lat['avg_retrieval_latency_ms']:.2f} ms` |
| **BGE Cross-Encoder Reranking** | `{lat['avg_reranker_latency_ms']:.2f} ms` |
| **Total Retrieval Pipeline** | `{lat['avg_total_latency_ms']:.2f} ms` (p95: `{lat['p95_total_latency_ms']:.2f} ms`) |

---

## 3. Candidate Pool Size Ablation

| Candidate Pool Size | Recall@5 | Candidate Recall | MRR | Reranker Latency |
| :--- | :---: | :---: | :---: | :---: |
| **10 Candidates** | {cands_ablation['candidates_10']['recall_at_5']:.4f} | {cands_ablation['candidates_10']['candidate_recall']:.4f} | {cands_ablation['candidates_10']['mrr']:.4f} | {cands_ablation['candidates_10']['avg_reranker_latency_ms']:.2f} ms |
| **20 Candidates (Default)** | **{cands_ablation['candidates_20']['recall_at_5']:.4f}** | **{cands_ablation['candidates_20']['candidate_recall']:.4f}** | **{cands_ablation['candidates_20']['mrr']:.4f}** | **{cands_ablation['candidates_20']['avg_reranker_latency_ms']:.2f} ms** |
| **30 Candidates** | {cands_ablation['candidates_30']['recall_at_5']:.4f} | {cands_ablation['candidates_30']['candidate_recall']:.4f} | {cands_ablation['candidates_30']['mrr']:.4f} | {cands_ablation['candidates_30']['avg_reranker_latency_ms']:.2f} ms |

---

## 4. Top-K Output Size Ablation

| Top-K Chunks | Recall | MRR | Total Latency |
| :--- | :---: | :---: | :---: |
| **k = 3** | {topk_ablation['top_k_3']['recall']:.4f} | {topk_ablation['top_k_3']['mrr']:.4f} | {topk_ablation['top_k_3']['avg_total_latency_ms']:.2f} ms |
| **k = 5 (Default)** | **{topk_ablation['top_k_5']['recall']:.4f}** | **{topk_ablation['top_k_5']['mrr']:.4f}** | **{topk_ablation['top_k_5']['avg_total_latency_ms']:.2f} ms** |
| **k = 10** | {topk_ablation['top_k_10']['recall']:.4f} | {topk_ablation['top_k_10']['mrr']:.4f} | {topk_ablation['top_k_10']['avg_total_latency_ms']:.2f} ms |
"""


if __name__ == "__main__":
    evaluator = RerankerEvaluator()
    evaluator.run_comprehensive_study()
