"""
MLflow Experiment Tracking Module for RegIntel RAG.

Handles structured logging of retrieval, generation, and comparison benchmarks,
including hyperparameter configurations, performance metrics, dataset versioning,
and evaluation artifacts.
Operates with graceful offline / no-op fallback when MLflow is disabled or unavailable.
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
from contextlib import contextmanager

from app.config import settings

logger = logging.getLogger("regintel.observability.mlflow")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def get_git_commit_hash() -> str:
    """Attempts to retrieve the current git commit hash, or 'unknown' if not in a git repo."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown_or_no_git"


class MLflowTracker:
    """
    Manages experiment tracking, hyperparameter logging, metric recording,
    and artifact persistence for retrieval and generation evaluations.
    """

    def __init__(
        self,
        experiment_name: Optional[str] = None,
        tracking_uri: Optional[str] = None,
        enabled: Optional[bool] = None
    ):
        self.experiment_name = experiment_name or settings.mlflow_experiment_name
        self.tracking_uri = tracking_uri or settings.mlflow_tracking_uri
        self.enabled = settings.mlflow_enabled if enabled is None else enabled
        self._mlflow = None
        self._is_active = False

        if self.enabled:
            self._initialize_mlflow()

    def _initialize_mlflow(self) -> None:
        """Attempts to import and configure the MLflow client with sqlite or directory tracking."""
        try:
            os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
            import mlflow
            self._mlflow = mlflow

            uri = self.tracking_uri
            if uri and not (uri.startswith("http://") or uri.startswith("https://") or uri.startswith("sqlite://")):
                p = Path(uri).resolve()
                p.mkdir(parents=True, exist_ok=True)
                db_path = (p / "mlflow.db").as_posix()
                uri = f"sqlite:///{db_path}"

            self._mlflow.set_tracking_uri(uri)
            self._mlflow.set_experiment(self.experiment_name)
            self._is_active = True
            logger.info(f"MLflow tracking initialized (URI: {uri}, Experiment: {self.experiment_name})")
        except ImportError:
            logger.warning("MLflow package not installed. Experiment tracking disabled.")
            self._is_active = False
        except Exception as e:
            logger.warning(f"Failed to initialize MLflow ({e}). Falling back to local offline mode.")
            self._is_active = False

    @property
    def is_active(self) -> bool:
        """Returns whether MLflow tracking is currently functional."""
        return self.enabled and self._is_active and self._mlflow is not None

    @contextmanager
    def start_run(self, run_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
        """Context manager to scope an active MLflow run with reproducibility tags."""
        if not self.is_active:
            yield None
            return

        run_tags = {
            "system": "regintel-rag",
            "version": settings.regintel_version,
            "git_commit": get_git_commit_hash(),
            "timestamp": datetime.utcnow().isoformat()
        }
        if tags:
            run_tags.update(tags)

        try:
            with self._mlflow.start_run(run_name=run_name, tags=run_tags) as run:
                yield run
        except Exception as e:
            logger.error(f"Error during MLflow run execution '{run_name}': {e}")
            yield None

    def log_params(self, params: Dict[str, Any]) -> None:
        """Logs a dictionary of parameters/hyperparameters."""
        if not self.is_active:
            return
        try:
            sanitized = {str(k): str(v) if not isinstance(v, (int, float, bool, str)) else v for k, v in params.items()}
            self._mlflow.log_params(sanitized)
        except Exception as e:
            logger.warning(f"Failed to log parameters to MLflow: {e}")

    def log_metrics(self, metrics: Dict[str, Union[int, float]], step: Optional[int] = None) -> None:
        """Logs scalar numerical metrics."""
        if not self.is_active:
            return
        try:
            clean_metrics = {}
            for k, v in metrics.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    clean_metrics[str(k)] = float(v)
            if clean_metrics:
                self._mlflow.log_metrics(clean_metrics, step=step)
        except Exception as e:
            logger.warning(f"Failed to log metrics to MLflow: {e}")

    def log_artifact(self, local_path: Union[str, Path], artifact_path: Optional[str] = None) -> None:
        """Logs a local file or directory as an MLflow artifact."""
        if not self.is_active:
            return
        try:
            path_obj = Path(local_path)
            if path_obj.exists():
                self._mlflow.log_artifact(str(path_obj), artifact_path=artifact_path)
        except Exception as e:
            logger.warning(f"Failed to log artifact '{local_path}' to MLflow: {e}")

    def log_dict(self, dictionary: Dict[str, Any], artifact_file: str) -> None:
        """Logs a JSON dictionary directly as an artifact."""
        if not self.is_active:
            return
        try:
            self._mlflow.log_dict(dictionary, artifact_file)
        except Exception as e:
            logger.warning(f"Failed to log dictionary artifact '{artifact_file}' to MLflow: {e}")

    def log_retrieval_evaluation(
        self,
        method: str,
        top_k: int,
        metrics: Dict[str, float],
        dataset_size: int,
        parameters: Optional[Dict[str, Any]] = None,
        results_file: Optional[Union[str, Path]] = None
    ) -> None:
        """Dedicated logger for retrieval benchmark runs with detailed retrieval parameters."""
        run_name = f"retrieval_{method}_k{top_k}"
        tags = {
            "evaluation_type": "retrieval",
            "retrieval_method": method
        }

        with self.start_run(run_name=run_name, tags=tags):
            params = {
                "retrieval_method": method,
                "embedding_model": settings.embedding_model,
                "embedding_dimensions": settings.embedding_dimension,
                "vector_index": "vector_index_cosine",
                "vector_top_k": top_k,
                "num_candidates": 20,
                "bm25_enabled": method in ("bm25", "hybrid", "hybrid_reranked"),
                "hybrid_enabled": "hybrid" in method,
                "vector_weight": 0.5 if "hybrid" in method else (1.0 if method == "vector" else 0.0),
                "bm25_weight": 0.5 if "hybrid" in method else (1.0 if method == "bm25" else 0.0),
                "reranker_enabled": "reranked" in method,
                "reranker_model": "BAAI/bge-reranker-v2-m3",
                "reranker_top_k": top_k,
                "temporal_boost_weight": settings.temporal_boost_weight,
                "dataset_size": dataset_size,
                "evaluation_dataset_version": "2026.08-sebi-retrieval-v1",
                "corpus_version": "2026.08.28-sebi-v1"
            }
            if parameters:
                params.update(parameters)
            self.log_params(params)
            self.log_metrics(metrics)

            if results_file:
                self.log_artifact(results_file, artifact_path="evaluation_results")

    def log_generation_evaluation(
        self,
        model_name: str,
        metrics: Dict[str, float],
        dataset_size: int,
        parameters: Optional[Dict[str, Any]] = None,
        results_file: Optional[Union[str, Path]] = None
    ) -> None:
        """Dedicated logger for end-to-end RAG generation benchmark runs."""
        run_name = f"generation_{model_name}"
        tags = {
            "evaluation_type": "generation",
            "model_name": model_name
        }

        with self.start_run(run_name=run_name, tags=tags):
            params = {
                "llm_model": model_name,
                "generation_temperature": 0.2,
                "max_output_tokens": 2048,
                "prompt_version": "v2-regulatory-grounded",
                "dataset_size": dataset_size,
                "evaluation_dataset_version": "2026.08-sebi-generation-v1",
                "corpus_version": "2026.08.28-sebi-v1",
                "embedding_model": settings.embedding_model
            }
            if parameters:
                params.update(parameters)
            self.log_params(params)
            self.log_metrics(metrics)

            if results_file:
                self.log_artifact(results_file, artifact_path="evaluation_results")


# Aliases
MLflowExperimentTracker = MLflowTracker
mlflow_tracker = MLflowTracker()
