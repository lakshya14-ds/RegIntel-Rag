"""
Agentic RAG Orchestrator (Phase 78).

Coordinates:
1. Query Understanding & DAG Planning (Phase 75)
2. Fast-path routing for SIMPLE / FACTUAL inquiries
3. Adaptive Multi-Hop Retrieval Loop (Phase 76)
4. Read-Only Regulatory Tool Execution & Strategy Routing (Phase 77)
5. Evidence Graph Building, Claim Verification & Safe Synthesis (Phase 78)
6. Non-CoT Operational Stepper & Audit Trace Persistence
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional

from app.agentic.models import (
    QueryIntent,
    QueryPlan,
    HopBudget,
    AgenticRAGResponse,
)
from app.agentic.planner import QueryPlanner
from app.agentic.retrieval_loop import AdaptiveRetrievalLoop
from app.agentic.tools import ToolRegistry
from app.agentic.strategy_router import RetrievalStrategyRouter
from app.agentic.evidence_graph import EvidenceGraph
from app.agentic.verifier import RegulatoryAnswerVerifier

logger = logging.getLogger(__name__)


class AgenticRAGOrchestrator:
    """
    Unified entry point for Agentic & Multi-Hop RAG workflows.
    Protects user experience by preserving fast-path single-hop retrieval for simple queries,
    while dynamically invoking multi-hop decomposition, evidence graph construction, and
    claim verification for complex cross-regulator and change-detection inquiries (75 - 78).
    """

    def __init__(
        self,
        planner: Optional[QueryPlanner] = None,
        registry: Optional[ToolRegistry] = None,
        router: Optional[RetrievalStrategyRouter] = None,
        verifier: Optional[RegulatoryAnswerVerifier] = None
    ):
        self.planner = planner or QueryPlanner()
        self.registry = registry or ToolRegistry()
        self.router = router or RetrievalStrategyRouter(self.registry)
        self.retrieval_loop = AdaptiveRetrievalLoop(
            tool_executor=self.router.create_tool_executor()
        )
        self.verifier = verifier or RegulatoryAnswerVerifier()

        # In-memory audit traces keyed by query_id
        self._traces: Dict[str, Dict[str, Any]] = {}

    def plan_query(self, query: str) -> QueryPlan:
        """Inspects and plans query execution without running retrieval."""
        return self.planner.create_plan(query)

    def get_trace(self, query_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves structured operational trace for audit inspection."""
        return self._traces.get(query_id)

    def answer(
        self,
        query: str,
        force_agentic: bool = False,
        budget: Optional[HopBudget] = None
    ) -> AgenticRAGResponse:
        """
        Executes end-to-end question answering.
        Selects fast-path for simple factual questions and agentic multi-hop pipeline for complex queries.
        """
        start_time = time.perf_counter()
        intent = self.planner.classify_intent(query)
        q_id = intent.query_id
        operational_steps: List[str] = ["Classified query intent and complexity tier"]

        # ---------------------------------------------------------------------
        # FAST PATH (SIMPLE FACTUAL)
        # ---------------------------------------------------------------------
        if intent.complexity == "SIMPLE" and not force_agentic:
            operational_steps.append("Simple inquiry identified - executing fast-path direct retrieval")
            auth = intent.authorities[0] if intent.authorities else None
            chunks = self.registry.search_chunks(query=query, authority=auth, limit=3)
            operational_steps.append("Synthesizing direct grounded answer")

            graph = EvidenceGraph()
            graph.build_from_evidence_items(chunks)
            synthesis = self.verifier.synthesize(query=query, graph=graph)
            elapsed = time.perf_counter() - start_time

            resp = AgenticRAGResponse(
                query_id=q_id,
                question=query,
                answer=synthesis["answer"],
                is_agentic=False,
                fast_path_used=True,
                strategy_used="DIRECT",
                plan=None,
                total_hops=1,
                total_evidence_count=len(chunks),
                verification_rate=synthesis["verification_rate"],
                verified_claims=synthesis["claims"],
                citations=synthesis["citations"],
                evidence_graph_summary=graph.summary(),
                operational_steps=operational_steps,
                execution_time_seconds=round(elapsed, 3)
            )
            self._traces[q_id] = resp.model_dump()
            return resp

        # ---------------------------------------------------------------------
        # AGENTIC MULTI-HOP PATH
        # ---------------------------------------------------------------------
        operational_steps.append("Complex multi-hop inquiry identified - generating DAG execution plan")
        plan = self.planner.create_plan(query)
        strategy = self.router.determine_strategy(intent)
        operational_steps.append(f"Assigned retrieval strategy: {strategy}")

        # Execute multi-hop retrieval
        operational_steps.append(f"Executing adaptive multi-hop loop across {len(plan.execution_order)} stages")
        loop_result = self.retrieval_loop.execute_plan(plan, budget=budget)
        operational_steps.append(f"Retrieved {loop_result['total_evidence_count']} evidence items in {loop_result['total_hops']} hops")

        # Build in-memory evidence graph
        operational_steps.append("Building relational evidence graph and resolving entity links")
        graph = EvidenceGraph()
        graph.build_from_evidence_items(loop_result["evidence"])

        # Verification & Safe synthesis
        operational_steps.append("Verifying factual claims and enforcing conservative regulatory phrasing")
        synthesis = self.verifier.synthesize(query=query, graph=graph)
        operational_steps.append("Grounded answer synthesis completed")

        elapsed = time.perf_counter() - start_time

        resp = AgenticRAGResponse(
            query_id=q_id,
            question=query,
            answer=synthesis["answer"],
            is_agentic=True,
            fast_path_used=False,
            strategy_used=strategy,
            plan=plan.model_dump(),
            total_hops=loop_result["total_hops"],
            total_evidence_count=loop_result["total_evidence_count"],
            verification_rate=synthesis["verification_rate"],
            verified_claims=synthesis["claims"],
            citations=synthesis["citations"],
            evidence_graph_summary=graph.summary(),
            operational_steps=operational_steps,
            execution_time_seconds=round(elapsed, 3)
        )

        # Store complete audit trace
        self._traces[q_id] = {
            **resp.model_dump(),
            "hops": [h.model_dump() for h in loop_result["hops"]],
            "evidence_graph": graph.to_dict()
        }

        return resp
