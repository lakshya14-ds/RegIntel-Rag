"""
Multi-Hop Regulatory Evidence Graph (Phase 78).

Provides:
- 78.1: In-memory typed EvidenceNode representation.
- 78.2: Directed, typed EvidenceEdge representation.
- 78.3: Dynamic graph builder converting multi-hop retrieval items into relational graph structures.
- 78.4: Graph traversal, neighborhood inspection, and topological summaries.
"""

import uuid
import logging
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field

from app.agentic.models import (
    EvidenceNode,
    EvidenceEdge,
    EvidenceNodeType,
    EvidenceEdgeType,
)

logger = logging.getLogger(__name__)


class EvidenceGraph:
    """
    In-memory directed relational graph linking regulatory documents, versions,
    sections, chunks, requirements, obligations, overlaps, and conflicts (78.1 - 78.3).
    """

    def __init__(self):
        self.nodes: Dict[str, EvidenceNode] = {}
        self.edges: List[EvidenceEdge] = []

    def clear(self):
        self.nodes.clear()
        self.edges.clear()

    # -------------------------------------------------------------------------
    # NODE & EDGE MUTATION
    # -------------------------------------------------------------------------

    def add_node(self, node: EvidenceNode) -> str:
        """Adds or updates an evidence vertex."""
        self.nodes[node.evidence_id] = node
        return node.evidence_id

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        rel_type: EvidenceEdgeType,
        evidence: Optional[str] = None,
        confidence: float = 1.0
    ) -> EvidenceEdge:
        """Adds a directed relation between two existing nodes."""
        edge = EvidenceEdge(
            edge_id=f"edge_{uuid.uuid4().hex[:8]}",
            from_id=from_id,
            to_id=to_id,
            relationship_type=rel_type,
            evidence=evidence,
            confidence=confidence
        )
        self.edges.append(edge)
        return edge

    # -------------------------------------------------------------------------
    # GRAPH TRAVERSAL & QUERYING
    # -------------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[EvidenceNode]:
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, node_type: EvidenceNodeType) -> List[EvidenceNode]:
        return [n for n in self.nodes.values() if n.type == node_type]

    def get_nodes_by_authority(self, authority: str) -> List[EvidenceNode]:
        auth_upper = authority.upper()
        return [n for n in self.nodes.values() if n.authority and n.authority.upper() == auth_upper]

    def get_edges_from(self, node_id: str) -> List[EvidenceEdge]:
        return [e for e in self.edges if e.from_id == node_id]

    def get_edges_to(self, node_id: str) -> List[EvidenceEdge]:
        return [e for e in self.edges if e.to_id == node_id]

    def get_neighbors(self, node_id: str) -> List[EvidenceNode]:
        neighbor_ids = set()
        for e in self.edges:
            if e.from_id == node_id:
                neighbor_ids.add(e.to_id)
            elif e.to_id == node_id:
                neighbor_ids.add(e.from_id)
        return [self.nodes[nid] for nid in neighbor_ids if nid in self.nodes]

    # -------------------------------------------------------------------------
    # 78.3 POPULATION FROM RETRIEVAL EVIDENCE
    # -------------------------------------------------------------------------

    def build_from_evidence_items(self, items: List[Dict[str, Any]]):
        """
        Ingests multi-hop evidence items and constructs typed nodes with relational edges.
        """
        for item in items:
            raw_id = str(
                item.get("evidence_id")
                or item.get("id")
                or item.get("chunk_id")
                or item.get("requirement_id")
                or item.get("obligation_id")
                or item.get("overlap_id")
                or item.get("conflict_id")
                or f"ev_{uuid.uuid4().hex[:8]}"
            )

            # Detect node type
            node_type: EvidenceNodeType = "CHUNK"
            if "overlap_id" in item or item.get("overlap_type"):
                node_type = "OVERLAP"
            elif "conflict_id" in item or item.get("conflict_type"):
                node_type = "CONFLICT"
            elif "obligation_id" in item or "action_required" in item:
                node_type = "OBLIGATION"
            elif "requirement_id" in item or "requirement_text" in item:
                node_type = "REQUIREMENT"
            elif "change_type" in item or "modified_sections" in item:
                node_type = "CHANGE"
            elif "milestones" in item:
                node_type = "TIMELINE_EVENT"
            elif "control_name" in item:
                node_type = "CHECKLIST"
            elif item.get("type") == "DOCUMENT" or "document_id" in item and "text" not in item:
                node_type = "DOCUMENT"

            text_content = (
                item.get("text")
                or item.get("content")
                or item.get("requirement_text")
                or item.get("action_required")
                or item.get("explanation")
                or item.get("summary")
                or ""
            )

            authority = (
                item.get("authority")
                or item.get("regulatory_authority")
                or item.get("regulator")
                or item.get("authority_a")
            )

            node = EvidenceNode(
                evidence_id=raw_id,
                type=node_type,
                authority=str(authority).upper() if authority else None,
                document_id=item.get("document_id"),
                document_version_id=str(item.get("version_number", "1.0")),
                section_id=item.get("section_id") or item.get("section"),
                chunk_id=item.get("chunk_id"),
                requirement_id=item.get("requirement_id"),
                obligation_id=item.get("obligation_id"),
                title=item.get("title") or item.get("topic"),
                text=text_content,
                relevance_score=float(item.get("relevance_score") or item.get("score", 0.8)),
                metadata={k: v for k, v in item.items() if k not in ("text", "content")}
            )
            self.add_node(node)

        # Build relational edges across created nodes
        self._link_relational_edges()

    def _link_relational_edges(self):
        """Automatically infers and creates inter-node relational edges."""
        req_nodes = self.get_nodes_by_type("REQUIREMENT")
        ob_nodes = self.get_nodes_by_type("OBLIGATION")
        chunk_nodes = self.get_nodes_by_type("CHUNK")
        overlap_nodes = self.get_nodes_by_type("OVERLAP")
        conflict_nodes = self.get_nodes_by_type("CONFLICT")

        # 1. Link obligations to matching requirements
        for ob in ob_nodes:
            topic = ob.metadata.get("topic")
            auth = ob.authority
            for req in req_nodes:
                if req.authority == auth and topic and req.metadata.get("topic") == topic:
                    self.add_edge(ob.evidence_id, req.evidence_id, "IMPLEMENTS", confidence=0.9)

        # 2. Link requirements to supporting chunks
        for req in req_nodes:
            auth = req.authority
            for chk in chunk_nodes:
                if chk.authority == auth:
                    self.add_edge(req.evidence_id, chk.evidence_id, "SUPPORTS", confidence=0.85)

        # 3. Link overlaps and conflicts across authorities
        for ov in overlap_nodes:
            auth_a = ov.metadata.get("authority_a")
            auth_b = ov.metadata.get("authority_b")
            topic = ov.metadata.get("topic")
            for node in self.nodes.values():
                if node.evidence_id != ov.evidence_id and node.authority in (auth_a, auth_b):
                    if topic and node.metadata.get("topic") == topic:
                        self.add_edge(ov.evidence_id, node.evidence_id, "OVERLAPS", confidence=0.95)

        for cf in conflict_nodes:
            auth_a = cf.metadata.get("authority_a")
            auth_b = cf.metadata.get("authority_b")
            topic = cf.metadata.get("topic")
            for node in self.nodes.values():
                if node.evidence_id != cf.evidence_id and node.authority in (auth_a, auth_b):
                    if topic and node.metadata.get("topic") == topic:
                        self.add_edge(cf.evidence_id, node.evidence_id, "POTENTIALLY_CONFLICTS", confidence=0.95)

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Provides high-level graph topology and entity distribution."""
        authorities = set(n.authority for n in self.nodes.values() if n.authority)
        types_count: Dict[str, int] = {}
        for n in self.nodes.values():
            types_count[n.type] = types_count.get(n.type, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "authorities": list(authorities),
            "node_types": types_count
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.model_dump() for n in self.nodes.values()],
            "edges": [e.model_dump() for e in self.edges],
            "summary": self.summary()
        }
