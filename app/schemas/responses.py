"""
Pydantic Response Models for RegIntel FastAPI Endpoints.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check status payload."""
    status: str = Field(description="'ok', 'degraded', or 'unavailable'")
    mongodb: bool = Field(description="MongoDB Atlas connection health")
    embedding_service: bool = Field(description="Gemini API embedding service availability")
    environment: str = Field(default="production")
    version: str = Field(default="1.0.0")


class SourceCitationResponse(BaseModel):
    """Structured citation item referenced in a generated answer."""
    source_id: int
    chunk_id: str
    document_id: str
    source: str
    title: str
    section: Optional[str] = "General"
    published_date: Optional[str] = "N/A"
    effective_date: Optional[str] = "N/A"
    url: str
    score: float


class QueryIntentResponse(BaseModel):
    """Parsed query classification and extracted regulatory metadata filters."""
    query_type: str
    time_intent: str
    source: Optional[str] = None
    category: Optional[str] = None
    document_type: Optional[str] = None
    circular_number: Optional[str] = None
    is_comparison: bool = False


class AskResponse(BaseModel):
    """Full grounded RAG answer response."""
    answer: str
    sources: List[SourceCitationResponse]
    query_intent: Optional[QueryIntentResponse] = None
    sufficient_evidence: bool = True
    disclaimer: str = "Based on indexed regulatory sources. Does not constitute official legal advice."
    debug_info: Optional[Dict[str, Any]] = None


class SearchItemResponse(BaseModel):
    """Retrieved candidate chunk item."""
    rank: int
    chunk_id: str
    document_id: str
    title: Optional[str] = None
    section: Optional[str] = None
    source: str = "SEBI"
    category: Optional[str] = None
    document_type: Optional[str] = None
    published_date: Optional[str] = None
    effective_date: Optional[str] = None
    url: str
    score: float
    content_snippet: str


class SearchResponse(BaseModel):
    """Direct multi-method retrieval results."""
    query: str
    retrieval_mode: str
    total_results: int
    results: List[SearchItemResponse]


class DocumentMetadataResponse(BaseModel):
    """Cleaned regulatory document metadata without embedding vectors."""
    document_id: str
    title: Optional[str] = None
    source: str = "SEBI"
    category: Optional[str] = None
    document_type: Optional[str] = None
    circular_number: Optional[str] = None
    published_date: Optional[str] = None
    effective_date: Optional[str] = None
    status: Optional[str] = "unknown"
    url: str = ""
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    document_version: Optional[str] = "1.0"
    content_hash: Optional[str] = None
    relationship_type: Optional[str] = None
    relationship_confidence: Optional[str] = None


class TimelineNodeResponse(BaseModel):
    """Timeline entry in document version lineage."""
    document_id: str
    title: Optional[str] = None
    published_date: Optional[str] = None
    status: str = "unknown"
    relationship: str = "related"


class DocumentVersionResponse(BaseModel):
    """Regulatory version graph relationship information for a specific document."""
    document_id: str
    title: Optional[str] = None
    status: str
    document_version: str
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    predecessor: Optional[DocumentMetadataResponse] = None
    successor: Optional[DocumentMetadataResponse] = None
    predecessor_candidates: List[str] = Field(default_factory=list)
    relationship_type: Optional[str] = None
    relationship_confidence: Optional[str] = None
    timeline: List[TimelineNodeResponse] = Field(default_factory=list)


class EvidenceSourceResponse(BaseModel):
    """Source reference for evidence backing a regulatory change."""
    document_id: str
    section_id: str
    heading: str
    section_number: Optional[str] = None
    url: Optional[str] = None
    published_date: Optional[str] = None


class SectionChangeResponse(BaseModel):
    """Individual section comparison delta entry with evidence mapping and side-by-side text."""
    section_index: int = 0
    section: Optional[str] = None
    heading: str
    change_type: str  # ADDED, REMOVED, MODIFIED, UNCHANGED
    substantive_change: bool = False
    category: Optional[str] = "GENERAL"
    modification_category: Optional[str] = None
    previous_text: Optional[str] = None
    current_text: Optional[str] = None
    summary: str = ""
    old_requirement: Optional[str] = None
    new_requirement: Optional[str] = None
    compliance_impact: Optional[str] = None
    impact: Optional[str] = None
    similarity_score: Optional[float] = None
    evidence: Optional[Any] = None
    old_source: Optional[EvidenceSourceResponse] = None
    new_source: Optional[EvidenceSourceResponse] = None


class CompareResponse(BaseModel):
    """Structured report returned from direct document comparison."""
    status: str = "SUCCESS"
    message: Optional[str] = None
    document_a: DocumentMetadataResponse
    document_b: DocumentMetadataResponse
    older_document: Optional[DocumentMetadataResponse] = None
    newer_document: Optional[DocumentMetadataResponse] = None
    document_order_confidence: str = "unknown"
    version_relationship: str = "UNKNOWN"
    relationship_confidence: str = "unknown"
    summary: str = ""
    executive_summary: str = ""
    key_changes: List[str] = Field(default_factory=list)
    total_changes: int = 0
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    unchanged_count: int = 0
    summary_counts: Dict[str, int] = Field(default_factory=dict)
    statistics: Dict[str, int] = Field(default_factory=dict)
    changes: List[SectionChangeResponse] = Field(default_factory=list)
    cached: bool = False
