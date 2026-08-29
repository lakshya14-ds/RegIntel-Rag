"""
Langfuse Observability Module for RegIntel RAG.

Provides execution tracing, span hierarchy instrumentation, and LLM generation
monitoring across query intent classification, retrieval fusion, reranking,
evidence synthesis, and citation verification.
Operates in graceful no-op mode if Langfuse credentials are not configured.
"""

import time
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

from app.config import settings

logger = logging.getLogger("regintel.observability.langfuse")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class DummyTrace:
    """No-op trace object mimicking Langfuse Trace interface."""
    def __init__(self, trace_id: str = "noop-trace-id"):
        self.id = trace_id

    def span(self, *args, **kwargs):
        return DummySpan()

    def generation(self, *args, **kwargs):
        return DummySpan()

    def update(self, *args, **kwargs):
        pass


class DummySpan:
    """No-op span object mimicking Langfuse Span/Generation interface."""
    def __init__(self, span_id: str = "noop-span-id"):
        self.id = span_id

    def end(self, *args, **kwargs):
        pass

    def update(self, *args, **kwargs):
        pass

    def score(self, *args, **kwargs):
        pass


class LangfuseTracker:
    """
    Manages Langfuse tracing client, active spans, and generation monitoring.
    """

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
        enabled: Optional[bool] = None
    ):
        self.public_key = public_key or settings.langfuse_public_key
        self.secret_key = secret_key or settings.langfuse_secret_key
        self.host = host or settings.langfuse_host
        self.enabled = settings.langfuse_enabled if enabled is None else enabled
        self._client = None
        self._is_active = False

        if self.enabled and self.public_key and self.secret_key:
            self._initialize_langfuse()

    def _initialize_langfuse(self) -> None:
        """Initializes the Langfuse SDK client."""
        try:
            from langfuse import Langfuse
            self._client = Langfuse(
                public_key=self.public_key,
                secret_key=self.secret_key,
                host=self.host
            )
            self._is_active = True
            logger.info(f"Langfuse observability initialized (Host: {self.host})")
        except ImportError:
            logger.warning("Langfuse package not installed. Live observability disabled.")
            self._is_active = False
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse client ({e}). Running in no-op mode.")
            self._is_active = False

    @property
    def is_active(self) -> bool:
        """Returns True if Langfuse is configured and actively recording."""
        return self.enabled and self._is_active and self._client is not None

    @contextmanager
    def start_trace(
        self,
        name: str = "RAG Query Execution",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[list] = None
    ):
        """Context manager initiating a root trace for an end-to-end request."""
        if not self.is_active:
            yield DummyTrace()
            return

        try:
            trace = self._client.trace(
                name=name,
                user_id=user_id,
                session_id=session_id,
                metadata=metadata or {},
                tags=tags or ["regintel-rag"]
            )
            yield trace
        except Exception as e:
            logger.warning(f"Error starting Langfuse trace '{name}': {e}")
            yield DummyTrace()

    @contextmanager
    def start_span(
        self,
        parent: Any,
        name: str,
        input_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Context manager recording an individual processing step/span."""
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
            logger.warning(f"Error during span '{name}': {e}")
            yield DummySpan()
        finally:
            if span_obj and hasattr(span_obj, "end"):
                try:
                    span_obj.end(output={"duration_s": round(time.time() - start_time, 4)})
                except Exception:
                    pass

    @contextmanager
    def record_generation(
        self,
        parent: Any,
        name: str = "LLM Generation",
        model: Optional[str] = None,
        model_parameters: Optional[Dict[str, Any]] = None,
        input_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Context manager tracking LLM prompt input and response completion."""
        if not self.is_active or isinstance(parent, DummyTrace) or parent is None:
            yield DummySpan()
            return

        gen_obj = None
        try:
            if hasattr(parent, "generation"):
                gen_obj = parent.generation(
                    name=name,
                    model=model or "gemini-2.5-flash",
                    model_parameters=model_parameters or {},
                    input=input_prompt,
                    metadata=metadata or {}
                )
            yield gen_obj
        except Exception as e:
            logger.warning(f"Error recording LLM generation span '{name}': {e}")
            yield DummySpan()

    def flush(self) -> None:
        """Forces pending events to flush to Langfuse server."""
        if self.is_active and hasattr(self._client, "flush"):
            try:
                self._client.flush()
            except Exception as e:
                logger.warning(f"Error flushing Langfuse events: {e}")


# Global singleton instance
langfuse_tracker = LangfuseTracker()
