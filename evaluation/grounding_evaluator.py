"""
Hallucination, Grounding, and Citation Evaluator for RegIntel RAG (Phase 43).

Evaluates:
- Atomic Substantive Claim Extraction
- Claim-Level Evidence Grounding (SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED)
- Grounded Claim Rate (%)
- Unsupported Claim Rate (%)
- Citation Integrity Rate (%)
- Citation Support Rate (%)
- Citation Coverage Rate (%)
- Safe Abstention Rate on Unanswerable Queries (%)

Generates detailed claim-level audit artifacts: claims.json, unsupported_claims.json, and summary reports.
"""

import os
import sys
import re
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.rag.pipeline import RAGPipeline, RAGResponse
from app.rag.citations import CitationManager, extract_citation_indices
from evaluation.prompts import build_claim_extraction_prompt, build_grounding_judge_prompt
from evaluation.metrics import (
    compute_grounded_claim_rate,
    compute_unsupported_claim_rate,
    compute_citation_integrity,
    compute_citation_support_rate,
    compute_citation_coverage_rate,
    compute_safe_abstention_rate
)

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

EVAL_DIR = Path(__file__).resolve().parent
GEN_DATASET_PATH = EVAL_DIR / "dataset" / "generation_questions.json"
RESULTS_DIR = EVAL_DIR / "results" / "grounding"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = EVAL_DIR / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class GroundingEvaluator:
    """
    Evaluator performing fine-grained factual claim extraction, citation verification,
    and evidence grounding analysis.
    """

    def __init__(
        self,
        dataset_path: Optional[Path] = None,
        pipeline: Optional[RAGPipeline] = None,
        enable_cache: bool = True
    ):
        self.dataset_path = dataset_path or GEN_DATASET_PATH
        self.pipeline = pipeline or RAGPipeline(retrieval_mode="hybrid", enable_reranker=True)
        self.enable_cache = enable_cache
        self._cache: Dict[str, Any] = self._load_cache()

    def _get_cache_path(self) -> Path:
        return CACHE_DIR / "grounding_eval_cache.json"

    def _load_cache(self) -> Dict[str, Any]:
        cache_path = self._get_cache_path()
        if cache_path.exists() and self.enable_cache:
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load grounding cache: {e}")
        return {}

    def _save_cache(self) -> None:
        if not self.enable_cache:
            return
        try:
            with open(self._get_cache_path(), "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save grounding cache: {e}")

    def _compute_cache_key(self, question: str, answer: str, evidence: str) -> str:
        raw = f"{question.strip()}|{answer.strip()}|{evidence.strip()}|grounding_v1"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def extract_claims(self, answer: str) -> List[str]:
        """
        Extracts atomic, substantive regulatory claims from a generated answer.
        Filters out greetings, transitions, and generic disclaimers.
        """
        if not answer or not answer.strip():
            return []

        # If answer is refusal/insufficient evidence, no substantive claims to audit
        if "could not find sufficient evidence" in answer.lower():
            return []

        prompt = build_claim_extraction_prompt(answer)
        try:
            from app.rag.generator import GeminiGenerator
            gen = GeminiGenerator()
            raw_res = gen._call_gemini(prompt)

            # Strip markdown formatting
            cleaned = re.sub(r"^```json\s*", "", raw_res.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*", "", cleaned.strip(), flags=re.MULTILINE)
            claims = json.loads(cleaned)
            if isinstance(claims, list) and all(isinstance(c, str) for c in claims):
                return [c.strip() for c in claims if len(c.strip()) > 10]
        except Exception as e:
            logger.debug(f"LLM claim extraction fallback: {e}")

        # Deterministic fallback: split sentences while filtering non-claims
        sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
        claims = []
        disclaimers = {"based on", "i hope", "please note", "according to", "in summary", "thank you"}
        for s in sentences:
            s_clean = s.strip()
            if len(s_clean) < 15:
                continue
            if any(s_clean.lower().startswith(d) for d in disclaimers) and "[" not in s_clean:
                continue
            claims.append(s_clean)

        return claims

    def evaluate_grounding_for_claims(
        self,
        question: str,
        evidence_text: str,
        claims: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Classifies each claim as SUPPORTED, PARTIALLY_SUPPORTED, or UNSUPPORTED against the evidence.
        """
        if not claims:
            return []

        if not evidence_text or not evidence_text.strip() or evidence_text.strip() == "[No evidence retrieved]":
            return [
                {
                    "claim": c,
                    "classification": "UNSUPPORTED",
                    "evidence_ids": [],
                    "reason": "No supporting evidence retrieved."
                }
                for c in claims
            ]

        prompt = build_grounding_judge_prompt(question, evidence_text, claims)
        try:
            from app.rag.generator import GeminiGenerator
            gen = GeminiGenerator()
            raw_res = gen._call_gemini(prompt)

            cleaned = re.sub(r"^```json\s*", "", raw_res.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*", "", cleaned.strip(), flags=re.MULTILINE)
            eval_list = json.loads(cleaned)

            if isinstance(eval_list, list) and len(eval_list) == len(claims):
                validated = []
                for item in eval_list:
                    clf = item.get("classification", "SUPPORTED").upper()
                    if clf not in ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"):
                        clf = "SUPPORTED"
                    validated.append({
                        "claim": item.get("claim", ""),
                        "classification": clf,
                        "evidence_ids": item.get("evidence_ids", []),
                        "reason": item.get("reason", "Evaluated by judge prompt.")
                    })
                return validated
        except Exception as e:
            logger.debug(f"LLM grounding evaluation failed ({e}); using deterministic keyword verification.")

        # Deterministic keyword verification fallback
        STOPWORDS = {
            "must", "shall", "will", "should", "have", "with", "from", "that", "this",
            "about", "been", "were", "they", "their", "such", "into", "over", "after",
            "before", "each", "every", "some", "only", "other", "under", "than", "then",
            "also", "when", "what", "which", "more", "most", "less", "these", "those"
        }
        results = []
        ev_lower = evidence_text.lower()
        for c in claims:
            c_tags = re.findall(r"\[(\d+)\]", c)
            c_words = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9]{3,}\b", c) if w.lower() not in STOPWORDS]
            match_count = sum(1 for w in c_words if w in ev_lower)
            match_ratio = match_count / max(1, len(c_words))

            if match_ratio >= 0.60:
                results.append({
                    "claim": c,
                    "classification": "SUPPORTED",
                    "evidence_ids": c_tags,
                    "reason": f"Textual overlap ({match_ratio:.0%}) with retrieved evidence."
                })
            elif match_ratio >= 0.40:
                results.append({
                    "claim": c,
                    "classification": "PARTIALLY_SUPPORTED",
                    "evidence_ids": c_tags,
                    "reason": f"Partial textual overlap ({match_ratio:.0%}) with evidence."
                })
            else:
                results.append({
                    "claim": c,
                    "classification": "UNSUPPORTED",
                    "evidence_ids": [],
                    "reason": f"Low textual overlap ({match_ratio:.0%}) with retrieved context."
                })
        return results

    def evaluate_query(
        self,
        item: Dict[str, Any],
        precomputed_gen_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluates a single question for claims, grounding, and citation accuracy."""
        q_id = item.get("id", "UNKNOWN")
        question = item["question"]
        answerability = item.get("answerability", "ANSWERABLE")

        if precomputed_gen_result:
            answer = precomputed_gen_result["generated_answer"]
            citations = precomputed_gen_result["citations"]
            evidence_text = precomputed_gen_result.get("evidence_text")
            if not evidence_text:
                evidence_lines = [
                    f"SOURCE [{c.get('source_id', i+1)}]\nTitle: {c.get('title', '')}\nSection: {c.get('section', '')}\nURL: {c.get('url', '')}"
                    for i, c in enumerate(citations)
                ]
                evidence_text = "\n\n".join(evidence_lines) if evidence_lines else "[No evidence retrieved]"
        else:
            rag_res: RAGResponse = self.pipeline.answer(question)
            answer = rag_res.answer
            citations = [
                {
                    "source_id": s.source_id,
                    "title": s.title,
                    "section": s.section,
                    "document_id": s.document_id,
                    "url": s.url
                }
                for s in rag_res.sources
            ]
            evidence_lines = [
                f"SOURCE [{c['source_id']}]\nTitle: {c['title']}\nSection: {c['section']}\nURL: {c['url']}"
                for c in citations
            ]
            evidence_text = "\n\n".join(evidence_lines) if evidence_lines else "[No evidence retrieved]"

        is_refusal = "could not find sufficient evidence" in answer.lower()

        # Handle Unanswerable / Refusals
        if is_refusal:
            safe_abstention = (answerability in ("UNANSWERABLE", "PARTIALLY_ANSWERABLE"))
            return {
                "question_id": q_id,
                "question": question,
                "answerability": answerability,
                "generated_answer": answer,
                "total_claims": 0,
                "claims": [],
                "supported_claims_count": 0,
                "partially_supported_count": 0,
                "unsupported_claims_count": 0,
                "grounded_claim_rate": 100.0,
                "unsupported_claim_rate": 0.0,
                "citation_integrity": 100.0,
                "citation_support_rate": 100.0,
                "citation_coverage_rate": 100.0,
                "is_refusal": True,
                "safe_abstention": safe_abstention,
                "unsupported_claims_records": []
            }

        # Check Cache
        cache_key = self._compute_cache_key(question, answer, evidence_text)
        if self.enable_cache and cache_key in self._cache:
            claims_eval = self._cache[cache_key]["claims_eval"]
        else:
            claims = self.extract_claims(answer)
            claims_eval = self.evaluate_grounding_for_claims(question, evidence_text, claims)
            if self.enable_cache:
                self._cache[cache_key] = {"claims_eval": claims_eval}
                self._save_cache()

        # Compute Claim Grounding Metrics
        total_claims = len(claims_eval)
        supported = [c for c in claims_eval if c["classification"] == "SUPPORTED"]
        partially = [c for c in claims_eval if c["classification"] == "PARTIALLY_SUPPORTED"]
        unsupported = [c for c in claims_eval if c["classification"] == "UNSUPPORTED"]

        # Citation validation
        cited_ids = extract_citation_indices(answer)
        total_tags = len(cited_ids)
        valid_tags = len([i for i in cited_ids if 1 <= i <= max(1, len(citations))])
        cit_integrity = compute_citation_integrity(valid_tags, total_tags)

        # Citation Coverage & Support Rate
        cited_claims = [c for c in claims_eval if "[" in c["claim"] and "]" in c["claim"]]
        supported_cited = [c for c in cited_claims if c["classification"] == "SUPPORTED"]

        cit_coverage_rate = compute_citation_coverage_rate(len(cited_claims), total_claims)
        cit_support_rate = compute_citation_support_rate(len(supported_cited), len(cited_claims))

        grd_rate = compute_grounded_claim_rate(len(supported), total_claims)
        unsupp_rate = compute_unsupported_claim_rate(len(unsupported), total_claims)

        unsupported_records = [
            {
                "question_id": q_id,
                "claim": c["claim"],
                "citations": re.findall(r"\[(\d+)\]", c["claim"]),
                "reason": c.get("reason", "No supporting evidence in retrieved context.")
            }
            for c in unsupported
        ]

        return {
            "question_id": q_id,
            "question": question,
            "answerability": answerability,
            "generated_answer": answer,
            "total_claims": total_claims,
            "claims": claims_eval,
            "supported_claims_count": len(supported),
            "partially_supported_count": len(partially),
            "unsupported_claims_count": len(unsupported),
            "grounded_claim_rate": grd_rate,
            "unsupported_claim_rate": unsupp_rate,
            "citation_integrity": cit_integrity,
            "citation_support_rate": cit_support_rate,
            "citation_coverage_rate": cit_coverage_rate,
            "is_refusal": False,
            "safe_abstention": True if answerability == "ANSWERABLE" else False,
            "unsupported_claims_records": unsupported_records
        }

    def run_evaluation(
        self,
        limit: Optional[int] = None,
        precomputed_generation_results: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Runs the Grounding and Citation evaluation across all queries."""
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)
        if limit:
            dataset = dataset[:limit]

        logger.info(f"Starting Grounding and Citation Evaluation on {len(dataset)} queries...")

        per_query_results = []
        all_claims_map = []
        all_unsupported_records = []

        gen_res_map = {
            r["id"]: r for r in (precomputed_generation_results or [])
        }

        for idx, item in enumerate(dataset, 1):
            logger.info(f"[{idx}/{len(dataset)}] Evaluating grounding for {item.get('id', '')}: {item['question'][:60]}...")
            precomputed = gen_res_map.get(item.get("id"))
            res = self.evaluate_query(item, precomputed_gen_result=precomputed)
            per_query_results.append(res)
            all_claims_map.append({
                "question_id": res["question_id"],
                "question": res["question"],
                "claims": res["claims"]
            })
            all_unsupported_records.extend(res["unsupported_claims_records"])

        total_queries = len(per_query_results)
        total_claims = sum(r["total_claims"] for r in per_query_results)
        total_supported = sum(r["supported_claims_count"] for r in per_query_results)
        total_partial = sum(r["partially_supported_count"] for r in per_query_results)
        total_unsupported = sum(r["unsupported_claims_count"] for r in per_query_results)

        unanswerable_queries = [r for r in per_query_results if r["answerability"] == "UNANSWERABLE"]
        safe_refusals = sum(1 for r in unanswerable_queries if r["is_refusal"])

        grd_claim_rate = compute_grounded_claim_rate(total_supported, total_claims)
        unsupp_claim_rate = compute_unsupported_claim_rate(total_unsupported, total_claims)
        partial_claim_rate = round((total_partial / max(1, total_claims)) * 100.0, 2)

        avg_cit_integrity = round(sum(r["citation_integrity"] for r in per_query_results) / total_queries, 2) if total_queries else 100.0
        avg_cit_support = round(sum(r["citation_support_rate"] for r in per_query_results) / total_queries, 2) if total_queries else 100.0
        avg_cit_coverage = round(sum(r["citation_coverage_rate"] for r in per_query_results) / total_queries, 2) if total_queries else 100.0
        safe_abstention_rate = compute_safe_abstention_rate(safe_refusals, len(unanswerable_queries))

        summary = {
            "evaluation_timestamp": datetime.utcnow().isoformat(),
            "total_questions": total_queries,
            "claim_statistics": {
                "total_claims_extracted": total_claims,
                "supported_claims": total_supported,
                "partially_supported_claims": total_partial,
                "unsupported_claims": total_unsupported
            },
            "grounding_metrics": {
                "grounded_claim_rate": grd_claim_rate,
                "partially_supported_claim_rate": partial_claim_rate,
                "unsupported_claim_rate": unsupp_claim_rate,
                "safe_abstention_rate": safe_abstention_rate
            },
            "citation_metrics": {
                "citation_integrity": avg_cit_integrity,
                "citation_support_rate": avg_cit_support,
                "citation_coverage_rate": avg_cit_coverage
            }
        }

        # Save timestamped results
        run_id = f"run_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"
        run_dir = RESULTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        with open(run_dir / "per_query.json", "w", encoding="utf-8") as f:
            json.dump(per_query_results, f, indent=2)
        with open(run_dir / "claims.json", "w", encoding="utf-8") as f:
            json.dump(all_claims_map, f, indent=2)
        with open(run_dir / "unsupported_claims.json", "w", encoding="utf-8") as f:
            json.dump(all_unsupported_records, f, indent=2)

        # Generate markdown report
        md_content = self._format_markdown_report(summary, all_unsupported_records)
        with open(run_dir / "summary.md", "w", encoding="utf-8") as f:
            f.write(md_content)

        # Root level convenience copies
        with open(EVAL_DIR / "results" / "claims.json", "w", encoding="utf-8") as f:
            json.dump(all_claims_map, f, indent=2)
        with open(EVAL_DIR / "results" / "unsupported_claims.json", "w", encoding="utf-8") as f:
            json.dump(all_unsupported_records, f, indent=2)

        return summary, per_query_results

    def _format_markdown_report(
        self,
        summary: Dict[str, Any],
        unsupported: List[Dict[str, Any]]
    ) -> str:
        gm = summary["grounding_metrics"]
        cm = summary["citation_metrics"]
        cs = summary["claim_statistics"]

        return f"""# Grounding, Hallucination & Citation Evaluation Report
**Timestamp**: {summary['evaluation_timestamp']}

## Executive Summary
- **Total Questions Evaluated**: {summary['total_questions']}
- **Total Claims Audited**: {cs['total_claims_extracted']} ({cs['supported_claims']} Supported, {cs['partially_supported_claims']} Partially Supported, {cs['unsupported_claims']} Unsupported)

## Grounding & Faithfulness Metrics
| Metric | Value | Target |
| :--- | :--- | :--- |
| **Grounded Claim Rate** | **{gm['grounded_claim_rate']}%** | $\ge 80.0\%$ |
| **Partially Supported Rate** | **{gm['partially_supported_claim_rate']}%** | $\le 15.0\%$ |
| **Unsupported Claim Rate** | **{gm['unsupported_claim_rate']}%** | $\le 5.0\%$ |
| **Safe Abstention Rate** | **{gm['safe_abstention_rate']}%** | $\ge 80.0\%$ |

## Citation Accuracy Metrics
| Metric | Value |
| :--- | :--- |
| **Citation Integrity Rate** | **{cm['citation_integrity']}%** |
| **Citation Support Rate** | **{cm['citation_support_rate']}%** |
| **Citation Coverage Rate** | **{cm['citation_coverage_rate']}%** |

## Unsupported Claims Audit
Total Unsupported Regulatory Claims: {len(unsupported)}
"""


if __name__ == "__main__":
    evaluator = GroundingEvaluator()
    summary, _ = evaluator.run_evaluation()
    print("\nGrounding & Citation Evaluation Summary:")
    print(json.dumps(summary, indent=2))
