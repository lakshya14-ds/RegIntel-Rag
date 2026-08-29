"""Unit tests for Langfuse observability tracker."""

from app.observability.langfuse_tracker import LangfuseTracker, DummyTrace, DummySpan


def test_langfuse_tracker_disabled():
    tracker = LangfuseTracker(enabled=False)
    assert not tracker.is_active

    with tracker.start_trace(name="Test RAG Pipeline") as trace:
        assert isinstance(trace, DummyTrace)
        assert trace.id == "noop-trace-id"

        with tracker.start_span(trace, name="Intent Analysis") as span:
            assert isinstance(span, DummySpan)

        with tracker.record_generation(trace, name="LLM Gen") as gen:
            assert isinstance(gen, DummySpan)

    tracker.flush()


def test_langfuse_tracker_missing_keys():
    # Enabled but without keys should gracefully fall back to no-op
    tracker = LangfuseTracker(public_key="", secret_key="", enabled=True)
    assert not tracker.is_active

    with tracker.start_trace(name="Query Execution") as trace:
        assert isinstance(trace, DummyTrace)
