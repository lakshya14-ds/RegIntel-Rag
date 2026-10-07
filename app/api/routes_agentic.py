"""
FastAPI Routes for Agentic & Multi-Hop RAG (Phases 75-78).

Exposes:
- POST /api/rag/plan: Generates and inspects decomposed QueryPlan without retrieval execution.
- POST /api/rag/agentic-ask: Executes end-to-end adaptive multi-hop RAG with claim verification.
- GET /api/rag/agentic-trace/{query_id}: Retrieves complete operational audit trace of hops and evidence graph.
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.agentic.models import QueryPlan, AgenticRAGResponse, HopBudget
from app.agentic.orchestrator import AgenticRAGOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["Agentic RAG"])

# Lazy singleton orchestrator
_orchestrator: Optional[AgenticRAGOrchestrator] = None


def get_orchestrator() -> AgenticRAGOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgenticRAGOrchestrator()
    return _orchestrator


class PlanRequest(BaseModel):
    query: str = Field(..., min_length=3, description="User regulatory question or instruction")


class AgenticAskRequest(BaseModel):
    query: str = Field(..., min_length=3, description="User regulatory question or instruction")
    force_agentic: bool = Field(default=False, description="Bypasses fast-path to force multi-hop execution")
    max_hops: Optional[int] = Field(default=5, ge=1, le=10, description="Max allowed retrieval hops")
    authority: Optional[str] = Field(default=None, description="Optional target authority filter")


@router.post("/plan", response_model=Dict[str, Any])
async def plan_query_endpoint(req: PlanRequest):
    """
    Decomposes query into structured QueryPlan with dependency DAG and tool requirements (Phase 75).
    Does not execute retrieval hops.
    """
    try:
        orch = get_orchestrator()
        plan = orch.plan_query(req.query)
        return plan.model_dump()
    except Exception as e:
        logger.error(f"Error planning query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query plan: {str(e)}"
        )


@router.post("/agentic-ask", response_model=Dict[str, Any])
async def agentic_ask_endpoint(req: AgenticAskRequest):
    """
    Executes Agentic Multi-Hop RAG:
    - Fast path for simple factual queries
    - Multi-hop retrieval loop, evidence graph construction, claim verification, and conservative synthesis for complex queries.
    """
    try:
        orch = get_orchestrator()
        budget = HopBudget(max_hops=req.max_hops or 5)
        response = orch.answer(
            query=req.query,
            force_agentic=req.force_agentic,
            budget=budget
        )
        return response.model_dump()
    except Exception as e:
        logger.error(f"Error executing agentic-ask: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agentic RAG execution failed: {str(e)}"
        )


@router.get("/agentic-trace/{query_id}", response_model=Dict[str, Any])
async def get_agentic_trace_endpoint(query_id: str):
    """
    Retrieves the complete audit trail and evidence graph trace for a prior query (Phase 78).
    """
    orch = get_orchestrator()
    trace = orch.get_trace(query_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No trace found for query_id '{query_id}'"
        )
    return trace
