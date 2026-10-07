"""
Unit Tests for Phase 75: Query Decomposition & Intent Planning Engine.
Tests:
- Deterministic signal detection and authority extraction.
- Intent classification and capability flag population.
- Complexity level categorization (SIMPLE, MODERATE, COMPLEX, AGENTIC).
- Decomposition DAG generation and topological stage execution order.
- Query rewriting logic.
- Complete QueryPlan creation and fast-path identification.
"""

import pytest
from app.agentic.planner import QueryPlanner
from app.agentic.models import QueryIntent, QueryType, QueryComplexity, QueryPlan


@pytest.fixture
def planner():
    return QueryPlanner(llm_provider=None)


class TestPhase75SignalDetection:
    def test_detect_deterministic_signals(self, planner):
        q = "Compare the cybersecurity audit requirements between SEBI and RBI, and what changed in 2024?"
        signals = planner.detect_signals(q)
        assert signals["comparison"] is True
        assert signals["change"] is True
        assert signals["requirement"] is True
        assert signals["temporal"] is True

    def test_detect_authorities(self, planner):
        q = "How does IRDAI cloud security guidance compare to IFSCA circulars?"
        auths = planner.detect_authorities(q)
        assert "IRDAI" in auths
        assert "IFSCA" in auths
        assert "SEBI" not in auths


class TestPhase75IntentClassification:
    def test_classify_simple_factual(self, planner):
        q = "What is the definition of net owned funds?"
        intent = planner.classify_intent(q)
        assert intent.complexity == "SIMPLE"
        assert intent.dominant_query_type in ("FACTUAL", "DEFINITION")
        assert not intent.requires_cross_regulator

    def test_classify_comparison(self, planner):
        q = "Compare the risk management committee guidelines of SEBI and RBI"
        intent = planner.classify_intent(q)
        assert intent.requires_comparison is True
        assert intent.requires_cross_regulator is True
        assert set(intent.target_authorities) == {"SEBI", "RBI"}
        assert intent.complexity in ("MODERATE", "COMPLEX", "AGENTIC")

    def test_classify_change_analysis(self, planner):
        q = "What changed in the SEBI LODR 2023 amendment regarding related party transactions?"
        intent = planner.classify_intent(q)
        assert intent.dominant_query_type == "CHANGE_ANALYSIS"
        assert intent.requires_timeline is True
        assert intent.requires_section_diff is True
        assert intent.complexity in ("MODERATE", "COMPLEX")

    def test_classify_conflict_query(self, planner):
        q = "Is there any potential conflict or inconsistency between RBI and SEBI KYC norms?"
        intent = planner.classify_intent(q)
        assert intent.dominant_query_type == "CONFLICT"
        assert intent.requires_conflict_detection is True
        assert intent.complexity in ("COMPLEX", "AGENTIC")

    def test_classify_overlap_query(self, planner):
        q = "Where is the regulatory overlap between PFRDA and IRDAI regarding annuity products?"
        intent = planner.classify_intent(q)
        assert intent.dominant_query_type == "OVERLAP"
        assert intent.requires_overlap_detection is True

    def test_classify_compliance_impact(self, planner):
        q = "Provide a compliance checklist and audit obligations for new merchant bankers under SEBI"
        intent = planner.classify_intent(q)
        assert intent.dominant_query_type in ("COMPLIANCE", "COMPLIANCE_IMPACT")
        assert intent.requires_compliance_checklist is True
        assert intent.requires_obligations is True


class TestPhase75DecompositionAndStages:
    def test_comparison_decomposition(self, planner):
        q = "Compare insider trading penalties under SEBI vs RBI market abuse rules"
        intent = planner.classify_intent(q)
        subquestions = planner.decompose_query(q, intent)
        
        assert len(subquestions) >= 3
        # First two should have no dependencies
        assert subquestions[0].dependencies == []
        assert subquestions[1].dependencies == []
        # Third is the comparison synthesis, depending on the previous
        assert len(subquestions[2].dependencies) == 2

        # Verify staged execution DAG
        stages = planner.build_execution_stages(subquestions)
        assert len(stages) >= 2
        # Stage 0 has independent retrievals
        assert len(stages[0]) >= 2
        # Stage 1 has dependent synthesis
        assert len(stages[1]) >= 1

    def test_change_analysis_decomposition(self, planner):
        q = "What changed in the digital lending guidelines?"
        intent = planner.classify_intent(q)
        subquestions = planner.decompose_query(q, intent)
        assert len(subquestions) >= 2
        stages = planner.build_execution_stages(subquestions)
        assert len(stages) >= 2

    def test_query_rewriting(self, planner):
        raw = "Please tell me what are the specific escrow account obligations for payment aggregators?"
        rewritten = planner.rewrite_query(raw, target_authority="RBI", query_type="OBLIGATION")
        assert not rewritten.lower().startswith("please tell me")
        assert "RBI" in rewritten or "obligation" in rewritten.lower()

    def test_create_complete_plan(self, planner):
        q = "Compare cybersecurity risk management guidelines between IRDAI and SEBI"
        plan = planner.create_plan(q)
        assert isinstance(plan, QueryPlan)
        assert plan.query == q
        assert plan.intent.dominant_query_type in ("COMPARISON", "CROSS_REGULATOR")
        assert len(plan.sub_questions) >= 3
        assert len(plan.execution_stages) >= 2
        assert plan.requires_agentic_loop is True

    def test_simple_plan_fast_path(self, planner):
        q = "What is a depository participant?"
        plan = planner.create_plan(q)
        assert plan.intent.complexity == "SIMPLE"
        assert plan.requires_agentic_loop is False
        assert len(plan.sub_questions) == 1
