"""
Connector Health and Run History Tracking (Phase 66).

Tracks crawl executions, errors, status, and health metrics across all
regulatory connectors without faking data.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

from app.config import settings
from app.connectors.authority import RegulatoryAuthority, list_authorities

logger = logging.getLogger("regintel.connectors.health")

RUNS_DIR = Path("data/ingestion/runs")
RUNS_DIR.mkdir(parents=True, exist_ok=True)


class ConnectorRun(BaseModel):
    """Model tracking an individual crawl or synchronization run of a connector."""
    run_id: str
    authority: RegulatoryAuthority
    started_at: str
    completed_at: Optional[str] = None
    status: Literal["RUNNING", "SUCCESS", "PARTIAL_SUCCESS", "FAILED"] = "RUNNING"
    discovered_count: int = 0
    downloaded_count: int = 0
    new_documents: int = 0
    changed_documents: int = 0
    skipped_documents: int = 0
    failed_documents: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    duration_seconds: Optional[float] = None


class ConnectorHealth(BaseModel):
    """Aggregated health status for a specific regulatory connector."""
    authority: RegulatoryAuthority
    status: Literal["HEALTHY", "WARNING", "FAILED", "UNKNOWN"] = "UNKNOWN"
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None
    last_run_id: Optional[str] = None
    total_discovered_last_run: int = 0
    consecutive_failures: int = 0
    error_summary: Optional[str] = None


class ConnectorRunTracker:
    """Manages recording and retrieval of connector execution runs and health status."""

    def __init__(self, runs_dir: Optional[Path] = None):
        self.runs_dir = runs_dir or RUNS_DIR
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._db = None

    def _get_db(self):
        if self._db is None:
            try:
                from app.db import MongoDBManager
                manager = MongoDBManager()
                self._db = manager.db
            except Exception:
                self._db = None
        return self._db

    def start_run(self, authority: RegulatoryAuthority | str) -> ConnectorRun:
        """Initializes a new connector run record."""
        auth_enum = RegulatoryAuthority(authority.strip().upper()) if isinstance(authority, str) else authority
        run_id = f"RUN_{auth_enum.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        run = ConnectorRun(
            run_id=run_id,
            authority=auth_enum,
            started_at=datetime.utcnow().isoformat(),
            status="RUNNING"
        )
        self._save_run(run)
        logger.info(f"Started connector run {run_id} for {auth_enum.value}")
        return run

    def finish_run(
        self,
        run: ConnectorRun,
        discovered: int = 0,
        downloaded: int = 0,
        new_docs: int = 0,
        changed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        errors: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[str]] = None
    ) -> ConnectorRun:
        """Finalizes a connector run with outcome metrics."""
        now = datetime.utcnow()
        run.completed_at = now.isoformat()
        run.discovered_count = discovered
        run.downloaded_count = downloaded
        run.new_documents = new_docs
        run.changed_documents = changed
        run.skipped_documents = skipped
        run.failed_documents = failed
        run.errors = errors or []
        run.warnings = warnings or []

        try:
            start_dt = datetime.fromisoformat(run.started_at)
            run.duration_seconds = round((now - start_dt).total_seconds(), 2)
        except Exception:
            run.duration_seconds = None

        if failed == 0 and not errors:
            run.status = "SUCCESS"
        elif downloaded > 0 or new_docs > 0 or skipped > 0:
            run.status = "PARTIAL_SUCCESS"
        else:
            run.status = "FAILED"

        self._save_run(run)
        logger.info(f"Completed connector run {run.run_id} for {run.authority.value} with status={run.status}")
        return run

    def _save_run(self, run: ConnectorRun):
        """Saves run to MongoDB and local JSON fallback."""
        # 1. Mongo
        db = self._get_db()
        if db is not None:
            try:
                db["connector_runs"].update_one(
                    {"run_id": run.run_id},
                    {"$set": run.model_dump()},
                    upsert=True
                )
            except Exception as e:
                logger.warning(f"Failed to persist run {run.run_id} to Mongo: {e}")

        # 2. Local JSON
        try:
            fpath = self.runs_dir / f"{run.run_id}.json"
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(run.model_dump(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save local run file {run.run_id}: {e}")

    def list_runs(
        self,
        authority: Optional[RegulatoryAuthority | str] = None,
        limit: int = 20
    ) -> List[ConnectorRun]:
        """Lists recent connector runs filtered by authority."""
        auth_enum = None
        if authority:
            auth_enum = RegulatoryAuthority(authority.strip().upper()) if isinstance(authority, str) else authority

        # Try Mongo first
        db = self._get_db()
        if db is not None:
            try:
                query = {}
                if auth_enum:
                    query["authority"] = auth_enum.value
                cursor = db["connector_runs"].find(query).sort("started_at", -1).limit(limit)
                runs = []
                for doc in cursor:
                    doc.pop("_id", None)
                    runs.append(ConnectorRun.model_validate(doc))
                if runs:
                    return runs
            except Exception as e:
                logger.warning(f"Error querying runs from Mongo: {e}")

        # Fallback to local files
        runs = []
        for f in sorted(self.runs_dir.glob("RUN_*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                    run = ConnectorRun.model_validate(data)
                    if auth_enum and run.authority != auth_enum:
                        continue
                    runs.append(run)
                    if len(runs) >= limit:
                        break
            except Exception:
                continue
        return runs

    def get_health(self, authority: RegulatoryAuthority | str) -> ConnectorHealth:
        """Computes current health status for an authority based on recent runs."""
        auth_enum = RegulatoryAuthority(authority.strip().upper()) if isinstance(authority, str) else authority
        runs = self.list_runs(authority=auth_enum, limit=5)

        if not runs:
            return ConnectorHealth(
                authority=auth_enum,
                status="UNKNOWN",
                error_summary="No runs recorded yet"
            )

        latest_run = runs[0]
        consecutive_fails = 0
        for r in runs:
            if r.status == "FAILED":
                consecutive_fails += 1
            else:
                break

        if latest_run.status == "SUCCESS":
            health_status = "HEALTHY"
        elif latest_run.status == "PARTIAL_SUCCESS":
            health_status = "WARNING"
        elif consecutive_fails > 0:
            health_status = "FAILED"
        else:
            health_status = "UNKNOWN"

        err_summary = None
        if latest_run.errors:
            err_summary = str(latest_run.errors[0].get("message") or latest_run.errors[0])

        return ConnectorHealth(
            authority=auth_enum,
            status=health_status,
            last_run_at=latest_run.completed_at or latest_run.started_at,
            last_run_status=latest_run.status,
            last_run_id=latest_run.run_id,
            total_discovered_last_run=latest_run.discovered_count,
            consecutive_failures=consecutive_fails,
            error_summary=err_summary
        )

    def get_all_health(self) -> List[ConnectorHealth]:
        """Returns health summaries across all defined authorities."""
        return [self.get_health(auth.code) for auth in list_authorities()]


# Global singleton tracker
connector_tracker = ConnectorRunTracker()
