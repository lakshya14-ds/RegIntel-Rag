"""
Cross-Regulator Overlaps & Conflicts REST API Router (Phases 73 & 74).

Exposes:
- 73.16: GET /api/regulatory-overlaps, GET /api/regulatory-overlaps/{id}
- 74.19: GET /api/regulatory-conflicts, GET /api/regulatory-conflicts/{id}
- 74.16, 74.18: PATCH /api/regulatory-conflicts/{id}/status (Human review & audit trail)
- POST /api/regulatory-overlaps/analyze (Trigger cross-regulator overlap analysis)
"""

import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, Path

from app.compliance.overlap_models import RegulatoryOverlap, OverlapType, OverlapStatus
from app.compliance.conflict_models import RegulatoryConflict, ConflictResolutionStatus
from app.compliance.repository import get_compliance_repository
from app.compliance.overlap_engine import get_overlap_engine
from app.compliance.conflict_engine import get_conflict_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Cross-Regulator Intelligence"])


class ConflictStatusUpdateRequest(BaseModel):
    """Payload for human compliance officer review action (74.16, 74.18)."""
    new_status: ConflictResolutionStatus
    reviewer_id: str = "compliance_officer"
    notes: Optional[str] = None


class OverlapAnalysisRequest(BaseModel):
    """Payload to trigger on-demand cross-regulator overlap analysis."""
    requirement_id: Optional[str] = None
    use_llm: bool = True
    max_candidates: int = 15


@router.get("/regulatory-overlaps", response_model=List[RegulatoryOverlap])
async def list_regulatory_overlaps(
    authority: Optional[str] = Query(None, description="Filter by authority (SEBI, RBI, IRDAI, etc.)"),
    relationship_type: Optional[str] = Query(None, description="IDENTICAL, NEAR_DUPLICATE, OVERLAPPING, COMPLEMENTARY, etc."),
    topic: Optional[str] = Query(None, description="Controlled topic (KYC, AML, REPORTING, etc.)"),
    status: Optional[str] = Query(None, description="ACTIVE, HISTORICAL, FUTURE"),
    confidence: Optional[str] = Query(None, description="HIGH, MEDIUM, LOW"),
    requirement_id: Optional[str] = Query(None, description="Filter by specific requirement ID"),
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Returns paginated regulatory overlap records with multi-dimensional filtering (73.16)."""
    repo = get_compliance_repository()
    return repo.get_overlaps(
        authority=authority,
        relationship_type=relationship_type,
        topic=topic,
        status=status,
        confidence=confidence,
        requirement_id=requirement_id,
        document_id=document_id,
        limit=limit,
        offset=offset
    )


@router.get("/regulatory-overlaps/{overlap_id}", response_model=RegulatoryOverlap)
async def get_regulatory_overlap_detail(
    overlap_id: str = Path(..., description="Unique overlap record ID")
):
    """Retrieves full side-by-side evidence and reasoning for a specific overlap record (73.16, 73.18)."""
    repo = get_compliance_repository()
    overlap = repo.get_overlap_by_id(overlap_id)
    if not overlap:
        raise HTTPException(status_code=404, detail=f"Regulatory overlap '{overlap_id}' not found.")
    return overlap


@router.get("/regulatory-conflicts", response_model=List[RegulatoryConflict])
async def list_regulatory_conflicts(
    authority: Optional[str] = Query(None, description="Filter by authority (SEBI, RBI, etc.)"),
    conflict_type: Optional[str] = Query(None, description="PARAMETER_CONFLICT, DEADLINE_CONFLICT, etc."),
    severity: Optional[str] = Query(None, description="HIGH, MEDIUM, LOW"),
    confidence: Optional[str] = Query(None, description="HIGH, MEDIUM, LOW"),
    resolution_status: Optional[str] = Query(None, description="OPEN, UNDER_REVIEW, RESOLVED, DISMISSED, FALSE_POSITIVE"),
    requirement_id: Optional[str] = Query(None, description="Filter by requirement ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Returns potential regulatory conflicts and inconsistencies (74.19)."""
    repo = get_compliance_repository()
    return repo.get_conflicts(
        authority=authority,
        conflict_type=conflict_type,
        severity=severity,
        confidence=confidence,
        resolution_status=resolution_status,
        requirement_id=requirement_id,
        limit=limit,
        offset=offset
    )


@router.get("/regulatory-conflicts/{conflict_id}", response_model=RegulatoryConflict)
async def get_regulatory_conflict_detail(
    conflict_id: str = Path(..., description="Unique conflict record ID")
):
    """Retrieves full conflict details including conflicting parameters and evidence (74.19, 74.21)."""
    repo = get_compliance_repository()
    conflict = repo.get_conflict_by_id(conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail=f"Regulatory conflict '{conflict_id}' not found.")
    return conflict


@router.patch("/regulatory-conflicts/{conflict_id}/status", response_model=RegulatoryConflict)
async def update_regulatory_conflict_status(
    conflict_id: str = Path(..., description="Unique conflict record ID"),
    payload: ConflictStatusUpdateRequest = ...
):
    """Updates resolution status for human review workflow and logs immutable audit event (74.16, 74.18)."""
    repo = get_compliance_repository()
    updated = repo.update_conflict_status(
        conflict_id=conflict_id,
        new_status=payload.new_status,
        reviewer_id=payload.reviewer_id,
        notes=payload.notes
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Conflict '{conflict_id}' not found.")
    return updated


@router.post("/regulatory-overlaps/analyze")
async def analyze_regulatory_overlaps(
    payload: OverlapAnalysisRequest
):
    """
    Triggers on-demand cross-regulator candidate discovery, overlap classification,
    and potential conflict identification for a given requirement or across all requirements.
    """
    repo = get_compliance_repository()
    overlap_engine = get_overlap_engine()
    conflict_engine = get_conflict_engine()

    all_reqs = repo.get_requirements(limit=500)
    if not all_reqs:
        return {"status": "success", "overlaps_detected": 0, "conflicts_detected": 0, "message": "No requirements found in repository."}

    target_reqs = [r for r in all_reqs if r.requirement_id == payload.requirement_id] if payload.requirement_id else all_reqs[:50]

    detected_overlaps: List[RegulatoryOverlap] = []
    detected_conflicts: List[RegulatoryConflict] = []

    for req in target_reqs:
        candidates = overlap_engine.generate_candidates_for_requirement(
            target_req=req,
            candidate_pool=all_reqs,
            max_candidates=payload.max_candidates
        )
        for cand, score, topic in candidates:
            ovl = overlap_engine.analyze_pair(req, cand, use_llm=payload.use_llm)
            if ovl:
                detected_overlaps.append(ovl)
                # Check for potential conflicts
                cnf = conflict_engine.detect_conflicts_from_overlap(ovl, req, cand, use_llm=payload.use_llm)
                if cnf:
                    detected_conflicts.append(cnf)

    if detected_overlaps:
        repo.save_overlaps(detected_overlaps)
    if detected_conflicts:
        repo.save_conflicts(detected_conflicts)

    return {
        "status": "success",
        "requirements_evaluated": len(target_reqs),
        "overlaps_detected": len(detected_overlaps),
        "conflicts_detected": len(detected_conflicts)
    }
