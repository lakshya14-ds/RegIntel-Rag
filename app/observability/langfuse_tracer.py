"""
Langfuse Tracing and Observability Module for RegIntel RAG (Phase 50).

Provides end-to-end distributed tracing, span hierarchy profiling, latency measurement,
token tracking, and LLM generation monitoring across the entire RAG pipeline:
- Query Analysis
- Query Embedding
- MongoDB Vector Search
- BM25 Keyword Search
- Hybrid Merging & Fusion
- BGE Cross-Encoder Reranking
- Temporal / Version Logic
- Context Construction
- LLM Generation (Gemini & Ollama)
- Fallback Failover Routing
- Citation Validation
- Regulatory Change Detection

Gracefully operates in no-op mode if Langfuse is disabled or unconfigured.
Guarantees zero impact on core RAG execution on any observability or network error.
"""

import re
import time
import random
import logging
from enum import Enum
from typing import Optional, Dict, Any, List, Union
from contextlib import contextmanager

from app.config import settings

logger = logging.getLogger("regintel.observability.langfuse")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class ErrorCategory(str, Enum):
    """Standardized error taxonomy for RegIntel RAG traces."""
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    MONGODB_ERROR = "MONGODB_ERROR"
    EMBEDDING_ERROR = "EMBEDDING_ERROR"
    RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
    RERANKER_ERROR = "RERANKER_ERROR"
    LLM_ERROR = "LLM_ERROR"
    CITATION_ERROR = "CITATION_ERROR"
    COMPARISON_ERROR = "COMPARISON_ERROR"
    TIMEOUT = "TIMEOUT"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class DummySpan:
    """No-op span object providing mock Langfuse span/generation methods."""

    def __init__(self, span_id: str = "noop-span-id", name: str = "noop"):
        self.id = span_id
        self.name = name

    def end(self, *args, **kwargs):
        pass

    def update(self, *args, **kwargs):
        pass

    def score(self, *args, **kwargs):
        pass

    def create_event(self, *args, **kwargs):
        pass

    def start_observation(self, *args, **kwargs):
        return DummySpan()

    def span(self, *args, **kwargs):
        return DummySpan()

    def generation(self, *args, **kwargs):
        return DummySpan()


class DummyTrace:
    """No-op trace object providing mock Langfuse root trace methods."""

    def __init__(self, trace_id: str = "noop-trace-id", name: str = "noop-trace"):
        self.id = trace_id
        self.name = name

    def span(self, *args, **kwargs):
        return DummySpan()

    def generation(self, *args, **kwargs):
        return DummySpan()

    def start_observation(self, *args, **kwargs):
        return DummySpan()

    def update(self, *args, **kwargs):
        pass

    def score(self, *args, **kwargs):
        pass


class LangfuseTracer:
    """
    Production-grade Langfuse Tracer managing request lifecycles, spans, and generations.
    """

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
        enabled: Optional[bool] = None,
        sample_rate: Optional[float] = None
    ):
        self.public_key = public_key if public_key is not None else settings.langfuse_public_key
        self.secret_key = secret_key if secret_key is not None else settings.langfuse_secret_key
        self.host = host or settings.langfuse_host or "https://cloud.langfuse.com"
        self.enabled = settings.langfuse_enabled if enabled is None else enabled
        
        # Validate sampling rate (0.0 to 1.0)
        raw_rate = sample_rate if sample_rate is not None else settings.langfuse_sample_rate
        if not (0.0 <= raw_rate <= 1.0):
            logger.warning(f"Invalid LANGFUSE_SAMPLE_RATE ({raw_rate}). Clamping to 1.0.")
            self.sample_rate = 1.0
        else:
            self.sample_rate = raw_rate

        self._client = None
        self._is_active = False

        if self.enabled and self.public_key and self.secret_key:
            self._initialize_client()

    def _initialize_client(self) -> None:
        """Initializes the Langfuse client."""
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
            logger.warning("Langfuse package not installed. Operating in no-op mode.")
            self._is_active = False
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse client ({e}). Operating in no-op mode.")
            self._is_active = False

    @property
    def is_active(self) -> bool:
        """Returns True if Langfuse is configured, enabled, and operational."""
        return bool(self.enabled and self._is_active and self._client is not None)

    def should_sample(self) -> bool:
        """Determines whether a trace should be sampled based on configured rate."""
        if not self.is_active:
            return False
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0.0:
            return False
        return random.random() < self.sample_rate

    def _sanitize_data(self, data: Any) -> Any:
        """Redacts sensitive credentials (keys, tokens, passwords) and truncates long strings."""
        if data is None:
            return None

        max_len = settings.langfuse_max_content_length or 5000

        if isinstance(data, str):
            # Mask potential API keys or connection credentials
            masked = re.sub(r"(AIzaSy[A-Za-z0-9_-]{33}|AQ\.[A-Za-z0-9_-]{40,}|sk-[A-Za-z0-9]{32,})", "[REDACTED_API_KEY]", data)
            masked = re.sub(r"mongodb(?:\+srv)?://([^:]+):([^@]+)@", "mongodb://[USER]:[REDACTED]@", masked)
            if len(masked) > max_len:
                return masked[:max_len] + f"... [TRUNCATED at {max_len} chars]"
            return masked

        elif isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                k_lower = str(k).lower()
                if any(sec in k_lower for sec in ("key", "secret", "password", "token", "auth")):
                    clean[k] = "[REDACTED]"
                else:
                    clean[k] = self._sanitize_data(v)
            return clean

        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data[:50]]

        return data

    @contextmanager
    def start_trace(
        self,
        name: str = "regintel.ask",
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ):
        """Initiates a top-level root trace for an end-to-end user request."""
        if not self.should_sample():
            yield DummyTrace()
            return

        trace_meta = {
            "environment": getattr(settings, "environment", "production"),
            "app_version": getattr(settings, "regintel_version", "0.1.0"),
            "request_id": request_id or "req-default"
        }
        if metadata:
            trace_meta.update(self._sanitize_data(metadata))

        trace_tags = tags or ["regintel-rag", trace_meta["environment"]]

        trace_obj = None
        try:
            if hasattr(self._client, "start_observation"):
                # Langfuse v4 API
                trace_obj = self._client.start_observation(
                    name=name,
                    as_type="chain",
                    metadata=trace_meta
                )
            elif hasattr(self._client, "trace"):
                # Langfuse v2/v3 fallback
                trace_obj = self._client.trace(
                    name=name,
                    user_id=user_id,
                    session_id=session_id,
                    metadata=trace_meta,
                    tags=trace_tags
                )
            else:
                trace_obj = DummyTrace()

            yield trace_obj

        except Exception as e:
            logger.warning(f"Error starting Langfuse trace '{name}': {e}")
            yield DummyTrace()
        finally:
            if trace_obj and hasattr(trace_obj, "end"):
                try:
                    trace_obj.end()
                except Exception:
                    pass

    @contextmanager
    def start_span(
        self,
        parent: Any,
        name: str,
        span_type: str = "span",
        input_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Records an execution span (query_analysis, vector_search, bm25, reranker, etc.)."""
        if not self.is_active or isinstance(parent, (DummyTrace, DummySpan)) or parent is None:
            yield DummySpan(name=name)
            return

        clean_input = None
        if settings.langfuse_capture_retrieved_content or settings.langfuse_capture_prompts:
            clean_input = self._sanitize_data(input_data)
        elif input_data is not None and not isinstance(input_data, (dict, list)):
            clean_input = self._sanitize_data(input_data)

        clean_meta = self._sanitize_data(metadata) if metadata else {}

        start_time = time.perf_counter()
        span_obj = None

        try:
            if hasattr(parent, "start_observation"):
                span_obj = parent.start_observation(
                    name=name,
                    as_type=span_type if span_type in ("span", "retriever", "embedding", "tool", "chain") else "span",
                    input=clean_input,
                    metadata=clean_meta
                )
            elif hasattr(parent, "span"):
                span_obj = parent.span(
                    name=name,
                    input=clean_input,
                    metadata=clean_meta
                )
            else:
                span_obj = DummySpan(name=name)

            yield span_obj

        except Exception as e:
            logger.warning(f"Error in span '{name}': {e}")
            yield DummySpan(name=name)
        finally:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            if span_obj and hasattr(span_obj, "end"):
                try:
                    span_obj.end(output={"latency_ms": latency_ms})
                except Exception:
                    pass

    @contextmanager
    def record_generation(
        self,
        parent: Any,
        name: str = "llm_generation",
        model: Optional[str] = None,
        model_parameters: Optional[Dict[str, Any]] = None,
        input_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Records an LLM generation event with model metadata, tokens, and latency."""
        if not self.is_active or isinstance(parent, (DummyTrace, DummySpan)) or parent is None:
            yield DummySpan(name=name)
            return

        clean_prompt = None
        if settings.langfuse_capture_prompts and input_prompt:
            clean_prompt = self._sanitize_data(input_prompt)

        clean_meta = self._sanitize_data(metadata) if metadata else {}
        clean_model = model or "unknown-model"

        start_time = time.perf_counter()
        gen_obj = None

        try:
            if hasattr(parent, "start_observation"):
                gen_obj = parent.start_observation(
                    name=name,
                    as_type="generation",
                    model=clean_model,
                    model_parameters=model_parameters or {},
                    input=clean_prompt,
                    metadata=clean_meta
                )
            elif hasattr(parent, "generation"):
                gen_obj = parent.generation(
                    name=name,
                    model=clean_model,
                    model_parameters=model_parameters or {},
                    input=clean_prompt,
                    metadata=clean_meta
                )
            else:
                gen_obj = DummySpan(name=name)

            yield gen_obj

        except Exception as e:
            logger.warning(f"Error in LLM generation span '{name}': {e}")
            yield DummySpan(name=name)
        finally:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            if gen_obj and hasattr(gen_obj, "end"):
                try:
                    gen_obj.end(output={"latency_ms": latency_ms})
                except Exception:
                    pass

    def record_error(
        self,
        span_or_trace: Any,
        error: Exception,
        category: Union[ErrorCategory, str] = ErrorCategory.UNKNOWN_ERROR
    ) -> None:
        """Annotates a span or trace with structured error classification."""
        if not span_or_trace or isinstance(span_or_trace, (DummySpan, DummyTrace)):
            return

        cat_str = category.value if isinstance(category, ErrorCategory) else str(category)
        err_msg = str(error)

        try:
            if hasattr(span_or_trace, "update"):
                span_or_trace.update(
                    level="ERROR",
                    status_message=f"[{cat_str}] {err_msg}",
                    metadata={"error_category": cat_str, "error_type": type(error).__name__}
                )
        except Exception as e:
            logger.warning(f"Failed to record error on span: {e}")

    def update_span(
        self,
        span_obj: Any,
        output_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        level: Optional[str] = None
    ) -> None:
        """Updates span with final results and metadata."""
        if not span_obj or isinstance(span_obj, (DummySpan, DummyTrace)):
            return
        try:
            if hasattr(span_obj, "update"):
                clean_output = self._sanitize_data(output_data) if output_data is not None else None
                clean_meta = self._sanitize_data(metadata) if metadata else None
                kwargs = {}
                if clean_output is not None:
                    kwargs["output"] = clean_output
                if clean_meta is not None:
                    kwargs["metadata"] = clean_meta
                if level:
                    kwargs["level"] = level
                span_obj.update(**kwargs)
        except Exception as e:
            logger.warning(f"Failed to update span: {e}")

    def update_trace(
        self,
        trace_obj: Any,
        output_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        level: Optional[str] = None
    ) -> None:
        """Updates the root trace with final output, summary metrics, and status."""
        if not trace_obj or isinstance(trace_obj, (DummySpan, DummyTrace)):
            return
        try:
            if hasattr(trace_obj, "update"):
                clean_output = self._sanitize_data(output_data) if output_data is not None else None
                clean_meta = self._sanitize_data(metadata) if metadata else None
                kwargs = {}
                if clean_output is not None:
                    kwargs["output"] = clean_output
                if clean_meta is not None:
                    kwargs["metadata"] = clean_meta
                if level:
                    kwargs["level"] = level
                trace_obj.update(**kwargs)
        except Exception as e:
            logger.warning(f"Failed to update trace: {e}")

    def flush(self) -> None:
        """Flushes buffered observations to Langfuse backend."""
        if self.is_active and hasattr(self._client, "flush"):
            try:
                self._client.flush()
            except Exception as e:
                logger.warning(f"Error flushing Langfuse events: {e}")

    def shutdown(self) -> None:
        """Cleanly shuts down the Langfuse client and flushes queues on application exit."""
        if self.is_active and hasattr(self._client, "shutdown"):
            try:
                self._client.shutdown()
                self._is_active = False
            except Exception as e:
                logger.warning(f"Error shutting down Langfuse client: {e}")


# Global singleton instance & Aliases for full backward compatibility
langfuse_tracer = LangfuseTracer()
LangfuseTracker = LangfuseTracer
langfuse_tracker = langfuse_tracer
