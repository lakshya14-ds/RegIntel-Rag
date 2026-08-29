"""
Langfuse Tracer Module for RegIntel RAG (Phase 33).

Provides structured request tracing, span hierarchy profiling, latency measurement,
and LLM generation monitoring across the entire RAG pipeline:
- Query Analysis
- Query Embedding
- Vector Search
- BM25
- Hybrid Retrieval
- Reranking
- Context Construction
- Gemini Generation
- Citation Validation

Gracefully operates in no-op mode if Langfuse is disabled or unconfigured.
"""

import time
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from app.config import settings

logger = logging.getLogger("regintel.observability.langfuse")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class DummySpan:
    """No-op span object providing mock Langfuse span/generation methods."""
    def __init__(self, span_id: str = "noop-span-id"):
        self.id = span_id
        self.name = "noop"

    def end(self, *args, **kwargs):
        pass

    def update(self, *args, **kwargs):
        pass

    def score(self, *args, **kwargs):
        pass


class DummyTrace:
    """No-op trace object providing mock Langfuse trace methods."""
    def __init__(self, trace_id: str = "noop-trace-id"):
        self.id = trace_id
        self.name = "noop-trace"

    def span(self, *args, **kwargs):
        return DummySpan()

    def generation(self, *args, **kwargs):
        return DummySpan()

    def update(self, *args, **kwargs):
        pass


class LangfuseTracer:
    """
    Manages Langfuse tracing client, request hierarchies, spans, and generations.
    """

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
        enabled: Optional[bool] = None
    ):
        self.public_key = public_key if public_key is not None else settings.langfuse_public_key
        self.secret_key = secret_key if secret_key is not None else settings.langfuse_secret_key
        self.host = host or settings.langfuse_host
        self.enabled = settings.langfuse_enabled if enabled is None else enabled
        self._client = None
        self._is_active = False

        if self.enabled and self.public_key and self.secret_key:
            self._initialize_client()

    def _initialize_client(self) -> None:
        """Initializes the Langfuse SDK client."""
        try:
            from langfuse import Langfuse
            self._client = Langfuse(
                public_key=self.public_key,
                secret_key=self.secret_key,
                host=self.host
            )
            self._is_active = True
            logger.info(f"Langfuse tracer initialized successfully (Host: {self.host})")
        except ImportError:
            logger.warning("Langfuse package not installed. Live tracing disabled.")
            self._is_active = False
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse client ({e}). Operating in no-op mode.")
            self._is_active = False

    @property
    def is_active(self) -> bool:
        """Returns True if Langfuse is configured and functional."""
        return self.enabled and self._is_active and self._client is not None

    @contextmanager
    def start_trace(
        self,
        name: str = "RAG Request",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ):
        """Initiates an end-to-end root trace for a RAG question/request."""
        if not self.is_active:
            yield DummyTrace()
            return

        trace = None
        try:
            trace = self._client.trace(
                name=name,
                user_id=user_id,
                session_id=session_id,
                metadata=metadata or {},
                tags=tags or ["regintel-rag", "production"]
            )
            yield trace
        except Exception as e:
            logger.warning(f"Error initiating Langfuse trace '{name}': {e}")
            yield DummyTrace()

    @contextmanager
    def start_span(
        self,
        parent: Any,
        name: str,
        input_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Records an execution span (e.g. Query Analysis, Vector Search, BM25, Reranking)."""
        if not self.is_active or isinstance(parent, DummyTrace) or parent is None:
            yield DummySpan()
            return

        start_time = time.time()
        span_obj = None
        try:
            if hasattr(parent, "span"):
                span_obj = parent.span(
                    name=name,
                    input=input_data,
                    metadata=metadata or {}
                )
            yield span_obj
        except Exception as e:
            logger.warning(f"Error in span '{name}': {e}")
            yield DummySpan()
        finally:
            if span_obj and hasattr(span_obj, "end"):
                try:
                    duration_s = round(time.time() - start_time, 4)
                    span_obj.end(output={"duration_seconds": duration_s})
                except Exception:
                    pass

    @contextmanager
    def log_generation(
        self,
        parent: Any,
        name: str = "Gemini Generation",
        model: Optional[str] = None,
        model_parameters: Optional[Dict[str, Any]] = None,
        input_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Records an LLM generation call with prompt, completion, and latency."""
        if not self.is_active or isinstance(parent, DummyTrace) or parent is None:
            yield DummySpan()
            return

        start_time = time.time()
        gen_obj = None
        try:
            if hasattr(parent, "generation"):
                gen_obj = parent.generation(
                    name=name,
                    model=model or "gemini-2.5-flash",
                    model_parameters=model_parameters or {"temperature": 0.2},
                    input=input_prompt,
                    metadata=metadata or {}
                )
            yield gen_obj
        except Exception as e:
            logger.warning(f"Error logging LLM generation '{name}': {e}")
            yield DummySpan()
        finally:
            if gen_obj and hasattr(gen_obj, "end"):
                try:
                    duration_s = round(time.time() - start_time, 4)
                    gen_obj.end(output={"duration_seconds": duration_s})
                except Exception:
                    pass

    def end_span(self, span_obj: Any, output_data: Optional[Any] = None) -> None:
        """Explicitly ends a span."""
        if span_obj and hasattr(span_obj, "end"):
            try:
                span_obj.end(output=output_data)
            except Exception:
                pass

    def end_trace(self, trace_obj: Any, output_data: Optional[Any] = None) -> None:
        """Explicitly updates or completes a trace."""
        if trace_obj and hasattr(trace_obj, "update"):
            try:
                trace_obj.update(output=output_data)
            except Exception:
                pass

    def flush(self) -> None:
        """Flushes queued events to the Langfuse backend."""
        if self.is_active and hasattr(self._client, "flush"):
            try:
                self._client.flush()
            except Exception as e:
                logger.warning(f"Error flushing Langfuse events: {e}")


# Global singleton instance & Aliases
langfuse_tracer = LangfuseTracer()
LangfuseTracker = LangfuseTracer
langfuse_tracker = langfuse_tracer
