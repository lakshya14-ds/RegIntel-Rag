"""
End-to-End Integration Tests for Stage 5: Agentic / Multi-Hop RAG (Phases 75–78).

Demonstrates complete agentic pipeline via REST API:
1. Query Intent & DAG Planning (/api/rag/plan)
2. Fast-Path Direct Retrieval for Simple Questions (/api/rag/agentic-ask)
3. Adaptive Multi-Hop Retrieval, Evidence Graph Building & Verification (/api/rag/agentic-ask)
4. Comprehensive Trace Audit Inspection (/api/rag/agentic-trace/{query_id})
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestAgenticRAGIntegrationE2E:
    def test_plan_query_endpoint(self, client):
        payload = {"query": "Compare cybersecurity incident reporting between SEBI and RBI"}
        response = client.post("/api/rag/plan", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "plan_id" in data
        assert "sub_questions" in data
        assert len(data["sub_questions"]) >= 3
        assert "execution_order" in data
        assert len(data["execution_order"]) >= 2
        assert "planned_tools" in data

    def test_fast_path_simple_ask(self, client):
        payload = {"query": "What is net owned funds?"}
        response = client.post("/api/rag/agentic-ask", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["fast_path_used"] is True
        assert data["is_agentic"] is False
        assert data["total_hops"] == 1
        assert len(data["answer"]) > 0
        assert "operational_steps" in data
        assert any("fast-path" in s.lower() for s in data["operational_steps"])

    def test_complex_multi_hop_ask(self, client):
        payload = {
            "query": "Compare cybersecurity audit mandates between SEBI and RBI, and identify potential conflicts",
            "max_hops": 4
        }
        response = client.post("/api/rag/agentic-ask", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["is_agentic"] is True
        assert data["fast_path_used"] is False
        assert data["strategy_used"] in ("CROSS_REGULATOR", "AGENTIC_MULTI_HOP")
        assert data["total_hops"] >= 2
        assert len(data["verified_claims"]) >= 1
        assert "evidence_graph_summary" in data
        assert data["evidence_graph_summary"]["total_nodes"] >= 1
        assert len(data["operational_steps"]) >= 5

        # Test trace inspection endpoint
        query_id = data["query_id"]
        trace_resp = client.get(f"/api/rag/agentic-trace/{query_id}")
        assert trace_resp.status_code == 200
        trace_data = trace_resp.json()
        assert trace_data["query_id"] == query_id
        assert "hops" in trace_data
        assert len(trace_data["hops"]) >= 2
        assert "evidence_graph" in trace_data

    def test_force_agentic_flag(self, client):
        payload = {
            "query": "What is net owned funds?",
            "force_agentic": True
        }
        response = client.post("/api/rag/agentic-ask", json=payload)
        assert response.status_code == 200

        data = response.json()
        # forced agentic executes the multi-hop loop even for simple queries
        assert data["is_agentic"] is True
        assert data["fast_path_used"] is False

    def test_trace_not_found(self, client):
        response = client.get("/api/rag/agentic-trace/non_existent_query_9999")
        assert response.status_code == 404
