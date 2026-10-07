"""
Agentic & Multi-Hop RAG package for RegIntel.
Phases 75-78: Query decomposition, multi-hop retrieval, tool routing, evidence graph, and safe verification.
"""

from app.agentic.models import (
    QueryIntent,
    SubQuestion,
    QueryPlan,
    QueryType,
    QueryComplexity,
    RetrievalHop,
    HopBudget,
    RetrievalType,
    EvidenceSufficiency,
    ToolName,
    ToolCallRecord,
    AgentState,
    RetrievalStrategy,
    EvidenceNode,
    EvidenceEdge,
    Claim,
    VerificationStatus,
)
from app.agentic.planner import QueryPlanner

__all__ = [
    "QueryIntent",
    "SubQuestion",
    "QueryPlan",
    "QueryType",
    "QueryComplexity",
    "RetrievalHop",
    "HopBudget",
    "RetrievalType",
    "EvidenceSufficiency",
    "ToolName",
    "ToolCallRecord",
    "AgentState",
    "RetrievalStrategy",
    "EvidenceNode",
    "EvidenceEdge",
    "Claim",
    "VerificationStatus",
    "QueryPlanner",
]
