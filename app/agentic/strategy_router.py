"""
Retrieval Strategy Router & Failure Recovery Engine (Phase 77).

Provides:
- 77.3: Dynamic strategy determination (DIRECT, HYBRID, CROSS_REGULATOR, CHANGE_AWARE, AGENTIC_MULTI_HOP).
- 77.4: Strategy cost classification (LOW, MEDIUM, HIGH).
- 77.5: Tool failure recovery and graceful fallback degradation.
- 77.7: Seamless integration bridging ToolRegistry with AdaptiveRetrievalLoop.
"""

import logging
from typing import Dict, Any, List, Optional, Callable

from app.agentic.models import (
    QueryIntent,
    RetrievalStrategy,
    ToolName,
    ToolCallRecord,
    SubQuestion,
    RetrievalType,
)
from app.agentic.tools import ToolRegistry, TOOL_COST_MAP

logger = logging.getLogger(__name__)


# Fallback mapping when primary specialized tool encounters an error or empty result (77.5)
TOOL_FALLBACK_MAP: Dict[ToolName, ToolName] = {
    "search_requirements": "search_chunks",
    "search_obligations": "search_chunks",
    "get_overlaps": "search_chunks",
    "get_conflicts": "search_chunks",
    "get_changes": "search_chunks",
    "get_compliance_items": "search_chunks",
    "get_timeline": "search_documents",
}


class RetrievalStrategyRouter:
    """
    Directs queries to the optimal retrieval strategy, assesses resource costs,
    and executes tool calls with resilient fallback recovery (77.3, 77.4, 77.5).
    """

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry()

    # -------------------------------------------------------------------------
    # 77.3 STRATEGY ROUTING
    # -------------------------------------------------------------------------
    def determine_strategy(self, intent: QueryIntent) -> RetrievalStrategy:
        """
        Selects retrieval strategy based on structured query intent classification.
        """
        if intent.complexity == "SIMPLE":
            return "DIRECT"

        if intent.requires_cross_regulator_analysis or intent.query_type in ("CROSS_REGULATOR", "OVERLAP", "CONFLICT"):
            return "CROSS_REGULATOR"

        if intent.requires_change_analysis or intent.query_type in ("CHANGE_ANALYSIS", "VERSION_COMPARISON"):
            return "CHANGE_AWARE"

        if intent.requires_compliance_analysis or intent.query_type in ("COMPLIANCE", "OBLIGATION_LOOKUP"):
            return "REQUIREMENT_AWARE"

        if intent.requires_temporal_reasoning or intent.query_type == "TEMPORAL":
            return "TEMPORAL"

        if intent.complexity in ("COMPLEX", "AGENTIC"):
            return "AGENTIC_MULTI_HOP"

        return "HYBRID"

    # -------------------------------------------------------------------------
    # 77.4 COST CLASSIFICATION
    # -------------------------------------------------------------------------
    def estimate_cost(self, strategy: RetrievalStrategy, estimated_hops: int = 1) -> str:
        """Estimates computational / API resource cost for an execution strategy."""
        if strategy == "DIRECT":
            return "LOW"
        if strategy in ("CROSS_REGULATOR", "AGENTIC_MULTI_HOP") or estimated_hops > 3:
            return "HIGH"
        return "MEDIUM"

    # -------------------------------------------------------------------------
    # 77.5 TOOL FAILURE RECOVERY & FALLBACK
    # -------------------------------------------------------------------------
    def execute_with_fallback(
        self,
        tool_name: ToolName,
        arguments: Dict[str, Any]
    ) -> ToolCallRecord:
        """
        Executes primary tool. If an error occurs or no results are returned,
        automatically attempts graceful fallback to a broader retrieval tool (77.5).
        """
        record = self.registry.call_tool(tool_name, arguments)

        if record.status in ("ERROR", "EMPTY"):
            fallback_tool = TOOL_FALLBACK_MAP.get(tool_name)
            if fallback_tool:
                logger.warning(
                    f"Tool '{tool_name}' returned {record.status}. Falling back to '{fallback_tool}'."
                )
                fallback_args = dict(arguments)
                # Map arguments cleanly if falling back to search_chunks
                if fallback_tool == "search_chunks":
                    if "query" not in fallback_args:
                        fallback_args["query"] = (
                            arguments.get("topic")
                            or arguments.get("predecessor_id")
                            or arguments.get("document_id")
                            or "regulatory guidelines"
                        )
                    if "authority_1" in fallback_args:
                        fallback_args["authority"] = fallback_args.pop("authority_1")
                    fallback_args.pop("authority_2", None)
                    fallback_args.pop("topic", None)
                    fallback_args.pop("predecessor_id", None)
                    fallback_args.pop("successor_id", None)

                fb_record = self.registry.call_tool(fallback_tool, fallback_args)
                fb_record.call_id = f"{record.call_id}_fallback"
                return fb_record

        return record

    # -------------------------------------------------------------------------
    # 77.7 BRIDGE TO ADAPTIVE RETRIEVAL LOOP
    # -------------------------------------------------------------------------
    def create_tool_executor(self) -> Callable:
        """
        Builds a callable tool_executor compatible with AdaptiveRetrievalLoop.
        Translates RetrievalType + query into concrete ToolName calls with fallback.
        """
        def executor(
            retrieval_type: RetrievalType,
            query: str,
            authority: Optional[str] = None,
            sub_question: Optional[SubQuestion] = None
        ) -> List[Dict[str, Any]]:
            # Map RetrievalType to primary ToolName
            tool_name: ToolName = "search_chunks"
            args: Dict[str, Any] = {"query": query, "authority": authority}

            if retrieval_type == "DOCUMENT_SEARCH":
                tool_name = "search_documents"
                args = {"query": query, "authority": authority}
            elif retrieval_type == "REQUIREMENT_SEARCH":
                tool_name = "search_requirements"
                args = {"query": query, "authority": authority}
            elif retrieval_type == "OBLIGATION_SEARCH":
                tool_name = "search_obligations"
                args = {"query": query, "authority": authority}
            elif retrieval_type == "OVERLAP_SEARCH":
                tool_name = "get_overlaps"
                args = {"topic": query, "authority_1": authority}
            elif retrieval_type == "CONFLICT_SEARCH":
                tool_name = "get_conflicts"
                args = {"topic": query, "authority_1": authority}
            elif retrieval_type == "CHANGE_SEARCH":
                tool_name = "get_changes"
                args = {"predecessor_id": f"{authority or 'REG'}_v1", "successor_id": f"{authority or 'REG'}_v2"}
            elif retrieval_type == "COMPLIANCE_SEARCH":
                tool_name = "get_compliance_items"
                args = {"category": "GOVERNANCE"}

            record = self.execute_with_fallback(tool_name, args)

            if record.result and isinstance(record.result, dict):
                data = record.result.get("data")
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return [data]
                return [record.result]
            return []

        return executor
