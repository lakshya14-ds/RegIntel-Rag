"""
Data Models for LLM Providers and Generation Responses (Phases 48 & 49).
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """
    Standardized response format returned by all LLM generation providers (Gemini, Ollama).
    """
    text: str = Field(..., description="Generated text content")
    provider: str = Field(..., description="Provider name ('gemini', 'ollama')")
    model: str = Field(..., description="Model identifier used for generation")
    input_tokens: Optional[int] = Field(default=None, description="Number of prompt/input tokens if reported")
    output_tokens: Optional[int] = Field(default=None, description="Number of generated/output tokens if reported")
    latency_ms: float = Field(default=0.0, description="Generation latency in milliseconds")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific diagnostic metadata")
    fallback_used: bool = Field(default=False, description="Whether fallback mechanism was triggered")
    primary_provider: Optional[str] = Field(default=None, description="Name of the initial provider attempted")
    fallback_provider: Optional[str] = Field(default=None, description="Name of the fallback provider used")
