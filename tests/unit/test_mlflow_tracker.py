"""Unit tests for MLflow experiment tracker."""

from pathlib import Path
from app.observability.mlflow_tracker import MLflowExperimentTracker


def test_mlflow_tracker_initialization(tmp_path: Path):
    tracker = MLflowExperimentTracker(
        experiment_name="test-experiment",
        tracking_uri=str(tmp_path / "test_mlruns"),
        enabled=True
    )
    assert tracker.experiment_name == "test-experiment"
    # Should safely report active or fallback
    assert isinstance(tracker.is_active, bool)


def test_mlflow_tracker_disabled():
    tracker = MLflowExperimentTracker(enabled=False)
    assert not tracker.is_active

    # Methods should safely no-op without exceptions
    with tracker.start_run(run_name="test_run") as run:
        assert run is None

    tracker.log_params({"top_k": 5, "method": "hybrid"})
    tracker.log_metrics({"mrr": 0.85, "recall_at_5": 92.0})
    tracker.log_dict({"test": "data"}, "test.json")


def test_mlflow_tracker_log_retrieval_evaluation(tmp_path: Path):
    dummy_results = tmp_path / "results.json"
    dummy_results.write_text('{"summary": "ok"}', encoding="utf-8")

    tracker = MLflowExperimentTracker(
        experiment_name="unit-test-retrieval",
        tracking_uri=str(tmp_path / "mlruns"),
        enabled=True
    )

    tracker.log_retrieval_evaluation(
        method="hybrid",
        top_k=5,
        metrics={"recall_at_5": 95.0, "mrr": 0.88},
        dataset_size=10,
        results_file=dummy_results
    )


def test_mlflow_tracker_log_generation_evaluation(tmp_path: Path):
    dummy_report = tmp_path / "gen_report.json"
    dummy_report.write_text('{"relevance": 4.8}', encoding="utf-8")

    tracker = MLflowExperimentTracker(
        experiment_name="unit-test-generation",
        tracking_uri=str(tmp_path / "mlruns"),
        enabled=True
    )

    tracker.log_generation_evaluation(
        model_name="gemini-2.5-flash",
        metrics={"average_relevance": 4.8, "citation_integrity": 100.0},
        dataset_size=10,
        results_file=dummy_report
    )
