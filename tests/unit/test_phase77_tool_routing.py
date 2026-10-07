"""
Unit Tests for Phase 77: Agentic Retrieval Strategy & Tool Routing.
Tests:
- ToolRegistry 15 read-only tools presence and successful invocation.
- Structured ToolCallRecord audit logging with latency and cost class.
- Strategy routing based on query intent dimensions.
- Cost classification (LOW, MEDIUM, HIGH).
- Graceful tool failure recovery and fallback to search_chunks.
- Bridge tool_executor integration with AdaptiveRetrievalLoop.
"""

import pytest
from app.agentic.tools import ToolRegistry, TOOL_COST_MAP
from app.agentic.strategy_router import RetrievalStrategyRouter
from app.agentic.models import QueryIntent, SubQuestion
from app.agentic.retrieval_loop import AdaptiveRetrievalLoop


@pytest.fixture
def registry():
    return ToolRegistry()


@pytest.fixture
def router(registry):
    return RetrievalStrategyRouter(registry)


class TestPhase77ToolRegistry:
    def test_all_15_tools_exist_and_callable(self, registry):
        expected_tools = [
            "search_documents",
            "search_chunks",
            "search_requirements",
            "search_obligations",
            "get_document",
            "get_version",
            "get_section",
            "get_timeline",
            "get_changes",
            "get_relationships",
            "get_overlaps",
            "get_conflicts",
            "get_compliance_items",
            "get_effective_state",
            "get_source_evidence",
        ]
        for tool_name in expected_tools:
            assert hasattr(registry, tool_name), f"Tool {tool_name} missing from ToolRegistry"
            assert callable(getattr(registry, tool_name)), f"Tool {tool_name} not callable"

    def test_call_tool_audit_record(self, registry):
        record = registry.call_tool(
            "search_chunks",
            {"query": "cybersecurity audit", "authority": "SEBI", "limit": 2}
        )
        assert record.tool_name == "search_chunks"
        assert record.status == "SUCCESS"
        assert record.latency_ms >= 0.0
        assert record.cost_class == "MEDIUM"
        assert record.result is not None

    def test_call_unknown_tool_returns_error_record(self, registry):
        record = registry.call_tool(
            "non_existent_tool",  # type: ignore
            {"arg": 123}
        )
        assert record.status == "ERROR"
        assert "not recognized" in record.error_message


class TestPhase77StrategyRouter:
    def test_determine_strategy(self, router):
        # 1. Simple factual
        intent_simple = QueryIntent(query_id="q1", original_query="What is NOF?", complexity="SIMPLE")
        assert router.determine_strategy(intent_simple) == "DIRECT"

        # 2. Cross regulator
        intent_cross = QueryIntent(
            query_id="q2",
            original_query="Compare SEBI vs RBI",
            requires_cross_regulator_analysis=True,
            complexity="COMPLEX"
        )
        assert router.determine_strategy(intent_cross) == "CROSS_REGULATOR"

        # 3. Change aware
        intent_change = QueryIntent(
            query_id="q3",
            original_query="What changed in 2024?",
            requires_change_analysis=True,
            complexity="MODERATE"
        )
        assert router.determine_strategy(intent_change) == "CHANGE_AWARE"

        # 4. Compliance aware
        intent_comp = QueryIntent(
            query_id="q4",
            original_query="Compliance checklist for brokers",
            requires_compliance_analysis=True,
            complexity="MODERATE"
        )
        assert router.determine_strategy(intent_comp) == "REQUIREMENT_AWARE"

    def test_estimate_cost(self, router):
        assert router.estimate_cost("DIRECT", estimated_hops=1) == "LOW"
        assert router.estimate_cost("HYBRID", estimated_hops=2) == "MEDIUM"
        assert router.estimate_cost("CROSS_REGULATOR", estimated_hops=4) == "HIGH"
        assert router.estimate_cost("AGENTIC_MULTI_HOP", estimated_hops=5) == "HIGH"

    def test_tool_failure_recovery_fallback(self, router, monkeypatch):
        # Force get_conflicts to fail
        def mock_failing_conflicts(**kwargs):
            raise RuntimeError("Temporary DB connection lost")

        monkeypatch.setattr(router.registry, "get_conflicts", mock_failing_conflicts)

        record = router.execute_with_fallback(
            "get_conflicts",
            {"topic": "escrow", "authority_1": "RBI"}
        )
        # Should have gracefully fallen back to search_chunks and succeeded
        assert record.tool_name == "search_chunks"
        assert record.status == "SUCCESS"
        assert "fallback" in record.call_id


class TestPhase77BridgeIntegration:
    def test_bridge_tool_executor_with_retrieval_loop(self, router):
        executor = router.create_tool_executor()
        assert callable(executor)

        # Execute CHUNK_SEARCH
        chunks = executor(
            retrieval_type="CHUNK_SEARCH",
            query="capital adequacy",
            authority="RBI"
        )
        assert isinstance(chunks, list)
        assert len(chunks) >= 1

        # Execute OVERLAP_SEARCH
        overlaps = executor(
            retrieval_type="OVERLAP_SEARCH",
            query="KYC verification",
            authority="SEBI"
        )
        assert isinstance(overlaps, list)
        assert len(overlaps) >= 1

        # Test within AdaptiveRetrievalLoop
        loop = AdaptiveRetrievalLoop(tool_executor=executor)
        sq = SubQuestion(
            id="sq_test",
            text="Verify RBI capital adequacy requirements",
            authority_scope="RBI",
            expected_evidence_type="REQUIREMENT"
        )
        hop = loop.execute_hop(sq, hop_number=1)
        assert hop.status == "SUCCESS"
        assert len(hop.retrieved_items) >= 1
