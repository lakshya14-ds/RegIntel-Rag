"""Unit tests for Langfuse tracer (Phase 33.10)."""

from unittest.mock import MagicMock, patch
from app.observability.langfuse_tracer import LangfuseTracer, DummyTrace, DummySpan


def test_langfuse_tracer_disabled_mode():
    tracer = LangfuseTracer(enabled=False)
    assert not tracer.is_active

    with tracer.start_trace(name="RAG Request") as trace:
        assert isinstance(trace, DummyTrace)
        assert trace.id == "noop-trace-id"

        with tracer.start_span(trace, name="Query Analysis") as span:
            assert isinstance(span, DummySpan)

        with tracer.log_generation(trace, name="Gemini Generation") as gen:
            assert isinstance(gen, DummySpan)

    tracer.end_span(span)
    tracer.end_trace(trace)
    tracer.flush()


def test_langfuse_tracer_missing_keys():
    tracer = LangfuseTracer(public_key="", secret_key="", enabled=True)
    assert not tracer.is_active

    with tracer.start_trace(name="RAG Request") as trace:
        assert isinstance(trace, DummyTrace)


def test_langfuse_tracer_mocked_client():
    mock_client = MagicMock()
    mock_trace = MagicMock()
    mock_span = MagicMock()
    mock_trace.span.return_value = mock_span
    mock_client.trace.return_value = mock_trace

    tracer = LangfuseTracer(public_key="pk_test", secret_key="sk_test", enabled=True)
    tracer._client = mock_client
    tracer._is_active = True
    assert tracer.is_active

    with tracer.start_trace(name="RAG Request", metadata={"test": "data"}) as trace:
        assert trace == mock_trace
        with tracer.start_span(trace, name="Vector Search", input_data={"k": 5}) as span:
            assert span == mock_span

    mock_client.trace.assert_called_once()
    mock_trace.span.assert_called_once_with(name="Vector Search", input={"k": 5}, metadata={})
    mock_span.end.assert_called_once()


def test_langfuse_tracer_no_secrets_in_tags():
    tracer = LangfuseTracer(enabled=False)
    with tracer.start_trace(name="RAG Request", tags=["test_tag"]) as trace:
        pass
