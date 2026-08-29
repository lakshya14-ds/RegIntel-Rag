"""
MLflow Experiment Runner CLI for RegIntel RAG (Phase 32.10).

Executes complete benchmark evaluation (retrieval + generation)
and logs all parameters, metrics, dataset metadata, and report artifacts to MLflow.

Usage:
    python -m evaluation.run_mlflow_experiment
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.observability.mlflow_tracker import mlflow_tracker, get_git_commit_hash
from evaluation.retrieval_evaluator import RetrievalEvaluator
from evaluation.generation_evaluator import GenerationEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("regintel.evaluation.mlflow_run")


def run_experiment(run_name: str = "comprehensive_benchmark_eval"):
    """
    Executes the full evaluation suite and logs parameters, metrics, and artifacts to MLflow.
    """
    print("\n" + "=" * 65)
    print(f"STARTING MLFLOW EVALUATION EXPERIMENT: {settings.mlflow_experiment_name}")
    print("=" * 65)

    tags = {
        "git_commit": get_git_commit_hash(),
        "experiment_type": "benchmark_evaluation",
        "system_version": settings.regintel_version
    }

    with mlflow_tracker.start_run(run_name=run_name, tags=tags) as run:
        # 1. Log Global Experiment Parameters
        doc_files = list(settings.processed_data_dir.glob("*.json"))
        chunk_files = list(settings.chunks_data_dir.glob("*.json"))
        global_params = {
            "version": settings.regintel_version,
            "git_commit": get_git_commit_hash(),
            "corpus_version": "2026.08.28-sebi-v1",
            "document_count": len(doc_files),
            "chunk_count": len(chunk_files),
            "embedding_model": settings.embedding_model,
            "embedding_dimensions": settings.embedding_dimension,
            "vector_index": "vector_index_cosine",
            "reranker_model": "BAAI/bge-reranker-v2-m3",
            "temporal_boost_weight": settings.temporal_boost_weight,
            "llm_model": "gemini-2.5-flash",
            "prompt_version": "v2-regulatory-grounded"
        }
        mlflow_tracker.log_params(global_params)

        # 2. Run Retrieval Evaluation
        print("\n>>> [1/2] Executing Systematic Retrieval Benchmarking...")
        ret_eval = RetrievalEvaluator()
        ret_report = ret_eval.run_all_evaluations()

        # Log summary metrics to MLflow
        summary = ret_report.get("summary", {})
        if "hybrid" in summary:
            mlflow_tracker.log_metrics({
                "hybrid_recall_at_3": summary["hybrid"]["recall_at_3"],
                "hybrid_recall_at_5": summary["hybrid"]["recall_at_5"],
                "hybrid_recall_at_10": summary["hybrid"]["recall_at_10"],
                "hybrid_mrr": summary["hybrid"]["mrr"],
                "hybrid_precision_at_5": summary["hybrid"]["precision_at_5"]
            })
        if "hybrid_reranked" in summary:
            mlflow_tracker.log_metrics({
                "reranked_recall_at_5": summary["hybrid_reranked"]["recall_at_5"],
                "reranked_mrr": summary["hybrid_reranked"]["mrr"]
            })

        # 3. Run Generation Evaluation
        print("\n>>> [2/2] Executing End-to-End RAG Answer & Citation Evaluation...")
        gen_eval = GenerationEvaluator()
        gen_report = gen_eval.evaluate_all()

        gen_metrics = gen_report.get("metrics", {})
        if gen_metrics:
            mlflow_tracker.log_metrics({
                "average_relevance_score": gen_metrics.get("average_relevance_score_1_to_5", 0.0),
                "average_groundedness_score": gen_metrics.get("average_groundedness_score_1_to_5", 0.0),
                "average_citation_score": gen_metrics.get("average_citation_score_1_to_5", 0.0),
                "citation_integrity_rate_percent": gen_metrics.get("citation_integrity_rate_percent", 0.0),
                "unsupported_question_handling_rate_percent": gen_metrics.get("unsupported_question_handling_rate_percent", 0.0)
            })

        # 4. Log Artifacts
        results_dir = Path(__file__).resolve().parent / "results"
        for artifact_name in [
            "retrieval_report.json",
            "retrieval_report.md",
            "generation_report.json",
            "generation_report.md",
            "manual_review.md",
            "retrieval_failures.json"
        ]:
            p = results_dir / artifact_name
            if p.exists():
                mlflow_tracker.log_artifact(p, artifact_path="reports")

    print("\n" + "=" * 65)
    print("MLFLOW EXPERIMENT RUN FINISHED SUCCESSFULLY")
    print(f"Tracking URI : {settings.mlflow_tracking_uri}")
    print(f"Experiment   : {settings.mlflow_experiment_name}")
    print("Launch UI with: mlflow ui --port 5000")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run_experiment()
