"""
Pydantic Request Models for RegIntel FastAPI Endpoints.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    """Request payload for regulatory Q&A generation endpoint /ask."""
    question: str = Field(
        ...,
        description="The regulatory compliance or legal intelligence query.",
        min_length=3,
        max_length=1000,
        examples=["What are the latest requirements for investment advisers?"]
    )
    top_k: Optional[int] = Field(
        default=5,
        description="Maximum number of evidence chunks to retrieve and ground against.",
        gt=0,
        le=20
    )
    retrieval_mode: Optional[Literal["hybrid", "vector", "bm25", "hybrid_reranked"]] = Field(
        default="hybrid",
        description="Retrieval engine to use."
    )
    category: Optional[str] = Field(
        default=None,
        description="Optional regulatory category filter (e.g. Investment Adviser, Mutual Funds)."
    )
    source: Optional[str] = Field(
        default=None,
        description="Optional regulatory authority filter (e.g. SEBI)."
    )

    @field_validator("question")
    @classmethod
    def validate_question_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty or whitespace only.")
        return cleaned


class CompareRequest(BaseModel):
    """Request payload for explicit document comparison endpoint /compare."""
    document_a_id: str = Field(
        ...,
        description="Document ID of the predecessor / reference regulatory document.",
        min_length=1
    )
    document_b_id: str = Field(
        ...,
        description="Document ID of the current / updated regulatory document.",
        min_length=1
    )

    @field_validator("document_a_id", "document_b_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Document ID cannot be empty.")
        return cleaned


class SearchRequest(BaseModel):
    """Request payload for direct multi-method retrieval endpoint /search."""
    query: str = Field(
        ...,
        description="Search terms or query string.",
        min_length=2,
        max_length=500,
        examples=["Record keeping period for investment advisers"]
    )
    top_k: Optional[int] = Field(
        default=10,
        description="Maximum number of candidate chunks to return.",
        gt=0,
        le=50
    )
    retrieval_mode: Optional[Literal["hybrid", "vector", "bm25", "hybrid_reranked"]] = Field(
        default="hybrid",
        description="Retrieval mechanism to execute."
    )
    category: Optional[str] = Field(
        default=None,
        description="Optional category filter."
    )
    source: Optional[str] = Field(
        default=None,
        description="Optional regulatory authority filter."
    )

    @field_validator("query")
    @classmethod
    def validate_query_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Query string cannot be empty.")
        return cleaned


class ChangeIntelligenceRequest(BaseModel):
    """Request payload for Change Intelligence ('What Changed?') endpoint (Phase 59)."""
    document_id: Optional[str] = Field(
        default=None,
        description="Target document ID for automatic reliable predecessor comparison (Mode A)."
    )
    document_a_id: Optional[str] = Field(
        default=None,
        description="Prior document ID for explicit comparison (Mode B)."
    )
    document_b_id: Optional[str] = Field(
        default=None,
        description="Current document ID for explicit comparison (Mode B)."
    )
    generate_summaries: bool = Field(
        default=True,
        description="Whether to generate semantic summaries via Gemini."
    )
