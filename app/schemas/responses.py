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
    source: str
    category: Optional[str] = None
    document_type: Optional[str] = None
    circular_number: Optional[str] = None
    published_date: Optional[str] = None
    effective_date: Optional[str] = None
    status: Optional[str] = "unknown"
    url: str
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    document_version: Optional[str] = "1.0"
    content_hash: Optional[str] = None
    relationship_type: Optional[str] = None
    relationship_confidence: Optional[str] = None


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


class SectionChangeResponse(BaseModel):
    """Individual section comparison delta entry."""
    section_index: int
    heading: str
    change_type: str  # ADDED, REMOVED, MODIFIED, UNCHANGED
    category: Optional[str] = "GENERAL"
    summary: str
    compliance_impact: Optional[str] = None
    similarity_score: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None


class CompareResponse(BaseModel):
    """Structured report returned from direct document comparison."""
    document_a: DocumentMetadataResponse
    document_b: DocumentMetadataResponse
    summary: str
    total_changes: int
    added_count: int
    removed_count: int
    modified_count: int
    unchanged_count: int
    changes: List[SectionChangeResponse]
