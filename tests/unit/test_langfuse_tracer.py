"""
Comprehensive Unit Tests for Langfuse Tracer & Observability (Phase 50).
"""

import pytest
from unittest.mock import MagicMock, patch

from app.observability.langfuse_tracer import (
    LangfuseTracer,
    DummyTrace,
    DummySpan,
    ErrorCategory
)
from app.config import settings


# 1. Tracing Disabled
def test_langfuse_tracing_disabled():
    tracer = LangfuseTracer(enabled=False)
    assert tracer.is_active is False

    with tracer.start_trace(name="regintel.ask") as trace:
        assert isinstance(trace, DummyTrace)
        with tracer.start_span(trace, name="query_analysis") as span:
            assert isinstance(span, DummySpan)


# 2. Tracing Enabled with Mock Client
def test_langfuse_tracing_enabled():
    mock_client = MagicMock()
    mock_span = MagicMock()
    mock_client.start_observation.return_value = mock_span

    tracer = LangfuseTracer(public_key="pk_test", secret_key="sk_test", enabled=True)
    tracer._client = mock_client
    tracer._is_active = True
    assert tracer.is_active is True

    with tracer.start_trace(name="regintel.ask", request_id="req-123") as trace:
        assert trace == mock_span
    mock_client.start_observation.assert_called()


# 3. Trace Creation with Request ID and Environment Metadata
def test_trace_creation_metadata_and_request_id():
    mock_client = MagicMock()
    mock_trace = MagicMock()
    mock_client.start_observation.return_value = mock_trace

    tracer = LangfuseTracer(public_key="pk_test", secret_key="sk_test", enabled=True)
    tracer._client = mock_client
    tracer._is_active = True

    with tracer.start_trace(name="regintel.ask", request_id="req-abc-999", metadata={"mode": "hybrid"}) as trace:
        pass

    mock_client.start_observation.assert_called_once()
    call_kwargs = mock_client.start_observation.call_args[1]
    assert call_kwargs["name"] == "regintel.ask"
    assert call_kwargs["metadata"]["request_id"] == "req-abc-999"
    assert call_kwargs["metadata"]["mode"] == "hybrid"


# 4. Span Creation & Timing
def test_span_creation_and_lifecycle():
    mock_trace = MagicMock()
    mock_span = MagicMock()
    mock_trace.start_observation.return_value = mock_span

    tracer = LangfuseTracer(public_key="pk_test", secret_key="sk_test", enabled=True)
    tracer._client = MagicMock()
    tracer._is_active = True

    with tracer.start_span(mock_trace, name="vector_search", span_type="retriever", metadata={"k": 20}) as span:
        assert span == mock_span

    mock_trace.start_observation.assert_called_once_with(
        name="vector_search",
        as_type="retriever",
        input=None,
        metadata={"k": 20}
    )
    mock_span.end.assert_called_once()


# 5. Generation Event Tracking
def test_generation_event_recording():
    mock_trace = MagicMock()
    mock_gen = MagicMock()
    mock_trace.start_observation.return_value = mock_gen

    tracer = LangfuseTracer(public_key="pk_test", secret_key="sk_test", enabled=True)
    tracer._client = MagicMock()
    tracer._is_active = True

    with tracer.record_generation(
        mock_trace,
        name="llm_generation",
        model="gemini-1.5-flash",
        model_parameters={"temperature": 0.0},
        input_prompt="What are SEBI rules?",
        metadata={"provider": "gemini"}
    ) as gen:
        assert gen == mock_gen

    mock_trace.start_observation.assert_called_once()
    call_kwargs = mock_trace.start_observation.call_args[1]
    assert call_kwargs["name"] == "llm_generation"
    assert call_kwargs["as_type"] == "generation"
    assert call_kwargs["model"] == "gemini-1.5-flash"
    mock_gen.end.assert_called_once()


# 6. Metadata Redaction of Secrets
def test_metadata_redaction_secrets():
    tracer = LangfuseTracer(enabled=False)
    dirty_dict = {
        "gemini_api_key": "AIzaSyDummySecret1234567890123456789",
        "mongodb_uri": "mongodb+srv://user:secretpassword123@cluster.mongodb.net/",
        "query": "SEBI investment advice",
        "nested": {
            "auth_token": "sk-secret-token-12345"
        }
    }

    clean = tracer._sanitize_data(dirty_dict)
    assert clean["gemini_api_key"] == "[REDACTED]"
    assert clean["nested"]["auth_token"] == "[REDACTED]"
    assert clean["query"] == "SEBI investment advice"


# 7. Error Recording with Standardized Taxonomy
def test_error_recording():
    mock_span = MagicMock()
    tracer = LangfuseTracer(public_key="pk_test", secret_key="sk_test", enabled=True)
    tracer._client = MagicMock()
    tracer._is_active = True

    err = ValueError("MongoDB connection timeout")
    tracer.record_error(mock_span, err, category=ErrorCategory.MONGODB_ERROR)

    mock_span.update.assert_called_once()
    kwargs = mock_span.update.call_args[1]
    assert kwargs["level"] == "ERROR"
    assert "MONGODB_ERROR" in kwargs["status_message"]
    assert kwargs["metadata"]["error_category"] == "MONGODB_ERROR"


# 8. Disabled Mode Guarantees Zero Client Calls
def test_disabled_mode_zero_client_calls():
    mock_client = MagicMock()
    tracer = LangfuseTracer(enabled=False)
    tracer._client = mock_client

    with tracer.start_trace(name="regintel.ask") as trace:
        with tracer.start_span(trace, name="vector_search") as span:
            tracer.record_error(span, RuntimeError("test error"), ErrorCategory.RETRIEVAL_ERROR)

    mock_client.start_observation.assert_not_called()
    mock_client.trace.assert_not_called()


# 9. Fail-Safe: Langfuse Exceptions Do Not Break RAG Execution
def test_langfuse_failure_does_not_break_app():
    mock_client = MagicMock()
    mock_client.start_observation.side_effect = ConnectionError("Langfuse server down")

    tracer = LangfuseTracer(public_key="pk_test", secret_key="sk_test", enabled=True)
    tracer._client = mock_client
    tracer._is_active = True

    # Starting a trace should not throw even if Langfuse client fails
    with tracer.start_trace(name="regintel.ask") as trace:
        assert isinstance(trace, DummyTrace)
        with tracer.start_span(trace, name="query_analysis") as span:
            assert isinstance(span, DummySpan)


# 10. Prompt Capture Configuration
def test_prompt_capture_disabled_by_default():
    tracer = LangfuseTracer(public_key="pk_test", secret_key="sk_test", enabled=True)
    mock_trace = MagicMock()
    tracer._client = MagicMock()
    tracer._is_active = True

    with patch.object(settings, "langfuse_capture_prompts", False):
        with tracer.record_generation(mock_trace, input_prompt="Super secret regulatory prompt") as gen:
            pass

    call_kwargs = mock_trace.start_observation.call_args[1]
    assert call_kwargs["input"] is None


# 11. Content Truncation at Maximum Bound
def test_content_truncation():
    tracer = LangfuseTracer(enabled=False)
    long_text = "A" * 10000

    with patch.object(settings, "langfuse_max_content_length", 200):
        sanitized = tracer._sanitize_data(long_text)
        assert len(sanitized) < 300
        assert "TRUNCATED at 200 chars" in sanitized


# 12. Sampling Rate Bounds and Clamping
def test_sampling_rate_validation():
    # Valid rate
    t1 = LangfuseTracer(sample_rate=0.5, enabled=False)
    assert t1.sample_rate == 0.5

    # Invalid rate clamped to 1.0
    t2 = LangfuseTracer(sample_rate=2.5, enabled=False)
    assert t2.sample_rate == 1.0

    t3 = LangfuseTracer(sample_rate=-0.5, enabled=False)
    assert t3.sample_rate == 1.0


# 13. Fallback Tracing Telemetry
def test_fallback_tracing_fields():
    mock_trace = MagicMock()
    tracer = LangfuseTracer(public_key="pk_test", secret_key="sk_test", enabled=True)
    tracer._client = MagicMock()
    tracer._is_active = True

    tracer.update_trace(
        mock_trace,
        metadata={
            "fallback_used": True,
            "primary_provider": "gemini",
            "fallback_provider": "ollama"
        }
    )

    mock_trace.update.assert_called_once()
    meta = mock_trace.update.call_args[1]["metadata"]
    assert meta["fallback_used"] is True
    assert meta["fallback_provider"] == "ollama"


# 14. Flush and Shutdown Lifecycles
def test_flush_and_shutdown():
    mock_client = MagicMock()
    tracer = LangfuseTracer(public_key="pk_test", secret_key="sk_test", enabled=True)
    tracer._client = mock_client
    tracer._is_active = True

    tracer.flush()
    mock_client.flush.assert_called_once()

    tracer.shutdown()
    mock_client.shutdown.assert_called_once()
    assert tracer._is_active is False
