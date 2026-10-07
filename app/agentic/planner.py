"""
Query Decomposition & Intent Planning Engine (Phase 75).

Provides:
- 75.1: Structured QueryIntent classification with boolean capability requirements.
- 75.2 & 75.3: Controlled QueryType and QueryComplexity classification.
- 75.4: Deterministic pre-LLM signal recognition (comparison, changes, temporal, cross-regulator).
- 75.5: LLM query planner refinement via Gemini / Ollama abstraction.
- 75.6 & 75.7: SubQuestion decomposition and dependency DAG ordering.
- 75.8: Pattern-driven planning rules (Comparison, What Changed, Compliance Impact, Cross-Regulator).
- 75.9: Contextual query rewriting for targeted retrieval hops.
"""

import re
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
from app.agentic.models import (
    QueryIntent,
    QueryType,
    QueryComplexity,
    SubQuestion,
    QueryPlan
)
from app.connectors.authority import RegulatoryAuthority
from app.compliance.topic_normalizer import normalize_regulatory_topic
from app.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)


# Deterministic signal regex patterns (75.4)
PATTERN_SIGNALS = {
    "comparison": [r"\bcompare\b", r"\bversus\b", r"\bvs\.?\b", r"\bdifference\b", r"\bdiffer\b", r"\bcontrast\b"],
    "change": [r"\bwhat changed\b", r"\bchanged\b", r"\bamended\b", r"\bsuperseded\b", r"\bmodified\b", r"\bbefore and after\b", r"\bpredecessor\b", r"\bnew vs old\b"],
    "temporal": [r"\bas of\b", r"\beffective date\b", r"\bcome into force\b", r"\btimeline\b", r"\bcurrent version\b", r"\bhistorical\b", r"\bin 202[0-9]\b", r"\b202[0-9]\b"],
    "cross_regulator": [r"\bacross regulators\b", r"\bboth sebi and rbi\b", r"\brbi and sebi\b", r"\bsebi vs rbi\b", r"\brbi vs sebi\b", r"\birdai and ifsca\b", r"\bpfrda\b", r"\bmultiple authorities\b"],
    "compliance": [r"\bcompliance\b", r"\bchecklists?\b", r"\bcontrols?\b", r"\bhow does this affect compliance\b", r"\bcompliance impact\b", r"\baudit requirements?\b"],
    "requirement": [r"\brequirements?\b", r"\bmandates?\b", r"\brules?\b", r"\bconditions?\b", r"\bthresholds?\b", r"\bfee caps?\b"],
    "obligation": [r"\bobligations?\b", r"\baction required\b", r"\bmust do\b", r"\bshall perform\b", r"\bprohibitions?\b"],
    "overlap": [r"\boverlaps?\b", r"\bduplicates?\b", r"\bcommon provisions?\b", r"\bharmoniz\b"],
    "conflict": [r"\bconflicts?\b", r"\binconsisten\b", r"\bcontradict\b", r"\bclash\b", r"\bdiscrepanc\b"]
}

KNOWN_AUTHORITIES = ["SEBI", "RBI", "IRDAI", "PFRDA", "IFSCA"]


class QueryPlanner:
    """
    Intelligent Query Decomposition & Planning Engine.
    Classifies intent, determines complexity, decomposes queries into a DAG of SubQuestions,
    and generates rewritten retrieval queries.
    """

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm_provider()
        return self._llm

    # -------------------------------------------------------------------------
    # 75.4 DETERMINISTIC SIGNAL DETECTION
    # -------------------------------------------------------------------------

    def detect_signals(self, query: str) -> Dict[str, bool]:
        """Detects deterministic regex hints across the user query string."""
        q_lower = query.lower()
        signals = {}
        for signal_name, patterns in PATTERN_SIGNALS.items():
            signals[signal_name] = any(re.search(p, q_lower) for p in patterns)
        return signals

    def detect_authorities(self, query: str) -> List[str]:
        """Extracts mentioned financial regulatory authorities from query."""
        q_upper = query.upper()
        return [auth for auth in KNOWN_AUTHORITIES if auth in q_upper]

    # -------------------------------------------------------------------------
    # 75.1 & 75.3 INTENT & COMPLEXITY CLASSIFICATION
    # -------------------------------------------------------------------------

    def classify_intent(self, query: str) -> QueryIntent:
        """
        Deterministically evaluates query intent and complexity before any expensive LLM calls.
        """
        signals = self.detect_signals(query)
        authorities = self.detect_authorities(query)
        q_id = f"q_{uuid.uuid4().hex[:8]}"

        # Identify dominant query type
        q_type: QueryType = "FACTUAL"
        if signals["conflict"]:
            q_type = "CONFLICT"
        elif signals["overlap"]:
            q_type = "OVERLAP"
        elif len(authorities) > 1 or signals["cross_regulator"]:
            q_type = "CROSS_REGULATOR"
        elif signals["change"] and signals["compliance"]:
            q_type = "COMPLIANCE"
        elif signals["change"]:
            q_type = "CHANGE_ANALYSIS"
        elif signals["comparison"]:
            q_type = "VERSION_COMPARISON" if signals["temporal"] else "MULTI_DOCUMENT"
        elif signals["temporal"]:
            q_type = "TEMPORAL"
        elif signals["compliance"]:
            q_type = "COMPLIANCE"
        elif signals["obligation"]:
            q_type = "OBLIGATION_LOOKUP"
        elif signals["requirement"]:
            q_type = "REQUIREMENT_LOOKUP"
        elif "what is" in query.lower() or "define" in query.lower():
            q_type = "DEFINITION"

        # Determine complexity (75.3)
        complexity: QueryComplexity = "SIMPLE"
        active_signals_count = sum(1 for v in signals.values() if v)

        if signals["cross_regulator"] or (signals["change"] and signals["compliance"]) or (signals["conflict"] and len(authorities) > 1):
            complexity = "AGENTIC"
        elif active_signals_count >= 3 or (signals["comparison"] and signals["change"]) or signals["compliance"]:
            complexity = "COMPLEX"
        elif active_signals_count == 2 or signals["change"] or signals["comparison"] or signals["temporal"]:
            complexity = "MODERATE"
        else:
            complexity = "SIMPLE"

        # Extract topics
        topic = normalize_regulatory_topic(text=query)
        topics = [topic] if topic != "OTHER" else []

        return QueryIntent(
            query_id=q_id,
            original_query=query,
            query_type=q_type,
            complexity=complexity,
            authorities=authorities,
            topics=topics,
            requires_comparison=signals["comparison"] or q_type in ("VERSION_COMPARISON", "CROSS_REGULATOR", "CONFLICT"),
            requires_temporal_reasoning=signals["temporal"] or q_type in ("TEMPORAL", "CHANGE_ANALYSIS"),
            requires_cross_regulator_analysis=signals["cross_regulator"] or len(authorities) > 1 or q_type in ("CROSS_REGULATOR", "OVERLAP", "CONFLICT"),
            requires_relationship_traversal=signals["change"] or q_type in ("CHANGE_ANALYSIS", "COMPLIANCE"),
            requires_requirement_analysis=signals["requirement"] or q_type in ("REQUIREMENT_LOOKUP", "COMPLIANCE", "CHANGE_ANALYSIS"),
            requires_obligation_analysis=signals["obligation"] or q_type in ("OBLIGATION_LOOKUP", "COMPLIANCE"),
            requires_change_analysis=signals["change"] or q_type == "CHANGE_ANALYSIS",
            requires_compliance_analysis=signals["compliance"] or q_type == "COMPLIANCE",
            confidence=0.95
        )

    # -------------------------------------------------------------------------
    # 75.6, 75.7, 75.8 SUB-QUESTION DECOMPOSITION & DAG PLANNING
    # -------------------------------------------------------------------------

    def decompose_query(self, query_or_intent: Any, maybe_intent: Optional[QueryIntent] = None) -> List[SubQuestion]:
        """
        Decomposes complex queries into atomic, dependency-aware SubQuestions (75.6, 75.7).
        Follows pattern-driven planning rules (75.8).
        Can be called as decompose_query(intent) or decompose_query(query, intent).
        """
        if isinstance(query_or_intent, QueryIntent):
            intent = query_or_intent
        elif maybe_intent is not None:
            intent = maybe_intent
        else:
            intent = self.classify_intent(str(query_or_intent))

        query = intent.original_query
        q_type = intent.query_type
        sub_questions: List[SubQuestion] = []

        # Case 1: Simple factual or direct lookup -> Single SubQuestion
        if intent.complexity == "SIMPLE":
            sub_questions.append(SubQuestion(
                id="sq_1",
                text=query,
                purpose="Direct evidence retrieval for factual inquiry",
                authority_scope=intent.authorities[0] if intent.authorities else None,
                expected_evidence_type="CHUNK",
                rewritten_query=self.rewrite_query(query, "FACTUAL")
            ))
            return sub_questions

        # Case 2: Cross-Regulator Comparison / Conflict (e.g. SEBI vs RBI)
        if intent.requires_cross_regulator_analysis or q_type in ("CROSS_REGULATOR", "OVERLAP", "CONFLICT"):
            auth_a = intent.authorities[0] if len(intent.authorities) > 0 else "SEBI"
            auth_b = intent.authorities[1] if len(intent.authorities) > 1 else ("RBI" if auth_a != "RBI" else "IRDAI")

            sq_1 = SubQuestion(
                id="sq_1",
                text=f"Retrieve active requirements and obligations for {auth_a} regarding {intent.topics[0] if intent.topics else 'relevant activity'}.",
                purpose=f"Gather regulatory baseline for {auth_a}",
                authority_scope=auth_a,
                expected_evidence_type="REQUIREMENT",
                rewritten_query=f"{auth_a} {intent.topics[0] if intent.topics else ''} requirements obligations"
            )
            sq_2 = SubQuestion(
                id="sq_2",
                text=f"Retrieve active requirements and obligations for {auth_b} regarding {intent.topics[0] if intent.topics else 'relevant activity'}.",
                purpose=f"Gather regulatory baseline for {auth_b}",
                authority_scope=auth_b,
                expected_evidence_type="REQUIREMENT",
                rewritten_query=f"{auth_b} {intent.topics[0] if intent.topics else ''} requirements obligations"
            )
            sq_3 = SubQuestion(
                id="sq_3",
                text=f"Identify verified regulatory overlaps between {auth_a} and {auth_b}.",
                parent_id=None,
                depends_on=["sq_1", "sq_2"],
                purpose="Find shared operational activity across both authorities",
                expected_evidence_type="OVERLAP",
                rewritten_query=f"overlap {auth_a} {auth_b}"
            )
            sq_4 = SubQuestion(
                id="sq_4",
                text=f"Identify potential inconsistencies or parameter conflicts between {auth_a} and {auth_b}.",
                depends_on=["sq_3"],
                purpose="Evaluate potential conflict between provisions",
                expected_evidence_type="CONFLICT",
                rewritten_query=f"conflict {auth_a} {auth_b}"
            )
            return [sq_1, sq_2, sq_3, sq_4]

        # Case 3: Change Analysis with Compliance Impact (What changed and affected checklist?)
        if intent.requires_change_analysis and intent.requires_compliance_analysis:
            auth = intent.authorities[0] if intent.authorities else None
            sq_1 = SubQuestion(
                id="sq_1",
                text="Identify the latest regulatory document and version.",
                purpose="Find current regulatory baseline",
                authority_scope=auth,
                expected_evidence_type="DOCUMENT",
                rewritten_query=f"{auth or ''} latest regulation circular"
            )
            sq_2 = SubQuestion(
                id="sq_2",
                text="Identify previous predecessor version and extract section-level changes.",
                depends_on=["sq_1"],
                purpose="Determine exact delta between versions",
                authority_scope=auth,
                expected_evidence_type="CHANGE",
                rewritten_query=f"{auth or ''} version diff change"
            )
            sq_3 = SubQuestion(
                id="sq_3",
                text="Extract modified regulatory requirements and resulting obligations.",
                depends_on=["sq_2"],
                purpose="Identify substantive legal duties changed",
                authority_scope=auth,
                expected_evidence_type="OBLIGATION",
                rewritten_query=f"{auth or ''} modified requirements obligations"
            )
            sq_4 = SubQuestion(
                id="sq_4",
                text="Identify affected compliance checklist controls and effective dates.",
                depends_on=["sq_3"],
                purpose="Map operational impact onto compliance controls",
                authority_scope=auth,
                expected_evidence_type="CHECKLIST",
                rewritten_query=f"{auth or ''} compliance checklist controls"
            )
            return [sq_1, sq_2, sq_3, sq_4]

        # Case 4: Standard Change Analysis (What changed?)
        if intent.requires_change_analysis:
            auth = intent.authorities[0] if intent.authorities else None
            sq_1 = SubQuestion(
                id="sq_1",
                text="Identify relevant regulation and current version.",
                purpose="Find current document",
                authority_scope=auth,
                expected_evidence_type="DOCUMENT",
                rewritten_query=self.rewrite_query(query, "DOCUMENT_LOOKUP")
            )
            sq_2 = SubQuestion(
                id="sq_2",
                text="Identify predecessor version and extract section changes.",
                depends_on=["sq_1"],
                purpose="Compute version diff and amendments",
                authority_scope=auth,
                expected_evidence_type="CHANGE",
                rewritten_query=f"{auth or ''} diff what changed"
            )
            sq_3 = SubQuestion(
                id="sq_3",
                text="Retrieve effective dates and timeline milestones.",
                depends_on=["sq_2"],
                purpose="Verify when changes take effect",
                authority_scope=auth,
                expected_evidence_type="CHUNK",
                rewritten_query=f"{auth or ''} effective date timeline"
            )
            return [sq_1, sq_2, sq_3]

        # Case 5: Temporal inquiry (As of date X / Timeline)
        if intent.requires_temporal_reasoning:
            auth = intent.authorities[0] if intent.authorities else None
            sq_1 = SubQuestion(
                id="sq_1",
                text=f"Retrieve effective regulatory status and active circulars as of specified date.",
                purpose="Resolve historical temporal state",
                authority_scope=auth,
                expected_evidence_type="CHUNK",
                rewritten_query=self.rewrite_query(query, "TEMPORAL")
            )
            sq_2 = SubQuestion(
                id="sq_2",
                text="Verify subsequent amendments or superseding circulars.",
                depends_on=["sq_1"],
                purpose="Verify continuity of provisions",
                authority_scope=auth,
                expected_evidence_type="CHUNK",
                rewritten_query=f"{auth or ''} supersedes amends history"
            )
            return [sq_1, sq_2]

        # Fallback multi-step
        sq_1 = SubQuestion(
            id="sq_1",
            text=f"Retrieve core regulatory requirements for {query}",
            purpose="Core requirement lookup",
            expected_evidence_type="CHUNK",
            rewritten_query=self.rewrite_query(query, "REQUIREMENT_LOOKUP")
        )
        sq_2 = SubQuestion(
            id="sq_2",
            text=f"Retrieve context, conditions, and compliance scope",
            depends_on=["sq_1"],
            purpose="Secondary context resolution",
            expected_evidence_type="CHUNK",
            rewritten_query=f"{query} conditions scope exceptions"
        )
        return [sq_1, sq_2]

    # -------------------------------------------------------------------------
    # 75.9 QUERY REWRITING
    # -------------------------------------------------------------------------

    def rewrite_query(
        self,
        query: str,
        context_type: str = "FACTUAL",
        target_authority: Optional[str] = None,
        query_type: Optional[str] = None
    ) -> str:
        """
        Produces clean, keyword-dense search queries optimized for BM25 and Vector Search (75.9).
        Strips conversational framing ('can you tell me', 'please explain').
        """
        c_type = query_type or context_type
        cleaned = re.sub(
            r"^(can you please |can you |could you |please tell me |what is |explain |tell me about |give me )",
            "",
            query.strip(),
            flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(r"\?+$", "", cleaned).strip()

        if target_authority and target_authority.upper() not in cleaned.upper():
            cleaned = f"{target_authority} {cleaned}"

        if c_type == "CHANGE_ANALYSIS":
            return f"{cleaned} amendment circular change"
        elif c_type == "TEMPORAL":
            return f"{cleaned} effective date coming into force"
        elif c_type in ("COMPLIANCE", "OBLIGATION", "REQUIREMENT"):
            return f"{cleaned} mandatory requirement obligation"
        elif c_type == "DEFINITION":
            return f"{cleaned} definition meaning shall mean"
        return cleaned

    # -------------------------------------------------------------------------
    # 75.7 DEPENDENCY GRAPH EXECUTION STAGING
    # -------------------------------------------------------------------------

    def build_execution_stages(self, sub_questions: List[SubQuestion]) -> List[List[str]]:
        """
        Converts the SubQuestion dependency DAG into sequential stages of parallel subquestion IDs (75.7).
        """
        resolved: set = set()
        remaining = list(sub_questions)
        stages: List[List[str]] = []

        while remaining:
            # Find all subquestions whose dependencies are already resolved
            current_stage = [
                sq.id for sq in remaining
                if all(dep in resolved for dep in sq.depends_on)
            ]
            if not current_stage:
                # Circular or broken dependency safeguard -> execute remaining in sequence
                current_stage = [remaining[0].id]

            stages.append(current_stage)
            for sid in current_stage:
                resolved.add(sid)
            remaining = [sq for sq in remaining if sq.id not in resolved]

        return stages

    # -------------------------------------------------------------------------
    # END-TO-END PLAN CREATION
    # -------------------------------------------------------------------------

    def create_plan(self, query: str) -> QueryPlan:
        """
        Creates an end-to-end QueryPlan with intent, decomposed subquestions,
        DAG stages, and planned tools.
        """
        intent = self.classify_intent(query)
        sub_questions = self.decompose_query(intent)
        stages = self.build_execution_stages(sub_questions)

        # Determine planned tools (Phase 77 integration)
        planned_tools = []
        if intent.complexity == "SIMPLE":
            planned_tools = ["search_chunks"]
        else:
            if intent.requires_change_analysis:
                planned_tools.extend(["get_document", "get_version", "get_changes"])
            if intent.requires_cross_regulator_analysis:
                planned_tools.extend(["search_requirements", "get_overlaps", "get_conflicts"])
            if intent.requires_compliance_analysis:
                planned_tools.extend(["search_obligations", "get_compliance_items"])
            if intent.requires_temporal_reasoning:
                planned_tools.extend(["get_timeline", "get_effective_state"])
            planned_tools.append("search_chunks")

        # Deduplicate planned tools preserving order
        unique_tools = list(dict.fromkeys(planned_tools))

        return QueryPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            query_id=intent.query_id,
            original_query=query,
            intent=intent,
            sub_questions=sub_questions,
            execution_order=stages,
            planned_tools=unique_tools
        )
