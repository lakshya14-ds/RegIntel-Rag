"""
Unit Tests for Phase 78: Evidence Graph, Answer Verification & Safe Synthesis.
Tests:
- EvidenceGraph node creation, item ingestion, and relational edge inference.
- Graph traversal and topological neighborhood querying.
- Atomic Claim extraction and claim typing.
- Claim-to-evidence verification with threshold/number grounding.
- Safe regulatory language enforcement and aggressive conflict sanitization.
- AgenticRAGOrchestrator fast-path vs. multi-hop agentic paths and trace auditing.
"""

import pytest
from app.agentic.models import EvidenceNode, Claim
from app.agentic.evidence_graph import EvidenceGraph
from app.agentic.verifier import RegulatoryAnswerVerifier
from app.agentic.orchestrator import AgenticRAGOrchestrator


class TestPhase78EvidenceGraph:
    def test_build_graph_from_items_and_link_edges(self):
        graph = EvidenceGraph()
        items = [
            {
                "requirement_id": "req_1",
                "requirement_text": "SEBI requires annual cybersecurity audit for all brokers.",
                "authority": "SEBI",
                "topic": "CYBERSECURITY",
                "score": 0.9
            },
            {
                "obligation_id": "ob_1",
                "action_required": "Submit CERT-In audit report by June 30 every year.",
                "authority": "SEBI",
                "topic": "CYBERSECURITY",
                "score": 0.85
            },
            {
                "id": "chunk_1",
                "content": "Brokers must appoint empanelled cyber auditors under SEBI circular.",
                "authority": "SEBI",
                "score": 0.8
            },
            {
                "overlap_id": "ov_1",
                "authority_a": "SEBI",
                "authority_b": "RBI",
                "topic": "CYBERSECURITY",
                "explanation": "Shared audit and governance provisions between SEBI and RBI."
            }
        ]
        graph.build_from_evidence_items(items)

        summary = graph.summary()
        assert summary["total_nodes"] == 4
        assert summary["total_edges"] >= 2
        assert "SEBI" in summary["authorities"]

        # Verify edge types inferred
        edge_types = [e.relationship_type for e in graph.edges]
        assert "IMPLEMENTS" in edge_types
        assert "SUPPORTS" in edge_types
        assert "OVERLAPS" in edge_types

    def test_graph_traversal(self):
        graph = EvidenceGraph()
        n1 = EvidenceNode(evidence_id="n1", type="DOCUMENT", text="Base Doc", authority="RBI")
        n2 = EvidenceNode(evidence_id="n2", type="CHUNK", text="Section text", authority="RBI")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge("n1", "n2", "BELONGS_TO")

        neighbors = graph.get_neighbors("n1")
        assert len(neighbors) == 1
        assert neighbors[0].evidence_id == "n2"

        rbi_nodes = graph.get_nodes_by_authority("RBI")
        assert len(rbi_nodes) == 2


class TestPhase78AnswerVerifier:
    def test_claim_extraction(self):
        verifier = RegulatoryAnswerVerifier()
        draft = (
            "Brokers must submit annual cybersecurity audit reports by June 30. "
            "A potential conflict exists between SEBI and RBI regarding reporting timelines. "
            "The amendment was published in 2024."
        )
        claims = verifier.extract_claims(draft)
        assert len(claims) == 3
        types = [c.claim_type for c in claims]
        assert "OBLIGATION" in types
        assert "POTENTIAL_CONFLICT" in types
        assert "DATE" in types

    def test_verify_claim_supported_with_numbers(self):
        verifier = RegulatoryAnswerVerifier()
        graph = EvidenceGraph()
        node = EvidenceNode(
            evidence_id="ev_chunk_1",
            type="CHUNK",
            text="Net Owned Funds requirement for NBFCs is INR 10 crore as mandated by RBI.",
            authority="RBI"
        )
        graph.add_node(node)

        # Claim with matching text and number (10)
        c1 = Claim(
            claim_id="c1",
            text="RBI requires Net Owned Funds of 10 crore for NBFCs."
        )
        verified_c1 = verifier.verify_claim(c1, graph)
        assert verified_c1.verification_status == "SUPPORTED"
        assert "ev_chunk_1" in verified_c1.supporting_evidence_ids

        # Claim with unsupported number (500)
        c2 = Claim(
            claim_id="c2",
            text="RBI requires Net Owned Funds of 500 crore for NBFCs."
        )
        verified_c2 = verifier.verify_claim(c2, graph)
        assert verified_c2.verification_status != "SUPPORTED"

    def test_safe_language_sanitization(self):
        verifier = RegulatoryAnswerVerifier()
        unsafe_text = "The new IRDAI rule definitely conflicts with existing IFSCA directives."
        safe_text = verifier.sanitize_claim_text(unsafe_text)
        assert "definitely conflicts" not in safe_text
        assert "potential regulatory inconsistency" in safe_text


class TestPhase78Orchestrator:
    def test_fast_path_for_simple_inquiry(self):
        orch = AgenticRAGOrchestrator()
        q = "What is the definition of a depository participant?"
        resp = orch.answer(q)

        assert resp.fast_path_used is True
        assert resp.is_agentic is False
        assert resp.total_hops == 1
        assert "fast-path direct retrieval" in " ".join(resp.operational_steps)
        assert len(resp.answer) > 0

    def test_multi_hop_for_complex_query(self):
        orch = AgenticRAGOrchestrator()
        q = "Compare the cybersecurity audit requirements between SEBI and RBI"
        resp = orch.answer(q)

        assert resp.fast_path_used is False
        assert resp.is_agentic is True
        assert resp.strategy_used in ("CROSS_REGULATOR", "AGENTIC_MULTI_HOP")
        assert resp.total_hops >= 2
        assert len(resp.verified_claims) >= 1
        assert resp.evidence_graph_summary["total_nodes"] >= 1

        # Check trace persistence
        trace = orch.get_trace(resp.query_id)
        assert trace is not None
        assert "evidence_graph" in trace
        assert len(trace["hops"]) >= 2
