"""
Connector Management and Health API Routes (Phases 66–69).

Provides REST endpoints for:
- Listing registered regulatory connectors and supported authorities
- Listing official regulatory sources
- Querying connector health statuses
- Viewing historical crawl execution runs
- Triggering connector ingestion runs
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, status
from pydantic import BaseModel, Field

from app.connectors import (
    RegulatoryAuthority,
    AuthorityMetadata,
    RegulatorySource,
    ConnectorRun,
    ConnectorHealth,
    connector_registry,
    source_registry,
    connector_tracker,
    list_authorities,
    get_authority_metadata
)
from app.ingestion.pipeline import IngestionPipeline

logger = logging.getLogger("regintel.api.connectors")
router = APIRouter(prefix="/api/connectors", tags=["Regulatory Connectors & Sources"])


class TriggerRunRequest(BaseModel):
    """Payload to trigger an ingestion run for a specific connector."""
    limit: Optional[int] = Field(default=10, ge=1, le=100, description="Max candidate documents to process")
    dry_run: bool = Field(default=False, description="Simulate without database writes")
    force: bool = Field(default=False, description="Force re-chunking and re-processing")


class TriggerRunResponse(BaseModel):
    """Response returned when a connector run is initiated."""
    message: str
    authority: str
    run_id: str
    status: str


@router.get("", response_model=List[AuthorityMetadata], summary="List Registered Regulatory Authorities")
def get_connectors():
    """Returns all supported financial regulatory authorities and their domains."""
    return list_authorities()


@router.get("/sources", response_model=List[RegulatorySource], summary="List Regulatory Sources")
def get_sources(
    authority: Optional[str] = Query(default=None, description="Filter by authority e.g. SEBI, RBI, IRDAI, PFRDA, IFSCA"),
    enabled_only: bool = Query(default=True, description="Return only active enabled sources")
):
    """Returns official registered sources from the SourceRegistry."""
    return source_registry.get_sources(authority=authority, enabled_only=enabled_only)


@router.get("/health", response_model=List[ConnectorHealth], summary="Get Connector Health Dashboard")
def get_connectors_health():
    """Returns real-time health and execution status across all regulatory connectors."""
    return connector_tracker.get_all_health()


@router.get("/runs", response_model=List[ConnectorRun], summary="List Connector Execution Runs")
def get_connector_runs(
    authority: Optional[str] = Query(default=None, description="Filter by authority e.g. RBI"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of runs to return")
):
    """Returns historical execution runs and crawl metrics."""
    return connector_tracker.list_runs(authority=authority, limit=limit)


def _run_pipeline_background(authority_str: str, limit: Optional[int], dry_run: bool, force: bool):
    """Executes ingestion run in background thread."""
    try:
        pipeline = IngestionPipeline()
        pipeline.run(
            source=authority_str.lower(),
            limit=limit,
            dry_run=dry_run,
            force=force
        )
    except Exception as e:
        logger.error(f"Background connector run failed for {authority_str}: {e}", exc_info=True)


@router.post("/{authority}/run", response_model=TriggerRunResponse, summary="Trigger Connector Ingestion Run")
def trigger_connector_run(
    authority: str,
    payload: TriggerRunRequest,
    background_tasks: BackgroundTasks
):
    """Triggers an incremental ingestion run for a specific regulatory authority."""
    connector = connector_registry.get_connector(authority)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regulatory connector for '{authority}' not found. Supported: {[a.value for a in RegulatoryAuthority]}"
        )

    run = connector_tracker.start_run(connector.authority)
    background_tasks.add_task(
        _run_pipeline_background,
        authority_str=connector.authority.value,
        limit=payload.limit,
        dry_run=payload.dry_run,
        force=payload.force
    )

    return TriggerRunResponse(
        message=f"Connector run initiated for {connector.authority.value}",
        authority=connector.authority.value,
        run_id=run.run_id,
        status="RUNNING"
    )
