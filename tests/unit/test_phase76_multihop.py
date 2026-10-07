"""
Unit Tests for Phase 76: Adaptive Multi-Hop Retrieval Loop.
Tests:
- Evidence sufficiency evaluation (empty, sufficient, partial missing authority).
- Loop prevention and cycle detection.
- Multi-hop evidence deduplication (retaining max score).
- Query reformulation and keyword expansion.
- Hop budget enforcement (max_hops, latency limit).
- Staged execution with mock retrieval executor and adaptive retry.
"""

import pytest
from app.agentic.models import QueryPlan, SubQuestion, QueryIntent, HopBudget
from app.agentic.retrieval_loop import (
    AdaptiveRetrievalLoop,
    evaluate_evidence_sufficiency,
    SufficiencyAssessment
)


class TestPhase76SufficiencyEvaluation:
    def test_evaluate_empty_evidence(self):
        assessment = evaluate_evidence_sufficiency(
            query="What is net owned funds for NBFCs?",
            retrieved_evidence=[],
            target_authorities=["RBI"]
        )
        assert assessment.is_sufficient is False
        assert assessment.sufficiency_status == "INSUFFICIENT"
        assert assessment.confidence == 0.0
        assert "No evidence retrieved" in assessment.missing_aspects

    def test_evaluate_sufficient_evidence(self):
        evidence = [
            {
                "id": "chunk_1",
                "content": "Net Owned Funds (NOF) requirement for NBFCs is set at INR 10 crore by RBI.",
                "authority": "RBI",
                "score": 0.85
            },
            {
                "id": "chunk_2",
                "content": "RBI Master Direction on NBFC capital adequacy and net owned funds guidelines.",
                "authority": "RBI",
                "score": 0.78
            }
        ]
        assessment = evaluate_evidence_sufficiency(
            query="What is net owned funds for NBFCs?",
            retrieved_evidence=evidence,
            target_authorities=["RBI"]
        )
        assert assessment.is_sufficient is True
        assert assessment.sufficiency_status == "SUFFICIENT"
        assert assessment.confidence >= 0.7

    def test_evaluate_partial_missing_authority(self):
        # Query requires both SEBI and RBI, but only SEBI evidence is present
        evidence = [
            {
                "id": "sebi_chunk",
                "content": "SEBI cybersecurity audit framework requires annual audit by CERT-In empaneled auditor.",
                "authority": "SEBI",
                "score": 0.82
            }
        ]
        assessment = evaluate_evidence_sufficiency(
            query="Compare cybersecurity audit requirements between SEBI and RBI",
            retrieved_evidence=evidence,
            target_authorities=["SEBI", "RBI"]
        )
        assert assessment.is_sufficient is False
        assert assessment.sufficiency_status == "PARTIAL"
        assert any("RBI" in a for a in assessment.missing_aspects)
        assert assessment.recommended_action == "TARGET_MISSING_AUTHORITY"


class TestPhase76LoopPreventionAndDeduplication:
    def test_loop_prevention(self):
        loop = AdaptiveRetrievalLoop()
        query = "sebi kyc guidelines"
        assert loop.is_loop(query) is False

        loop.mark_visited(query, [{"id": "c1", "content": "test"}])
        assert loop.is_loop(query) is True
        assert loop.is_loop("  SEBI KYC GUIDELINES  ") is True

    def test_query_reformulation(self):
        loop = AdaptiveRetrievalLoop()
        loop.mark_visited("sebi kyc guidelines", [])

        # Reformulate with missing authority
        expanded = loop.reformulate_query(
            "sebi kyc guidelines",
            ["Missing evidence from authority: RBI"],
            authority="RBI"
        )
        assert "RBI" in expanded

    def test_evidence_deduplication(self):
        loop = AdaptiveRetrievalLoop()
        item1 = {"id": "c1", "content": "Common text", "score": 0.6}
        item2 = {"id": "c2", "content": "Distinct text", "score": 0.7}
        loop.deduplicate_evidence([item1, item2])
        assert len(loop.accumulated_evidence) == 2

        # Add duplicate item1 with higher score
        item1_better = {"id": "c1", "content": "Common text", "score": 0.95}
        item3 = {"id": "c3", "content": "New text", "score": 0.5}
        added = loop.deduplicate_evidence([item1_better, item3])

        assert len(loop.accumulated_evidence) == 3
        # Ensure item1 score updated to 0.95
        c1_item = next(it for it in loop.accumulated_evidence if it["id"] == "c1")
        assert c1_item["score"] == 0.95
        assert len(added) == 1  # Only c3 is newly added


class TestPhase76BudgetEnforcement:
    def test_max_hops_enforcement(self):
        # Create a mock query plan with 4 subquestions across 2 stages
        intent = QueryIntent(
            query_id="q_test",
            original_query="Complex cross-regulator query",
            authorities=["SEBI", "RBI"]
        )
        sqs = [
            SubQuestion(id=f"sq_{i}", text=f"Subquestion {i}", authority_scope="SEBI")
            for i in range(1, 5)
        ]
        plan = QueryPlan(
            plan_id="p_test",
            query_id="q_test",
            original_query="Complex cross-regulator query",
            intent=intent,
            sub_questions=sqs,
            execution_order=[["sq_1", "sq_2"], ["sq_3", "sq_4"]]
        )

        def mock_executor(retrieval_type, query, authority, sub_question):
            return [{"id": f"chunk_{sub_question.id}", "content": f"Evidence for {query}", "score": 0.8, "authority": authority}]

        loop = AdaptiveRetrievalLoop(tool_executor=mock_executor)
        # Limit budget to 2 hops
        budget = HopBudget(max_hops=2)
        result = loop.execute_plan(plan, budget=budget)

        assert result["total_hops"] <= 2
        assert len(result["hops"]) <= 2

    def test_adaptive_retry_on_insufficient(self):
        # Subquestion that returns empty first, then returns evidence on retry
        intent = QueryIntent(
            query_id="q_test2",
            original_query="Retry query",
            authorities=["SEBI"]
        )
        sq = SubQuestion(id="sq_1", text="Search difficult term", authority_scope="SEBI")
        plan = QueryPlan(
            plan_id="p_test2",
            query_id="q_test2",
            original_query="Retry query",
            intent=intent,
            sub_questions=[sq],
            execution_order=[["sq_1"]]
        )

        call_count = 0
        def mock_executor(retrieval_type, query, authority, sub_question):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return []  # First call empty
            return [{"id": "chunk_retry", "content": "Recovered content", "score": 0.85, "authority": "SEBI"}]

        loop = AdaptiveRetrievalLoop(tool_executor=mock_executor)
        budget = HopBudget(max_hops=5)
        result = loop.execute_plan(plan, budget=budget)

        # First hop was empty -> triggered adaptive retry hop -> total hops = 2
        assert result["total_hops"] == 2
        assert result["hops"][0].status == "EMPTY"
        assert result["hops"][1].status == "SUCCESS"
        assert len(result["evidence"]) == 1
