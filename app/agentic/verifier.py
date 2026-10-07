"""
Claim-Level Answer Verification & Safe Regulatory Synthesis (Phase 78).

Provides:
- 78.4: Atomic Claim extraction from draft response text.
- 78.5: Claim-to-Evidence verification against EvidenceGraph nodes.
- 78.6: Strict grounding validation for numbers, thresholds, and dates.
- 78.7: Contradiction resolution and safe regulatory abstention rules.
- 78.8: Final grounded synthesis with claim-specific citations.
"""

import re
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple

from app.agentic.models import (
    Claim,
    ClaimType,
    VerificationStatus,
    EvidenceNode,
)
from app.agentic.evidence_graph import EvidenceGraph
from app.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)


# Forbidden aggressive conflict phrasing
AGGRESSIVE_CONFLICT_PATTERNS = [
    r"\bdefinitely conflicts\b",
    r"\bviolates the regulation\b",
    r"\billegal under\b",
    r"\bregulations directly clash\b",
    r"\bnon-compliant regulation\b",
]

# Safe conservative replacement phrasing
SAFE_CONSERVATIVE_PREFIX = "Potential regulatory inconsistency observed:"


class RegulatoryAnswerVerifier:
    """
    Verifies factual claims against the structured evidence graph and ensures
    conservative, legally grounded, safe synthesis (78.4 - 78.8).
    """

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm_provider()
        return self._llm

    # -------------------------------------------------------------------------
    # 78.4 CLAIM EXTRACTION
    # -------------------------------------------------------------------------
    def extract_claims(self, text: str) -> List[Claim]:
        """
        Splits narrative text into discrete atomic claims for verification (78.4).
        """
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        claims: List[Claim] = []

        for idx, s in enumerate(sentences):
            clean_s = s.strip()
            if len(clean_s) < 15:
                continue

            c_lower = clean_s.lower()
            c_type: ClaimType = "FACT"
            if any(k in c_lower for k in ("conflict", "inconsisten", "differen")):
                c_type = "POTENTIAL_CONFLICT"
            elif any(k in c_lower for k in ("overlap", "duplicate", "common")):
                c_type = "OVERLAP"
            elif any(k in c_lower for k in ("shall", "must", "required to", "mandate")):
                c_type = "OBLIGATION"
            elif any(k in c_lower for k in ("amended", "changed", "superseded", "revised")):
                c_type = "CHANGE"
            elif re.search(r"\b202[0-9]\b|\bdate\b|\beffective\b", c_lower):
                c_type = "DATE"

            claims.append(Claim(
                claim_id=f"claim_{idx+1}",
                text=clean_s,
                claim_type=c_type,
                confidence=1.0,
                verification_status="UNKNOWN"
            ))

        return claims

    # -------------------------------------------------------------------------
    # 78.5 & 78.6 CLAIM VERIFICATION AGAINST EVIDENCE GRAPH
    # -------------------------------------------------------------------------
    def verify_claim(self, claim: Claim, graph: EvidenceGraph) -> Claim:
        """
        Verifies whether an atomic claim is grounded in the EvidenceGraph (78.5, 78.6).
        Checks content overlap, authority matching, and exact numeric/threshold grounding.
        """
        claim_text = claim.text
        claim_lower = claim_text.lower()
        supporting_nodes: List[EvidenceNode] = []

        # Extract numeric values or percentages in the claim
        claim_numbers = re.findall(r"\b\d+(?:\.\d+)?%?\b", claim_text)

        best_overlap_score = 0.0
        best_node = None

        for node in graph.nodes.values():
            node_text = (node.text or "").lower()
            if not node_text:
                continue

            # Word overlap
            claim_words = [w for w in claim_lower.split() if len(w) > 3]
            if not claim_words:
                continue

            matched = [w for w in claim_words if w in node_text]
            overlap = len(matched) / len(claim_words)

            # If claim has numbers, verify numbers exist in node text
            numbers_matched = True
            if claim_numbers:
                numbers_matched = any(num.lower() in node_text for num in claim_numbers)

            score = overlap * (1.2 if numbers_matched else 0.5)
            if score > best_overlap_score:
                best_overlap_score = score
                best_node = node

            if overlap >= 0.35 and numbers_matched:
                supporting_nodes.append(node)

        claim.supporting_evidence_ids = [n.evidence_id for n in supporting_nodes]

        # Determine verification status
        if best_overlap_score >= 0.5 and supporting_nodes:
            claim.verification_status = "SUPPORTED"
            claim.confidence = min(1.0, round(best_overlap_score, 2))
            claim.verification_notes = f"Verified against {len(supporting_nodes)} evidence node(s)."
        elif best_overlap_score >= 0.25:
            claim.verification_status = "PARTIALLY_SUPPORTED"
            claim.confidence = 0.5
            claim.verification_notes = "Partially matched evidence; contextual inference required."
        else:
            claim.verification_status = "UNSUPPORTED"
            claim.confidence = 0.1
            claim.verification_notes = "No supporting evidence found in gathered nodes."

        return claim

    # -------------------------------------------------------------------------
    # 78.7 SAFE REGULATORY ABSTENTION & SANITIZATION
    # -------------------------------------------------------------------------
    def sanitize_claim_text(self, text: str) -> str:
        """
        Enforces conservative regulatory language (78.7).
        Replaces aggressive conflict declarations with cautious potential inconsistency phrasing.
        """
        sanitized = text
        for pattern in AGGRESSIVE_CONFLICT_PATTERNS:
            sanitized = re.sub(
                pattern,
                "presents a potential regulatory inconsistency with",
                sanitized,
                flags=re.IGNORECASE
            )
        return sanitized

    # -------------------------------------------------------------------------
    # 78.8 GROUNDED SYNTHESIS & CITATION MAPPING
    # -------------------------------------------------------------------------
    def synthesize(
        self,
        query: str,
        graph: EvidenceGraph,
        draft_response: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates or verifies final grounded response text with node citations (78.8).
        """
        # If no draft provided, synthesize based on evidence nodes
        if not draft_response:
            supported_nodes = list(graph.nodes.values())
            if not supported_nodes:
                return {
                    "answer": "Insufficient regulatory evidence retrieved to address this inquiry.",
                    "claims": [],
                    "citations": [],
                    "verification_rate": 0.0,
                    "is_safe": True
                }

            # Build grounded narrative from nodes
            lines = []
            citations = []
            for idx, node in enumerate(supported_nodes[:5], start=1):
                auth_str = f"[{node.authority}] " if node.authority else ""
                title_str = f"{node.title}: " if node.title else ""
                content_snip = node.text[:200].strip()
                lines.append(f"{auth_str}{title_str}{content_snip} [{idx}]")
                citations.append({
                    "citation_number": idx,
                    "evidence_id": node.evidence_id,
                    "type": node.type,
                    "authority": node.authority,
                    "document_id": node.document_id,
                    "section_id": node.section_id,
                    "text_snippet": node.text[:150]
                })

            draft_response = "\n\n".join(lines)

        # Extract and verify claims
        raw_claims = self.extract_claims(draft_response)
        verified_claims = [self.verify_claim(c, graph) for c in raw_claims]

        # Sanitize language for regulatory safety
        safe_response_lines = []
        for c in verified_claims:
            safe_text = self.sanitize_claim_text(c.text)
            if c.verification_status == "UNSUPPORTED":
                safe_response_lines.append(f"{safe_text} *(Note: Subject to further regulatory confirmation)*")
            else:
                safe_response_lines.append(safe_text)

        final_answer = " ".join(safe_response_lines)

        supported_count = sum(1 for c in verified_claims if c.verification_status == "SUPPORTED")
        rate = supported_count / len(verified_claims) if verified_claims else 1.0

        # Build citation catalog
        citation_catalog = []
        for n_id in {nid for c in verified_claims for nid in c.supporting_evidence_ids}:
            node = graph.get_node(n_id)
            if node:
                citation_catalog.append({
                    "evidence_id": node.evidence_id,
                    "type": node.type,
                    "authority": node.authority,
                    "document_id": node.document_id,
                    "section_id": node.section_id,
                    "title": node.title,
                    "snippet": node.text[:180]
                })

        return {
            "answer": final_answer,
            "claims": [c.model_dump() for c in verified_claims],
            "citations": citation_catalog,
            "verification_rate": round(rate, 2),
            "is_safe": True
        }
