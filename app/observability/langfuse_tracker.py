"""
Langfuse Observability Module for RegIntel RAG.

Exposes unified LangfuseTracer singleton for backward compatibility.
"""

from app.observability.langfuse_tracer import (
    LangfuseTracer,
    LangfuseTracker,
    DummySpan,
    DummyTrace,
    ErrorCategory,
    langfuse_tracer,
    langfuse_tracker
)

__all__ = [
    "LangfuseTracer",
    "LangfuseTracker",
    "DummySpan",
    "DummyTrace",
    "ErrorCategory",
    "langfuse_tracer",
    "langfuse_tracker"
]
