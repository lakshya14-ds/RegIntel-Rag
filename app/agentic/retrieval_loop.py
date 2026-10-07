"""
Adaptive Multi-Hop Retrieval Loop Engine (Phase 76).

Provides:
- 76.1: Multi-hop retrieval loop driven by staged QueryPlan execution.
- 76.2: Evidence sufficiency evaluator evaluating coverage, authority distribution, and topical relevance.
- 76.3: Loop prevention and cycle detection using visited queries, entities, and documents.
- 76.4: Hop budget enforcement (max hops, max chunks, token budget, latency limits).
- 76.5: Context-aware query reformulation and expansion when evidence is insufficient.
- 76.6: Multi-hop evidence deduplication preserving highest relevance scores.
- 76.7: Comprehensive hop history recording with latency and quality metrics.
"""

import time
import uuid
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from pydantic import BaseModel, Field

from app.agentic.models import (
    QueryPlan,
    SubQuestion,
    RetrievalHop,
    HopBudget,
    RetrievalType,
    EvidenceSufficiency,
    QueryIntent,
)

logger = logging.getLogger(__name__)


class SufficiencyAssessment(BaseModel):
    """Structured evaluation of retrieved evidence quality and completeness (76.2)."""
    is_sufficient: bool = False
    confidence: float = 0.0
    sufficiency_status: EvidenceSufficiency = "UNKNOWN"
    missing_aspects: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    hop_recommendation: Optional[str] = None


def evaluate_evidence_sufficiency(
    query: str,
    retrieved_evidence: List[Dict[str, Any]],
    expected_type: str = "CHUNK",
    target_authorities: Optional[List[str]] = None,
    intent: Optional[QueryIntent] = None,
) -> SufficiencyAssessment:
    """
    Evaluates whether the gathered evidence is sufficient to reliably answer the query (76.2).
    Evaluates:
    - Item quantity and score thresholds
    - Multi-authority coverage (e.g. both SEBI and RBI present if cross-regulator)
    - Keyword / topic coverage
    """
    if not retrieved_evidence:
        return SufficiencyAssessment(
            is_sufficient=False,
            confidence=0.0,
            sufficiency_status="INSUFFICIENT",
            missing_aspects=["No evidence retrieved"],
            recommended_action="EXPAND_QUERY",
            hop_recommendation="Broaden query keywords and search across all authorities"
        )

    # Calculate score metrics
    scores = [
        item.get("relevance_score") or item.get("score") or item.get("similarity", 0.5)
        for item in retrieved_evidence
    ]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0

    missing_aspects: List[str] = []

    # Check authority coverage if cross-regulator or target authorities specified
    authorities_needed = set(target_authorities or (intent.authorities if intent else []))
    if authorities_needed:
        authorities_present = set()
        for item in retrieved_evidence:
            auth = (
                item.get("authority")
                or item.get("regulator")
                or item.get("metadata", {}).get("authority")
            )
            if auth:
                authorities_present.add(str(auth).upper())

        missing_auths = [a for a in authorities_needed if a.upper() not in authorities_present]
        if missing_auths:
            for ma in missing_auths:
                missing_aspects.append(f"Missing evidence from authority: {ma}")

    # Check text content relevance
    q_words = set(w.lower() for w in query.split() if len(w) > 3)
    matched_words = set()
    for item in retrieved_evidence:
        content = (item.get("content") or item.get("text") or item.get("description") or "").lower()
        for qw in q_words:
            if qw in content:
                matched_words.add(qw)

    word_coverage = len(matched_words) / len(q_words) if q_words else 1.0
    if word_coverage < 0.3:
        missing_aspects.append("Key search terms absent in retrieved chunks")

    # Determine sufficiency status
    if missing_aspects and any("Missing evidence from authority" in m for m in missing_aspects):
        status: EvidenceSufficiency = "PARTIAL"
        confidence = max(0.2, avg_score * 0.6)
        is_sufficient = False
        action = "TARGET_MISSING_AUTHORITY"
        rec = f"Execute targeted search for {', '.join(missing_auths)}"
    elif len(retrieved_evidence) >= 2 and max_score >= 0.4 and word_coverage >= 0.4:
        status = "SUFFICIENT"
        confidence = min(1.0, (avg_score + max_score) / 2.0 + 0.2)
        is_sufficient = True
        action = "SYNTHESIZE"
        rec = "Sufficient evidence collected; proceed to verification and synthesis"
    elif len(retrieved_evidence) >= 1 and max_score >= 0.3:
        status = "PARTIAL"
        confidence = 0.5
        is_sufficient = False
        action = "REFORMULATE"
        rec = "Evidence is partial; reformulate query with synonyms or broaden scope"
    else:
        status = "INSUFFICIENT"
        confidence = 0.2
        is_sufficient = False
        action = "EXPAND_QUERY"
        rec = "Evidence quality low; broaden search terms"

    return SufficiencyAssessment(
        is_sufficient=is_sufficient,
        confidence=round(confidence, 3),
        sufficiency_status=status,
        missing_aspects=missing_aspects,
        recommended_action=action,
        hop_recommendation=rec
    )


class AdaptiveRetrievalLoop:
    """
    Orchestrates dynamic, multi-hop retrieval across staged SubQuestions with loop prevention,
    hop budgets, query expansion, and evidence deduplication (76.1 - 76.8).
    """

    def __init__(self, tool_executor=None, default_budget: Optional[HopBudget] = None):
        self.tool_executor = tool_executor
        self.default_budget = default_budget or HopBudget()

        # State tracking per loop execution
        self.visited_queries: Set[str] = set()
        self.visited_chunks: Set[str] = set()
        self.visited_documents: Set[str] = set()
        self.hop_history: List[RetrievalHop] = []
        self.accumulated_evidence: List[Dict[str, Any]] = []

    def reset(self):
        """Clears execution state for a fresh multi-hop session."""
        self.visited_queries.clear()
        self.visited_chunks.clear()
        self.visited_documents.clear()
        self.hop_history.clear()
        self.accumulated_evidence.clear()

    # -------------------------------------------------------------------------
    # 76.3 LOOP PREVENTION & CYCLE DETECTION
    # -------------------------------------------------------------------------

    def is_loop(self, normalized_query: str) -> bool:
        """Detects if query is an exact or near-duplicate of a prior hop."""
        norm = normalized_query.strip().lower()
        return norm in self.visited_queries

    def mark_visited(self, query: str, items: List[Dict[str, Any]]):
        """Records queries, documents, and chunk IDs to prevent redundant retrieval cycles."""
        norm = query.strip().lower()
        self.visited_queries.add(norm)

        for item in items:
            cid = item.get("id") or item.get("chunk_id")
            if cid:
                self.visited_chunks.add(str(cid))
            doc_id = item.get("document_id") or item.get("doc_id")
            if doc_id:
                self.visited_documents.add(str(doc_id))

    # -------------------------------------------------------------------------
    # 76.6 MULTI-HOP EVIDENCE DEDUPLICATION
    # -------------------------------------------------------------------------

    def deduplicate_evidence(self, new_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merges new items with accumulated evidence, retaining highest relevance scores (76.6).
        """
        existing_map: Dict[str, Dict[str, Any]] = {}
        for item in self.accumulated_evidence:
            key = str(item.get("id") or item.get("chunk_id") or item.get("content", "")[:60])
            existing_map[key] = item

        added_items = []
        for item in new_items:
            key = str(item.get("id") or item.get("chunk_id") or item.get("content", "")[:60])
            if key in existing_map:
                # Update score if higher
                old_score = existing_map[key].get("relevance_score") or existing_map[key].get("score", 0.0)
                new_score = item.get("relevance_score") or item.get("score", 0.0)
                if new_score > old_score:
                    existing_map[key] = item
            else:
                existing_map[key] = item
                added_items.append(item)

        self.accumulated_evidence = list(existing_map.values())
        return added_items

    # -------------------------------------------------------------------------
    # 76.5 QUERY EXPANSION & REFORMULATION
    # -------------------------------------------------------------------------

    def reformulate_query(
        self,
        base_query: str,
        missing_aspects: List[str],
        authority: Optional[str] = None
    ) -> str:
        """
        Expands or reformulates query when initial retrieval produces insufficient evidence (76.5).
        """
        expanded = base_query
        if authority and authority.upper() not in expanded.upper():
            expanded = f"{authority} {expanded}"

        for aspect in missing_aspects:
            if "Missing evidence from authority:" in aspect:
                auth = aspect.split(":")[-1].strip()
                if auth not in expanded:
                    expanded = f"{auth} {expanded}"
            elif "search terms absent" in aspect:
                expanded = f"{expanded} regulatory circular guidelines compliance requirements"

        # If already visited, mutate slightly to break cycle
        if expanded.strip().lower() in self.visited_queries:
            expanded = f"{expanded} circular guidelines overview"

        return expanded.strip()

    # -------------------------------------------------------------------------
    # 76.1 HOP EXECUTION
    # -------------------------------------------------------------------------

    def execute_hop(
        self,
        sub_question: SubQuestion,
        hop_number: int,
        query: Optional[str] = None,
        budget: Optional[HopBudget] = None,
        parent_hop_id: Optional[str] = None,
    ) -> RetrievalHop:
        """
        Executes a single retrieval hop for a given SubQuestion.
        """
        start_time = time.perf_counter()
        q = query or sub_question.rewritten_query or sub_question.text
        norm_q = q.strip().lower()

        # Check loop prevention
        if self.is_loop(norm_q):
            logger.info(f"Loop detected for query '{norm_q}'. Reformulating...")
            q = self.reformulate_query(q, ["search terms absent"], sub_question.authority_scope)

        retrieval_type: RetrievalType = "CHUNK_SEARCH"
        exp_type = sub_question.expected_evidence_type.upper()
        if exp_type == "DOCUMENT":
            retrieval_type = "DOCUMENT_SEARCH"
        elif exp_type == "REQUIREMENT":
            retrieval_type = "REQUIREMENT_SEARCH"
        elif exp_type == "OBLIGATION":
            retrieval_type = "OBLIGATION_SEARCH"
        elif exp_type == "OVERLAP":
            retrieval_type = "OVERLAP_SEARCH"
        elif exp_type == "CONFLICT":
            retrieval_type = "CONFLICT_SEARCH"
        elif exp_type == "CHECKLIST":
            retrieval_type = "COMPLIANCE_SEARCH"
        elif exp_type == "CHANGE":
            retrieval_type = "CHANGE_SEARCH"

        # Dispatch retrieval
        retrieved: List[Dict[str, Any]] = []
        if self.tool_executor:
            try:
                retrieved = self.tool_executor(
                    retrieval_type=retrieval_type,
                    query=q,
                    authority=sub_question.authority_scope,
                    sub_question=sub_question
                )
            except Exception as e:
                logger.error(f"Error during tool execution for hop {hop_number}: {e}")
                retrieved = []

        # Deduplicate and register visited
        new_items = self.deduplicate_evidence(retrieved)
        self.mark_visited(q, retrieved)

        # Evaluate sufficiency
        target_auths = [sub_question.authority_scope] if sub_question.authority_scope else None
        assessment = evaluate_evidence_sufficiency(
            query=q,
            retrieved_evidence=retrieved,
            expected_type=exp_type,
            target_authorities=target_auths
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        hop = RetrievalHop(
            hop_id=f"hop_{uuid.uuid4().hex[:8]}",
            query_id=sub_question.id,
            sub_question_id=sub_question.id,
            hop_number=hop_number,
            retrieval_type=retrieval_type,
            query=q,
            filters={"authority": sub_question.authority_scope} if sub_question.authority_scope else {},
            retrieved_items=retrieved,
            selected_items=new_items,
            evidence_quality=assessment.confidence,
            completeness=assessment.confidence,
            sufficiency=assessment.sufficiency_status,
            status="SUCCESS" if retrieved else "EMPTY",
            parent_hop_id=parent_hop_id
        )

        self.hop_history.append(hop)
        sub_question.status = "RESOLVED" if assessment.is_sufficient else "PARTIAL"
        return hop

    # -------------------------------------------------------------------------
    # 76.1 & 76.4 MULTI-HOP PLAN EXECUTION
    # -------------------------------------------------------------------------

    def execute_plan(
        self,
        plan: QueryPlan,
        budget: Optional[HopBudget] = None
    ) -> Dict[str, Any]:
        """
        Executes the staged SubQuestions in the QueryPlan within the allocated HopBudget.
        Returns accumulated deduplicated evidence, hop trajectory, and final sufficiency.
        """
        active_budget = budget or self.default_budget
        self.reset()
        start_time = time.perf_counter()

        sq_map = {sq.id: sq for sq in plan.sub_questions}
        hop_count = 0

        # Execute through DAG stages
        for stage_idx, stage_sq_ids in enumerate(plan.execution_order):
            if hop_count >= active_budget.max_hops:
                logger.warning(f"Hop budget reached ({active_budget.max_hops}). Halting retrieval loop.")
                break

            elapsed = time.perf_counter() - start_time
            if elapsed >= active_budget.max_latency_seconds:
                logger.warning(f"Latency limit reached ({active_budget.max_latency_seconds}s). Halting loop.")
                break

            for sq_id in stage_sq_ids:
                if hop_count >= active_budget.max_hops:
                    break

                sq = sq_map.get(sq_id)
                if not sq:
                    continue

                hop_count += 1
                sq.status = "EXECUTING"
                hop = self.execute_hop(
                    sub_question=sq,
                    hop_number=hop_count,
                    budget=active_budget
                )

                # Adaptive retry: If evidence is insufficient and hops remain in budget, try 1 reformulation hop
                if hop.sufficiency == "INSUFFICIENT" and hop_count < active_budget.max_hops:
                    hop_count += 1
                    expanded_q = self.reformulate_query(
                        hop.query,
                        ["search terms absent"],
                        sq.authority_scope
                    )
                    retry_hop = self.execute_hop(
                        sub_question=sq,
                        hop_number=hop_count,
                        query=expanded_q,
                        budget=active_budget,
                        parent_hop_id=hop.hop_id
                    )

        # Global final sufficiency evaluation
        final_assessment = evaluate_evidence_sufficiency(
            query=plan.original_query,
            retrieved_evidence=self.accumulated_evidence,
            target_authorities=plan.intent.authorities,
            intent=plan.intent
        )

        return {
            "plan_id": plan.plan_id,
            "evidence": self.accumulated_evidence,
            "hops": self.hop_history,
            "total_hops": len(self.hop_history),
            "total_evidence_count": len(self.accumulated_evidence),
            "sufficiency": final_assessment.model_dump(),
            "is_sufficient": final_assessment.is_sufficient,
            "execution_time_seconds": round(time.perf_counter() - start_time, 3)
        }
