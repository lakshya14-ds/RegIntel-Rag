"""
FastAPI REST Routes for Regulatory Requirements, Obligations, and Compliance Checklists (Phases 61, 62, 63).
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Path, Body, status, Response

from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    ComplianceChecklist,
    ChecklistItem,
)
from app.compliance.repository import get_compliance_repository
from app.compliance.requirement_extractor import get_requirement_extractor
from app.compliance.obligation_extractor import get_obligation_extractor
from app.compliance.checklist_generator import get_checklist_generator
from app.compliance.traceability import get_traceability_service, TraceabilityNode, ChecklistAuditReport
from app.compliance.export import export_checklist_to_markdown, export_checklist_to_json
from app.api.routes_documents import _load_doc_from_local_or_mongo
from app.change_detection.diff_engine import extract_hierarchical_sections

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Compliance & Intelligence"])

repo = get_compliance_repository()
req_extractor = get_requirement_extractor()
ob_extractor = get_obligation_extractor()
chk_generator = get_checklist_generator()
trace_service = get_traceability_service()


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
