"""
Master Evaluation Suite Runner for RegIntel RAG (Phases 42, 43, 44).

Executes:
1. Phase 42: Generation and Answer Quality Evaluation
2. Phase 43: Hallucination, Grounding, and Citation Evaluation
3. Phase 44: Failure Root-Cause Analysis, Manual Review Sampling, and Final Master Report Generation
4. System Quality Gate verification (PASS, WARNING, FAIL)
"""

import os
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.generation_evaluator import GenerationEvaluator
from evaluation.grounding_evaluator import GroundingEvaluator
from evaluation.failure_analyzer import FailureAnalyzer, QualityGateConfig

logger = logging.getLogger("MasterEvaluation")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def run_master_evaluation(limit: int = None):
    print("\n" + "=" * 80)
    print("REGINTEL RAG — MASTER POST-RETRIEVAL & GENERATION EVALUATION SUITE")
    print("=" * 80)

    # 1. Generation Evaluation (Phase 42)
    print("\n[1/4] Running Generation Quality Evaluation (Phase 42)...")
    gen_eval = GenerationEvaluator()
    gen_summary, gen_per_query = gen_eval.run_evaluation(limit=limit)
    print(f"-> Total Questions: {gen_summary['total_questions']}")
    print(f"-> Avg Relevance: {gen_summary['metrics']['average_relevance']} / 5.0")
    print(f"-> Avg Completeness: {gen_summary['metrics']['average_completeness']} / 5.0")
    print(f"-> Answerability Handling: {gen_summary['metrics']['answerability_handling_rate']}%")
    print(f"-> Avg Total Latency: {gen_summary['latency']['average_total_ms']} ms (P95: {gen_summary['latency']['p95_total_ms']} ms)")

    # 2. Grounding & Citation Evaluation (Phase 43)
    print("\n[2/4] Running Grounding & Citation Evaluation (Phase 43)...")
    grd_eval = GroundingEvaluator()
    grd_summary, grd_per_query = grd_eval.run_evaluation(
        limit=limit,
        precomputed_generation_results=gen_per_query
    )
    print(f"-> Total Substantive Claims: {grd_summary['claim_statistics']['total_claims_extracted']}")
    print(f"-> Grounded Claim Rate: {grd_summary['grounding_metrics']['grounded_claim_rate']}%")
    print(f"-> Unsupported Claim Rate: {grd_summary['grounding_metrics']['unsupported_claim_rate']}%")
    print(f"-> Citation Integrity: {grd_summary['citation_metrics']['citation_integrity']}%")
    print(f"-> Citation Support Rate: {grd_summary['citation_metrics']['citation_support_rate']}%")
    print(f"-> Citation Coverage Rate: {grd_summary['citation_metrics']['citation_coverage_rate']}%")
    print(f"-> Safe Abstention Rate: {grd_summary['grounding_metrics']['safe_abstention_rate']}%")

    # 3. Failure Analysis & Report Generation (Phase 44)
    print("\n[3/4] Running RAG Failure Analysis & Quality Gate (Phase 44)...")
    analyzer = FailureAnalyzer(QualityGateConfig(
        min_recall_at_5=0.20,
        min_grounded_claim_rate=80.0,
        min_citation_integrity=95.0,
        min_safe_abstention_rate=80.0
    ))

    results_dir = Path(__file__).resolve().parent / "results"

    failure_summary = analyzer.analyze_evaluation_results(gen_per_query, grd_per_query)
    analyzer.generate_failure_analysis_report(failure_summary)
    analyzer.generate_manual_review_report(gen_per_query, sample_size=20)

    # Retrieval summary (if available)
    ret_summary = None
    ret_report_path = results_dir / "retrieval_report.json"
    if ret_report_path.exists():
        try:
            with open(ret_report_path, "r", encoding="utf-8") as f:
                ret_summary = json.load(f)
        except Exception:
            pass

    qg_result = analyzer.evaluate_quality_gate(
        retrieval_summary=ret_summary,
        generation_summary=gen_summary,
        grounding_summary=grd_summary
    )

    final_report = analyzer.generate_master_final_report(
        retrieval_summary=ret_summary,
        generation_summary=gen_summary,
        grounding_summary=grd_summary,
        failure_summary=failure_summary,
        quality_gate=qg_result
    )

    print(f"-> Total Failures Identified: {failure_summary['total_failures']}")
    print(f"-> Quality Gate Status: {qg_result.status}")
    for p in qg_result.passed_checks:
        print(f"   [PASS] {p}")
    for w in qg_result.warning_checks:
        print(f"   [WARN] {w}")
    for fl in qg_result.failed_checks:
        print(f"   [FAIL] {fl}")

    print("\n[4/4] Master Evaluation Reports Generated:")
    print(f"- Final Master Report: {results_dir / 'final_report.md'}")
    print(f"- Failure Analysis   : {results_dir / 'failure_analysis.md'}")
    print(f"- Manual Review (20) : {results_dir / 'manual_review.md'}")
    print(f"- Failure Summary    : {results_dir / 'failure_summary.json'}")
    print(f"- Grounding Claims   : {results_dir / 'claims.json'}")
    print(f"- Unsupported Claims : {results_dir / 'unsupported_claims.json'}")
    print("=" * 80)
    print("MASTER EVALUATION COMPLETED SUCCESSFULLY")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_master_evaluation()
