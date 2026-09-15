"""
FastAPI REST Routes for Regulatory Requirements, Obligations, and Compliance Checklists (Phases 61, 62, 63).
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Path, Body, status, Response

from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ComplianceChecklist,
    ChecklistItem,
)
from app.compliance.temporal_models import (
    RegulatoryDateEvent,
    TemporalStateEvaluation,
    RequirementTemporalState,
    ObligationTemporalState,
    ChecklistItemTemporalState,
    DateConflict,
)
from app.compliance.repository import get_compliance_repository
from app.compliance.requirement_extractor import get_requirement_extractor
from app.compliance.obligation_extractor import get_obligation_extractor
from app.compliance.checklist_generator import get_checklist_generator
from app.compliance.traceability import get_traceability_service, TraceabilityNode, ChecklistAuditReport
from app.compliance.export import export_checklist_to_markdown, export_checklist_to_json
from app.compliance.date_extractor import get_regulatory_date_extractor
from app.compliance.effective_state_engine import get_effective_state_engine
from app.compliance.alert_models import (
    RegulatoryEvent,
    RegulatoryDeadline,
    RegulatoryAlert,
    Watchlist,
)
from app.compliance.alert_engine import get_alert_engine
from app.compliance.deadline_engine import get_deadline_engine
from app.compliance.jobs import get_job_runner
from app.api.routes_documents import _load_doc_from_local_or_mongo
from app.change_detection.diff_engine import extract_hierarchical_sections

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Compliance & Intelligence"])

repo = get_compliance_repository()
req_extractor = get_requirement_extractor()
ob_extractor = get_obligation_extractor()
chk_generator = get_checklist_generator()
trace_service = get_traceability_service()
date_extractor = get_regulatory_date_extractor()
state_engine = get_effective_state_engine()
alert_engine = get_alert_engine()
deadline_engine = get_deadline_engine()
job_runner = get_job_runner()


# =============================================================================
# PHASE 61: REQUIREMENTS ROUTES (61.11)
# =============================================================================

@router.get("/requirements", response_model=List[RegulatoryRequirement], summary="List Regulatory Requirements")
def list_requirements(
    document_id: Optional[str] = Query(None, description="Filter by Document ID"),
    section_id: Optional[str] = Query(None, description="Filter by Section ID"),
    authority: Optional[str] = Query(None, description="Filter by Authority e.g. SEBI"),
    document_type: Optional[str] = Query(None, description="Filter by Document Type"),
    requirement_type: Optional[str] = Query(None, description="Filter by Requirement Type"),
    confidence: Optional[str] = Query(None, description="Filter by Confidence (HIGH, MEDIUM, LOW)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Queries extracted regulatory requirements with optional filters and pagination."""
    return repo.get_requirements(
        document_id=document_id,
        section_id=section_id,
        authority=authority,
        document_type=document_type,
        requirement_type=requirement_type,
        confidence=confidence,
        limit=limit,
        offset=offset
    )


@router.get("/requirements/{requirement_id}", response_model=RegulatoryRequirement, summary="Get Requirement by ID")
def get_requirement(
    requirement_id: str = Path(..., description="Unique requirement ID")
):
    """Retrieves a single requirement by ID."""
    req = repo.get_requirement_by_id(requirement_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Requirement '{requirement_id}' not found.")
    return req


@router.get("/documents/{document_id}/requirements", response_model=List[RegulatoryRequirement], summary="Get Document Requirements")
def get_document_requirements(
    document_id: str = Path(..., description="Document ID")
):
    """Returns all requirements extracted for a specific document."""
    return repo.get_requirements(document_id=document_id, limit=200)


@router.post("/documents/{document_id}/extract-requirements", response_model=List[RegulatoryRequirement], summary="Extract Requirements from Document")
def extract_document_requirements(
    document_id: str = Path(..., description="Document ID to extract requirements from"),
    use_llm: bool = Query(False, description="Whether to invoke LLM for semantic enrichment"),
    force: bool = Query(False, description="Force re-extraction even if already saved")
):
    """
    Extracts requirements for a document. Extracts across hierarchical sections,
    normalizes, validates, and persists results.
    """
    if not force:
        existing = repo.get_requirements(document_id=document_id, limit=200)
        if existing:
            return existing

    doc_data = _load_doc_from_local_or_mongo(document_id)
    if not doc_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")

    content = doc_data.get("content", "")
    title = doc_data.get("title", "")
    doc_type = doc_data.get("document_type", "Circular")
    source = doc_data.get("source", "SEBI")
    eff_date = doc_data.get("effective_date")

    # Extract sections preserving hierarchy
    sections = extract_hierarchical_sections(content, document_id=document_id)
    extracted_reqs: List[RegulatoryRequirement] = []

    if not sections:
        # Fallback to whole content
        reqs = req_extractor.extract_requirements_from_text(
            text=content,
            document_id=document_id,
            authority=source,
            document_title=title,
            document_type=doc_type,
            effective_date=eff_date,
            use_llm=use_llm
        )
        extracted_reqs.extend(reqs)
    else:
        for sec in sections:
            reqs = req_extractor.extract_requirements_from_text(
                text=sec.content,
                document_id=document_id,
                authority=source,
                document_title=title,
                document_type=doc_type,
                effective_date=eff_date,
                section_id=sec.section_id,
                section_number=sec.section_number,
                heading=sec.heading,
                page_number=sec.page_start,
                use_llm=use_llm
            )
            extracted_reqs.extend(reqs)

    # Persist
    repo.save_requirements(extracted_reqs)

    # Automatically derive and persist baseline obligations as well (Phase 62)
    obs = ob_extractor.extract_obligations(extracted_reqs, document_status=doc_data.get("status"))
    repo.save_obligations(obs)

    return extracted_reqs


# =============================================================================
# PHASE 62: OBLIGATIONS ROUTES (62.9)
# =============================================================================

@router.get("/obligations", response_model=List[RegulatoryObligation], summary="List Regulatory Obligations")
def list_obligations(
    document_id: Optional[str] = Query(None, description="Filter by Document ID"),
    requirement_id: Optional[str] = Query(None, description="Filter by Requirement ID"),
    obligated_party: Optional[str] = Query(None, description="Filter by Obligated Party e.g. Investment Adviser"),
    obligation_type: Optional[str] = Query(None, description="Filter by Deontic Type e.g. MANDATORY, PROHIBITION"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by Lifecycle Status e.g. ACTIVE, SUPERSEDED"),
    confidence: Optional[str] = Query(None, description="Filter by Confidence"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Queries operational obligations with optional filters and pagination."""
    return repo.get_obligations(
        document_id=document_id,
        requirement_id=requirement_id,
        obligated_party=obligated_party,
        obligation_type=obligation_type,
        status=status_filter,
        confidence=confidence,
        limit=limit,
        offset=offset
    )


@router.get("/obligations/{obligation_id}", response_model=RegulatoryObligation, summary="Get Obligation by ID")
def get_obligation(
    obligation_id: str = Path(..., description="Obligation ID")
):
    """Retrieves a single obligation by ID."""
    ob = repo.get_obligation_by_id(obligation_id)
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Obligation '{obligation_id}' not found.")
    return ob


@router.get("/requirements/{requirement_id}/obligations", response_model=List[RegulatoryObligation], summary="Get Obligations for Requirement")
def get_requirement_obligations(
    requirement_id: str = Path(..., description="Requirement ID")
):
    """Returns all obligations derived from a specific requirement."""
    return repo.get_obligations(requirement_id=requirement_id)


@router.get("/documents/{document_id}/obligations", response_model=List[RegulatoryObligation], summary="Get Document Obligations")
def get_document_obligations(
    document_id: str = Path(..., description="Document ID")
):
    """Returns all obligations for a specific document."""
    return repo.get_obligations(document_id=document_id, limit=200)


# =============================================================================
# PHASE 63: COMPLIANCE CHECKLISTS ROUTES (63.10)
# =============================================================================

@router.post("/compliance/checklists/generate", response_model=ComplianceChecklist, summary="Generate Compliance Checklist")
def generate_checklist(
    payload: Dict[str, Any] = Body(
        ...,
        examples=[{
            "title": "Investment Adviser Annual Compliance Review",
            "document_ids": ["doc_ia_2024"],
            "authority": "SEBI",
            "entity_filter": "Investment Adviser",
            "description": "Standard checklist for IA regulatory obligations."
        }]
    )
):
    """
    Generates a new, evidence-grounded Compliance Checklist from active obligations.
    """
    title = payload.get("title") or "Regulatory Compliance Checklist"
    doc_ids = payload.get("document_ids") or []
    authority = payload.get("authority") or "SEBI"
    entity_filter = payload.get("entity_filter")
    description = payload.get("description")

    # Gather obligations for the specified documents
    obligations: List[RegulatoryObligation] = []
    if doc_ids:
        for did in doc_ids:
            obs = repo.get_obligations(document_id=did, limit=100)
            if not obs:
                # If obligations haven't been extracted yet, trigger extraction
                extract_document_requirements(document_id=did)
                obs = repo.get_obligations(document_id=did, limit=100)
            obligations.extend(obs)
    else:
        obligations = repo.get_obligations(authority=authority, limit=100)

    if not obligations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No obligations found for the specified scope. Ingest or extract requirements first."
        )

    checklist = chk_generator.generate_checklist(
        title=title,
        obligations=obligations,
        document_ids=doc_ids,
        authority=authority,
        entity_filter=entity_filter,
        description=description
    )

    repo.save_checklist(checklist)
    return checklist


@router.get("/compliance/checklists", response_model=List[ComplianceChecklist], summary="List Compliance Checklists")
def list_checklists(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Lists saved compliance checklists."""
    return repo.get_checklists(limit=limit, offset=offset)


@router.get("/compliance/checklists/{checklist_id}", response_model=ComplianceChecklist, summary="Get Checklist Details")
def get_checklist_details(
    checklist_id: str = Path(..., description="Checklist ID")
):
    """Retrieves a compliance checklist by ID."""
    chk = repo.get_checklist_by_id(checklist_id)
    if not chk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Checklist '{checklist_id}' not found.")
    return chk


@router.patch("/compliance/checklists/{checklist_id}/items/{item_id}", response_model=ComplianceChecklist, summary="Update Checklist Item Status")
def update_checklist_item(
    checklist_id: str = Path(...),
    item_id: str = Path(...),
    payload: Dict[str, Any] = Body(..., examples=[{"status": "COMPLIANT", "notes": "Filing verified on portal on 2024-09-01."}])
):
    """
    Updates the review status and notes for a specific checklist item.
    """
    status_val = payload.get("status")
    notes_val = payload.get("notes")

    chk = repo.update_checklist_item_status(
        checklist_id=checklist_id,
        item_id=item_id,
        status=status_val,
        notes=notes_val
    )
    if not chk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist or item not found.")
    return chk


@router.post("/compliance/checklists/{checklist_id}/regenerate", response_model=ComplianceChecklist, summary="Regenerate Checklist after Regulatory Changes")
def regenerate_checklist(
    checklist_id: str = Path(..., description="Checklist ID to re-sync")
):
    """
    Re-syncs a checklist against current regulatory versions while preserving reviewer notes and status.
    """
    existing = repo.get_checklist_by_id(checklist_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Checklist '{checklist_id}' not found.")

    # Re-fetch latest obligations for its document scope
    latest_obs: List[RegulatoryObligation] = []
    for did in existing.document_ids:
        obs = repo.get_obligations(document_id=did, limit=100)
        latest_obs.extend(obs)

    fresh = chk_generator.regenerate_checklist(
        existing_checklist=existing,
        new_obligations=latest_obs
    )
    repo.save_checklist(fresh)
    return fresh


@router.get("/compliance/checklists/{checklist_id}/export", summary="Export Compliance Checklist")
def export_checklist(
    checklist_id: str = Path(...),
    format_type: str = Query("markdown", alias="format", pattern="^(markdown|json)$")
):
    """Exports a checklist to Markdown or JSON format."""
    chk = repo.get_checklist_by_id(checklist_id)
    if not chk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Checklist '{checklist_id}' not found.")

    if format_type == "json":
        return Response(
            content=export_checklist_to_json(chk),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{checklist_id}.json"'}
        )
    else:
        return Response(
            content=export_checklist_to_markdown(chk),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{checklist_id}.md"'}
        )


@router.get("/compliance/checklists/{checklist_id}/traceability/{item_id}", response_model=TraceabilityNode, summary="Trace Item Provenance")
def trace_item_provenance(
    checklist_id: str = Path(...),
    item_id: str = Path(...)
):
    """
    Returns full bidirectional traceability node: Item -> Obligation -> Requirement -> Source Evidence.
    """
    chk = repo.get_checklist_by_id(checklist_id)
    if not chk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Checklist '{checklist_id}' not found.")

    item = next((it for it in chk.items if it.item_id == item_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Item '{item_id}' not found in checklist.")

    return trace_service.get_item_traceability(item)


@router.get("/compliance/checklists/{checklist_id}/audit", response_model=ChecklistAuditReport, summary="Audit Checklist Integrity")
def audit_checklist_endpoint(
    checklist_id: str = Path(...)
):
    """
    Audits an entire checklist to detect orphan items, broken references, and ungrounded claims.
    """
    chk = repo.get_checklist_by_id(checklist_id)
    if not chk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Checklist '{checklist_id}' not found.")

    return trace_service.audit_checklist(chk)


# =============================================================================
# PHASE 64: EFFECTIVE-DATE INTELLIGENCE ROUTES (64.8, 64.9, 64.14, 64.15)
# =============================================================================

@router.get("/regulatory-state/{document_id}", response_model=TemporalStateEvaluation, summary="Get Regulatory Effective State")
def get_document_regulatory_state(
    document_id: str = Path(..., description="Document ID"),
    as_of: Optional[str] = Query(None, description="Historical or future reference date (YYYY-MM-DD)")
):
    """
    Evaluates the regulatory state of a document as of an arbitrary date (64.8, 64.9).
    Answers: Was this document effective on [as_of_date]?
    """
    doc_data = _load_doc_from_local_or_mongo(document_id)
    if not doc_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")

    date_events = repo.get_date_events(document_id=document_id)
    return state_engine.get_regulatory_state(
        doc_data=doc_data,
        as_of_date=as_of,
        date_events=date_events
    )


@router.get("/requirements/{requirement_id}/state", response_model=RequirementTemporalState, summary="Get Requirement Temporal State")
def get_requirement_temporal_state(
    requirement_id: str = Path(..., description="Requirement ID"),
    as_of: Optional[str] = Query(None, description="Reference date (YYYY-MM-DD)")
):
    """
    Evaluates whether a specific requirement was active on as_of_date (64.10).
    """
    req = repo.get_requirement_by_id(requirement_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Requirement '{requirement_id}' not found.")

    doc_eval = None
    doc_data = _load_doc_from_local_or_mongo(req.document_id)
    if doc_data:
        date_events = repo.get_date_events(document_id=req.document_id)
        doc_eval = state_engine.get_regulatory_state(doc_data=doc_data, as_of_date=as_of, date_events=date_events)

    return state_engine.evaluate_requirement_temporal_state(
        requirement=req,
        as_of_date=as_of,
        document_eval=doc_eval
    )


@router.get("/obligations/{obligation_id}/state", response_model=ObligationTemporalState, summary="Get Obligation Temporal State")
def get_obligation_temporal_state(
    obligation_id: str = Path(..., description="Obligation ID"),
    as_of: Optional[str] = Query(None, description="Reference date (YYYY-MM-DD)")
):
    """
    Evaluates operational obligation lifecycle state relative to as_of_date (64.11).
    """
    ob = repo.get_obligation_by_id(obligation_id)
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Obligation '{obligation_id}' not found.")

    doc_eval = None
    doc_data = _load_doc_from_local_or_mongo(ob.document_id)
    if doc_data:
        date_events = repo.get_date_events(document_id=ob.document_id)
        doc_eval = state_engine.get_regulatory_state(doc_data=doc_data, as_of_date=as_of, date_events=date_events)

    return state_engine.evaluate_obligation_temporal_state(
        obligation=ob,
        as_of_date=as_of,
        document_eval=doc_eval
    )


@router.get("/compliance/checklists/{checklist_id}/temporal-state", response_model=List[ChecklistItemTemporalState], summary="Get Checklist Temporal State")
def get_checklist_temporal_state(
    checklist_id: str = Path(..., description="Checklist ID"),
    as_of: Optional[str] = Query(None, description="Reference date (YYYY-MM-DD)")
):
    """
    Evaluates temporal applicability for all items in a checklist as of a given date (64.12).
    """
    chk = repo.get_checklist_by_id(checklist_id)
    if not chk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Checklist '{checklist_id}' not found.")

    results: List[ChecklistItemTemporalState] = []
    for it in chk.items:
        ob = repo.get_obligation_by_id(it.obligation_id)
        ob_state = None
        if ob:
            doc_data = _load_doc_from_local_or_mongo(ob.document_id)
            doc_eval = state_engine.get_regulatory_state(doc_data=doc_data, as_of_date=as_of) if doc_data else None
            ob_state = state_engine.evaluate_obligation_temporal_state(ob, as_of_date=as_of, document_eval=doc_eval)

        item_state = state_engine.evaluate_checklist_item_temporal_state(it, as_of_date=as_of, obligation_state=ob_state)
        results.append(item_state)

    return results


@router.post("/documents/{document_id}/extract-dates", response_model=List[RegulatoryDateEvent], summary="Extract Regulatory Date Events")
def extract_document_date_events(
    document_id: str = Path(...),
    use_llm: bool = Query(False, description="Whether to use LLM fallback for ambiguous clauses")
):
    """
    Extracts explicit, relative, and derived regulatory date events from document text (64.3, 64.5).
    """
    doc_data = _load_doc_from_local_or_mongo(document_id)
    if not doc_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")

    content = doc_data.get("content", "")
    pub_date = doc_data.get("published_date") or (doc_data.get("metadata", {}) or {}).get("published_date")
    notif_date = doc_data.get("notification_date") or (doc_data.get("metadata", {}) or {}).get("notification_date")

    events = date_extractor.extract_dates(
        text=content,
        document_id=document_id,
        known_publication_date=pub_date,
        known_notification_date=notif_date,
        use_llm_fallback=use_llm
    )
    repo.save_date_events(events)
    return events


@router.get("/documents/{document_id}/dates", response_model=List[RegulatoryDateEvent], summary="Get Document Date Events")
def get_document_date_events(
    document_id: str = Path(...)
):
    """Returns all stored regulatory date events for a document."""
    return repo.get_date_events(document_id=document_id)


@router.get("/regulatory-events/calendar", response_model=List[RegulatoryDateEvent], summary="Get Regulatory Events Calendar")
def get_regulatory_calendar(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    event_type: Optional[str] = Query(None, description="Filter by event type e.g. EFFECTIVE, EXPIRES")
):
    """Returns chronological regulatory date events within a date window for calendar views (64.14)."""
    return repo.get_calendar_date_events(start_date=start_date, end_date=end_date, event_type=event_type)


@router.get("/regulatory-events/upcoming", response_model=List[RegulatoryDateEvent], summary="Get Upcoming Regulatory Events")
def get_upcoming_regulatory_events(
    days: int = Query(30, ge=1, le=365, description="Lookahead window in days"),
    as_of: Optional[str] = Query(None, description="Reference date (YYYY-MM-DD)"),
    event_type: Optional[str] = Query(None, description="Filter by event type")
):
    """Returns regulatory changes becoming effective in the next N days (64.15)."""
    return repo.get_upcoming_date_events(days=days, as_of_date=as_of, event_type=event_type)


# =============================================================================
# PHASE 65: REGULATORY ALERT & DEADLINE INTELLIGENCE ROUTES (65.13, 65.14)
# =============================================================================

@router.get("/alerts", response_model=List[RegulatoryAlert], summary="List Regulatory Alerts")
def list_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    status: Optional[str] = Query(None, description="Filter by status (UNREAD, READ, DISMISSED)"),
    document_id: Optional[str] = Query(None, description="Filter by Document ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Retrieves active regulatory alerts with filtering and pagination (65.13)."""
    return repo.get_alerts(
        severity=severity,
        alert_type=alert_type,
        status=status,
        document_id=document_id,
        limit=limit,
        offset=offset
    )


@router.get("/alerts/{alert_id}", response_model=RegulatoryAlert, summary="Get Alert by ID")
def get_alert(
    alert_id: str = Path(..., description="Alert ID")
):
    """Retrieves full detail and explainability payload for a single alert (65.13, 65.18)."""
    alt = repo.get_alert_by_id(alert_id)
    if not alt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert '{alert_id}' not found.")
    return alt


@router.patch("/alerts/{alert_id}", response_model=RegulatoryAlert, summary="Update Alert")
def patch_alert(
    alert_id: str = Path(...),
    payload: Dict[str, Any] = Body(...)
):
    """Updates alert status."""
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'status' in payload.")
    alt = repo.update_alert_status(alert_id, new_status)
    if not alt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert '{alert_id}' not found.")
    return alt


@router.post("/alerts/{alert_id}/read", response_model=RegulatoryAlert, summary="Mark Alert as Read")
def mark_alert_read(
    alert_id: str = Path(...)
):
    """Marks an alert as read (65.13)."""
    alt = repo.update_alert_status(alert_id, "READ")
    if not alt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert '{alert_id}' not found.")
    return alt


@router.post("/alerts/{alert_id}/dismiss", response_model=RegulatoryAlert, summary="Dismiss Alert")
def dismiss_alert(
    alert_id: str = Path(...)
):
    """Dismisses an alert from view (65.13)."""
    alt = repo.update_alert_status(alert_id, "DISMISSED")
    if not alt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert '{alert_id}' not found.")
    return alt


@router.get("/deadlines", response_model=List[RegulatoryDeadline], summary="List Compliance Deadlines")
def list_deadlines(
    document_id: Optional[str] = Query(None, description="Filter by Document ID"),
    obligation_id: Optional[str] = Query(None, description="Filter by Obligation ID"),
    status: Optional[str] = Query(None, description="Filter by deadline status (UPCOMING, DUE_SOON, OVERDUE)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Lists compliance deadlines including bounded recurring occurrences (65.2, 65.4)."""
    return repo.get_deadlines(
        document_id=document_id,
        obligation_id=obligation_id,
        status=status,
        limit=limit,
        offset=offset
    )


@router.get("/watchlists", response_model=List[Watchlist], summary="List Watchlists")
def list_watchlists(
    user_id: Optional[str] = Query(None, description="Filter by User ID")
):
    """Lists configured regulatory watchlists (65.9)."""
    return repo.get_watchlists(user_id=user_id)


@router.post("/watchlists", response_model=Watchlist, summary="Create or Update Watchlist")
def save_user_watchlist(
    payload: Dict[str, Any] = Body(...)
):
    """Creates or updates a user regulatory watchlist (65.9)."""
    w_id = payload.get("watchlist_id") or f"wtch_{uuid.uuid4().hex[:10]}"
    watchlist = Watchlist(
        watchlist_id=w_id,
        user_id=payload.get("user_id", "default_user"),
        name=payload.get("name", "Custom Watchlist"),
        authorities=payload.get("authorities", []),
        document_ids=payload.get("document_ids", []),
        topics=payload.get("topics", []),
        requirement_types=payload.get("requirement_types", []),
        obligation_types=payload.get("obligation_types", []),
        event_types=payload.get("event_types", []),
        is_active=payload.get("is_active", True)
    )
    return repo.save_watchlist(watchlist)


@router.get("/watchlists/{watchlist_id}", response_model=Watchlist, summary="Get Watchlist by ID")
def get_watchlist(
    watchlist_id: str = Path(...)
):
    """Retrieves a single watchlist by ID."""
    w = repo.get_watchlist_by_id(watchlist_id)
    if not w:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Watchlist '{watchlist_id}' not found.")
    return w


@router.post("/jobs/run-alert-evaluation", summary="Trigger Regulatory Alert Evaluation Job")
def trigger_alert_evaluation(
    as_of: Optional[str] = Query(None, description="Reference date (YYYY-MM-DD)")
):
    """
    Triggers the scheduled intelligence evaluation job to evaluate upcoming effective dates,
    refresh recurring deadlines, generate alerts, and deduplicate (65.11, 65.12).
    """
    return job_runner.run_daily_evaluation(as_of_date=as_of)
