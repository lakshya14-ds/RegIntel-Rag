"""
Domain Data Models for Stage 5: Agentic / Multi-Hop RAG (Phases 75–78).

Defines:
- Phase 75: QueryIntent, QueryType, QueryComplexity, SubQuestion, QueryPlan
- Phase 76: RetrievalHop, RetrievalType, EvidenceSufficiency, HopBudget
- Phase 77: RetrievalStrategy, ToolName, ToolCallRecord, AgentState
- Phase 78: EvidenceNode, EvidenceEdge, EvidenceNodeType, EvidenceEdgeType, Claim, ClaimType, VerificationStatus
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# =============================================================================
# PHASE 75: QUERY INTENT & DECOMPOSITION MODELS
# =============================================================================

QueryType = Literal[
    "FACTUAL",
    "DEFINITION",
    "DOCUMENT_LOOKUP",
    "REQUIREMENT_LOOKUP",
    "OBLIGATION_LOOKUP",
    "COMPLIANCE",
    "CHANGE_ANALYSIS",
    "VERSION_COMPARISON",
    "TEMPORAL",
    "CROSS_REGULATOR",
    "OVERLAP",
    "CONFLICT",
    "MULTI_DOCUMENT",
    "MULTI_HOP",
    "UNKNOWN"
]

QueryComplexity = Literal[
    "SIMPLE",
    "MODERATE",
    "COMPLEX",
    "AGENTIC"
]


class QueryIntent(BaseModel):
    """Structured classification and intent decomposition of user query (75.1)."""
    query_id: str
    original_query: str

    query_type: QueryType = "FACTUAL"
    complexity: QueryComplexity = "SIMPLE"

    authorities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    documents: List[str] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)
    effective_date: Optional[str] = None
    temporal_scope: Optional[str] = None

    entities: List[str] = Field(default_factory=list)
    activities: List[str] = Field(default_factory=list)

    # Boolean intent dimensions (75.1)
    requires_comparison: bool = False
    requires_temporal_reasoning: bool = False
    requires_cross_regulator_analysis: bool = False
    requires_relationship_traversal: bool = False
    requires_requirement_analysis: bool = False
    requires_obligation_analysis: bool = False
    requires_change_analysis: bool = False
    requires_compliance_analysis: bool = False

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def dominant_query_type(self) -> str:
        return self.query_type

    @property
    def target_authorities(self) -> List[str]:
        return self.authorities

    @property
    def requires_cross_regulator(self) -> bool:
        return self.requires_cross_regulator_analysis

    @property
    def requires_timeline(self) -> bool:
        return self.requires_temporal_reasoning

    @property
    def requires_section_diff(self) -> bool:
        return self.requires_change_analysis

    @property
    def requires_compliance_checklist(self) -> bool:
        return self.requires_compliance_analysis

    @property
    def requires_obligations(self) -> bool:
        return self.requires_obligation_analysis

    @property
    def requires_conflict_detection(self) -> bool:
        return self.query_type == "CONFLICT" or self.requires_cross_regulator_analysis

    @property
    def requires_overlap_detection(self) -> bool:
        return self.query_type == "OVERLAP" or self.requires_cross_regulator_analysis


class SubQuestion(BaseModel):
    """Atomic step in a decomposed multi-hop query plan (75.6)."""
    id: str
    text: str
    parent_id: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)
    purpose: str = ""
    target_entity: Optional[str] = None
    authority_scope: Optional[str] = None
    temporal_scope: Optional[str] = None
    expected_evidence_type: str = "CHUNK"  # CHUNK, REQUIREMENT, OBLIGATION, CHANGE, OVERLAP, CONFLICT, CHECKLIST
    status: Literal["PENDING", "EXECUTING", "RESOLVED", "FAILED", "SKIPPED"] = "PENDING"
    rewritten_query: Optional[str] = None

    @property
    def dependencies(self) -> List[str]:
        return self.depends_on


class QueryPlan(BaseModel):
    """Structured multi-hop execution plan with dependency DAG (75.7, 75.10)."""
    plan_id: str
    query_id: str
    original_query: str
    intent: QueryIntent
    sub_questions: List[SubQuestion] = Field(default_factory=list)
    execution_order: List[List[str]] = Field(default_factory=list)  # Parallel stages of subquestion IDs
    planned_tools: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def query(self) -> str:
        return self.original_query

    @property
    def execution_stages(self) -> List[List[str]]:
        return self.execution_order

    @property
    def requires_agentic_loop(self) -> bool:
        return self.intent.complexity != "SIMPLE"


# =============================================================================
# PHASE 76: ADAPTIVE MULTI-HOP RETRIEVAL MODELS
# =============================================================================

RetrievalType = Literal[
    "DOCUMENT_SEARCH",
    "CHUNK_SEARCH",
    "REQUIREMENT_SEARCH",
    "OBLIGATION_SEARCH",
    "RELATIONSHIP_SEARCH",
    "VERSION_SEARCH",
    "TIMELINE_SEARCH",
    "CHANGE_SEARCH",
    "OVERLAP_SEARCH",
    "CONFLICT_SEARCH",
    "COMPLIANCE_SEARCH",
    "SOURCE_LOOKUP"
]

EvidenceSufficiency = Literal[
    "SUFFICIENT",
    "PARTIAL",
    "INSUFFICIENT",
    "CONTRADICTORY",
    "UNKNOWN"
]


class RetrievalHop(BaseModel):
    """Single retrieval action executed as part of an adaptive multi-hop loop (76.1)."""
    hop_id: str
    query_id: str
    sub_question_id: Optional[str] = None
    hop_number: int = 1

    retrieval_type: RetrievalType = "CHUNK_SEARCH"
    query: str
    filters: Dict[str, Any] = Field(default_factory=dict)

    retrieved_items: List[Dict[str, Any]] = Field(default_factory=list)
    selected_items: List[Dict[str, Any]] = Field(default_factory=list)

    evidence_quality: float = 0.0
    completeness: float = 0.0
    sufficiency: EvidenceSufficiency = "UNKNOWN"

    status: Literal["SUCCESS", "PARTIAL", "EMPTY", "FAILED"] = "SUCCESS"
    parent_hop_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class HopBudget(BaseModel):
    """Configurable safety limits for agentic retrieval loops (76.8)."""
    max_hops: int = 5
    max_tool_calls: int = 10
    max_documents: int = 10
    max_chunks: int = 20
    max_tokens: int = 4000
    max_latency_seconds: float = 30.0


# =============================================================================
# PHASE 77: TOOL ROUTING & AGENT STATE MODELS
# =============================================================================

RetrievalStrategy = Literal[
    "DIRECT",
    "HYBRID",
    "TEMPORAL",
    "VERSION_AWARE",
    "RELATIONSHIP_AWARE",
    "REQUIREMENT_AWARE",
    "OBLIGATION_AWARE",
    "CROSS_REGULATOR",
    "CHANGE_AWARE",
    "AGENTIC_MULTI_HOP"
]

ToolName = Literal[
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
    "get_source_evidence"
]


class ToolCallRecord(BaseModel):
    """Audit record of an individual tool call executed by the agent (77.2, 77.6)."""
    call_id: str
    tool_name: str  # ToolName or arbitrary string if error
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    status: Literal["SUCCESS", "ERROR", "TIMEOUT", "EMPTY"] = "SUCCESS"
    error_message: Optional[str] = None
    latency_ms: float = 0.0
    cost_class: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AgentState(BaseModel):
    """Structured operational state of the agent during multi-hop execution (77.9)."""
    query: str
    intent: Optional[QueryIntent] = None
    plan: Optional[QueryPlan] = None
    completed_subquestions: List[str] = Field(default_factory=list)
    pending_subquestions: List[str] = Field(default_factory=list)
    evidence_items: List[Dict[str, Any]] = Field(default_factory=list)
    visited_entities: Dict[str, List[str]] = Field(default_factory=dict)  # docs, versions, reqs
    executed_queries: List[str] = Field(default_factory=list)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    final_claims: List[Dict[str, Any]] = Field(default_factory=list)
    verification_status: str = "IN_PROGRESS"
    total_latency_seconds: float = 0.0
    terminated_reason: Optional[str] = None


# =============================================================================
# PHASE 78: EVIDENCE GRAPH & CLAIM MODELS
# =============================================================================

EvidenceNodeType = Literal[
    "DOCUMENT",
    "VERSION",
    "SECTION",
    "CHUNK",
    "REQUIREMENT",
    "OBLIGATION",
    "CHANGE",
    "OVERLAP",
    "CONFLICT",
    "CHECKLIST",
    "TIMELINE_EVENT"
]

EvidenceEdgeType = Literal[
    "BELONGS_TO",
    "VERSION_OF",
    "LOCATED_IN",
    "SUPPORTS",
    "DERIVED_FROM",
    "AMENDS",
    "SUPERSEDES",
    "CHANGES",
    "IMPLEMENTS",
    "REQUIRES",
    "AFFECTS",
    "OVERLAPS",
    "POTENTIALLY_CONFLICTS"
]


class EvidenceNode(BaseModel):
    """Vertex in the multi-hop regulatory evidence graph (78.1)."""
    evidence_id: str
    type: EvidenceNodeType

    authority: Optional[str] = None
    document_id: Optional[str] = None
    document_version_id: Optional[str] = "1.0"
    section_id: Optional[str] = None
    chunk_id: Optional[str] = None
    requirement_id: Optional[str] = None
    obligation_id: Optional[str] = None

    source_url: Optional[str] = None
    page_number: Optional[int] = None
    title: Optional[str] = None
    text: str = ""

    retrieval_hop: int = 1
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvidenceEdge(BaseModel):
    """Directed relation between two evidence nodes (78.2)."""
    edge_id: str
    from_id: str
    to_id: str
    relationship_type: EvidenceEdgeType
    evidence: Optional[str] = None
    confidence: float = 1.0


ClaimType = Literal[
    "FACT",
    "DATE",
    "REQUIREMENT",
    "OBLIGATION",
    "CHANGE",
    "COMPARISON",
    "OVERLAP",
    "POTENTIAL_CONFLICT",
    "COMPLIANCE",
    "UNKNOWN"
]

VerificationStatus = Literal[
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "UNSUPPORTED",
    "CONTRADICTED",
    "UNKNOWN"
]


class Claim(BaseModel):
    """Atomic factual statement extracted for pre-synthesis verification (78.4, 78.7)."""
    claim_id: str
    text: str
    claim_type: ClaimType = "FACT"
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    verification_status: VerificationStatus = "UNKNOWN"
    verification_notes: Optional[str] = None


class AgenticRAGResponse(BaseModel):
    """End-to-end structured response produced by AgenticRAGOrchestrator."""
    query_id: str
    question: str
    answer: str
    is_agentic: bool = True
    fast_path_used: bool = False
    strategy_used: str = "HYBRID"
    plan: Optional[Dict[str, Any]] = None
    total_hops: int = 0
    total_evidence_count: int = 0
    verification_rate: float = 1.0
    verified_claims: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_graph_summary: Dict[str, Any] = Field(default_factory=dict)
    operational_steps: List[str] = Field(default_factory=list)
    execution_time_seconds: float = 0.0
