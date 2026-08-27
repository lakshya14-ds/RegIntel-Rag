"""
Unified Evaluation Runner for RegIntel RAG.

Runs both Retrieval and Generation benchmarks and prints combined results.
"""

from evaluation.retrieval_evaluator import RetrievalEvaluator
from evaluation.generation_evaluator import GenerationEvaluator


def run_all():
    print("\n" + "=" * 65)
    print("RUNNING COMPLETE REGINTEL RAG BENCHMARK EVALUATION")
    print("=" * 65)

    # 1. Retrieval evaluation
    print("\n>>> 1/2 Running Retrieval Benchmark...")
    ret_evaluator = RetrievalEvaluator()
    ret_report = ret_evaluator.run_all_evaluations()

    # 2. Generation evaluation
    print("\n>>> 2/2 Running Generation & Grounding Benchmark...")
    gen_evaluator = GenerationEvaluator()
    gen_report = gen_evaluator.evaluate_all()

    print("\n" + "=" * 65)
    print("ALL EVALUATIONS COMPLETED SUCCESSFULLY")
    print("=" * 65)
    print("Reports generated under evaluation/results/:")
    print("- retrieval_report.json / retrieval_report.md")
    print("- generation_report.json / generation_report.md")
    print("- manual_review.md")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run_all()
