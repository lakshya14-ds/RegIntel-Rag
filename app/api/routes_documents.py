"""
Document and Version Management API Routes for RegIntel FastAPI.
"""

import json
import logging
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.responses import DocumentMetadataResponse, DocumentVersionResponse, DocumentRelationshipResponse
from app.ingestion.repository import DocumentRepository
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Documents & Versions"])

_doc_repo: Optional[DocumentRepository] = None


def get_doc_repo() -> DocumentRepository:
    global _doc_repo
    if _doc_repo is None:
        _doc_repo = DocumentRepository()
    return _doc_repo


def _load_doc_from_local_or_mongo(document_id: str) -> Optional[dict]:
    """Helper to load document metadata from Mongo or fallback processed JSON files."""
    try:
        repo = get_doc_repo()
        doc_model = repo.get_document(document_id)
        if doc_model:
            return doc_model.model_dump()
    except Exception:
        pass

    # Fallback to local files
    for fname in [f"{document_id}.json", f"sebi_{document_id}.json"]:
        json_path = settings.processed_data_dir / fname
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading local file {json_path}: {e}")

    # Glob fallback
    if settings.processed_data_dir.exists():
        for f in settings.processed_data_dir.glob("*.json"):
            if f.name.endswith("_chunks.json"):
                continue
            if document_id in f.name:
                try:
                    with open(f, "r", encoding="utf-8") as f_obj:
                        data = json.load(f_obj)
                        if data.get("document_id") == document_id:
                            return data
                except Exception:
                    pass
    return None


@router.get("/document/{document_id}", response_model=DocumentMetadataResponse, summary="Get Document Metadata")
def get_document_metadata(document_id: str) -> DocumentMetadataResponse:
    """
    Returns regulatory document metadata without embedding vectors.
    """
    doc_dict = _load_doc_from_local_or_mongo(document_id)
    if not doc_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regulatory document with ID '{document_id}' not found."
        )

    meta = doc_dict.get("metadata", {})
    return DocumentMetadataResponse(
        document_id=doc_dict.get("document_id", document_id),
        title=doc_dict.get("title"),
        source=doc_dict.get("source", "SEBI"),
        category=doc_dict.get("category") or meta.get("category"),
        document_type=doc_dict.get("document_type") or meta.get("document_type"),
        circular_number=doc_dict.get("circular_number") or meta.get("circular_number"),
        published_date=doc_dict.get("published_date") or meta.get("published_date"),
        effective_date=doc_dict.get("effective_date") or meta.get("effective_date"),
        status=doc_dict.get("status") or meta.get("status", "unknown"),
        url=doc_dict.get("url", ""),
        supersedes=doc_dict.get("supersedes") or meta.get("supersedes"),
        superseded_by=doc_dict.get("superseded_by") or meta.get("superseded_by"),
        document_version=doc_dict.get("document_version") or meta.get("document_version", "1.0"),
        content_hash=doc_dict.get("content_hash") or meta.get("content_hash"),
        relationship_type=doc_dict.get("relationship_type") or meta.get("relationship_type"),
        relationship_confidence=doc_dict.get("relationship_confidence") or meta.get("relationship_confidence")
    )


@router.get("/document/{document_id}/versions", response_model=DocumentVersionResponse, summary="Get Version Relationships & Timeline 2.0")
def get_document_versions(document_id: str) -> DocumentVersionResponse:
    """
    Returns explicit version relationships, predecessor, successor, and multi-branch chronological timeline (Phase 58).
    """
    from app.versioning.timeline import get_document_timeline
    from app.schemas.responses import TimelineNodeResponse, DocumentRelationshipResponse

    doc_dict = _load_doc_from_local_or_mongo(document_id)
    if not doc_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regulatory document with ID '{document_id}' not found."
        )

    timeline_data = get_document_timeline(document_id)
    raw_events = timeline_data.get("events", [])
    raw_rels = timeline_data.get("relationships", [])

    events_out: List[TimelineNodeResponse] = []
    for ev in raw_events:
        events_out.append(TimelineNodeResponse(
            document_id=ev.get("document_id", ""),
            title=ev.get("title"),
            published_date=ev.get("published_date"),
            effective_date=ev.get("effective_date"),
            status=ev.get("status", "UNKNOWN"),
            relationship=ev.get("relationship_to_previous", "RELATED_TO"),
            relationship_to_previous=ev.get("relationship_to_previous"),
            relationship_confidence=ev.get("relationship_confidence", "LOW"),
            evidence=ev.get("evidence"),
            is_branch=ev.get("is_branch", False),
            parent_document_id=ev.get("parent_document_id"),
            chronology_uncertain=ev.get("chronology_uncertain", False),
            order=ev.get("order", 0)
        ))

    rels_out: List[DocumentRelationshipResponse] = [
        DocumentRelationshipResponse(
            source_document_id=r.get("source_document_id", ""),
            target_document_id=r.get("target_document_id", ""),
            relationship_type=r.get("relationship_type", "RELATED_TO"),
            confidence=r.get("confidence", "LOW"),
            evidence=r.get("evidence"),
            is_explicit=r.get("is_explicit", False)
        )
        for r in raw_rels
    ]

    # Predecessor doc if reliable
    pred_doc = None
    pred_id = timeline_data.get("predecessor_id")
    if pred_id:
        pred_dict = _load_doc_from_local_or_mongo(pred_id)
        if pred_dict:
            pred_meta = pred_dict.get("metadata", {})
            pred_doc = DocumentMetadataResponse(
                document_id=pred_dict.get("document_id", pred_id),
                title=pred_dict.get("title"),
                source=pred_dict.get("source", "SEBI"),
                category=pred_dict.get("category") or pred_meta.get("category"),
                document_type=pred_dict.get("document_type") or pred_meta.get("document_type"),
                circular_number=pred_dict.get("circular_number") or pred_meta.get("circular_number"),
                published_date=pred_dict.get("published_date") or pred_meta.get("published_date"),
                effective_date=pred_dict.get("effective_date") or pred_meta.get("effective_date"),
                status=pred_dict.get("status") or pred_meta.get("status", "HISTORICAL"),
                url=pred_dict.get("url", "")
            )

    # Successor doc if any
    succ_doc = None
    succ_rel = next((r for r in raw_rels if r.get("target_document_id") == document_id and r.get("relationship_type") in ("SUPERSEDES", "REPLACES")), None)
    if succ_rel:
        succ_id = succ_rel.get("source_document_id")
        succ_dict = _load_doc_from_local_or_mongo(succ_id)
        if succ_dict:
            succ_meta = succ_dict.get("metadata", {})
            succ_doc = DocumentMetadataResponse(
                document_id=succ_dict.get("document_id", succ_id),
                title=succ_dict.get("title"),
                source=succ_dict.get("source", "SEBI"),
                category=succ_dict.get("category") or succ_meta.get("category"),
                document_type=succ_dict.get("document_type") or succ_meta.get("document_type"),
                circular_number=succ_dict.get("circular_number") or succ_meta.get("circular_number"),
                published_date=succ_dict.get("published_date") or succ_meta.get("published_date"),
                effective_date=succ_dict.get("effective_date") or succ_meta.get("effective_date"),
                status=succ_dict.get("status") or succ_meta.get("status", "CURRENT"),
                url=succ_dict.get("url", "")
            )

    doc_meta = doc_dict.get("metadata", {})
    return DocumentVersionResponse(
        document_id=document_id,
        title=doc_dict.get("title"),
        status=timeline_data.get("status", "UNKNOWN"),
        document_version=doc_dict.get("document_version") or doc_meta.get("document_version", "1.0"),
        supersedes=pred_doc.document_id if pred_doc else None,
        superseded_by=succ_doc.document_id if succ_doc else None,
        predecessor=pred_doc,
        successor=succ_doc,
        predecessor_candidates=[ev.document_id for ev in events_out if ev.document_id != document_id],
        relationship_type=raw_rels[0].get("relationship_type") if raw_rels else "UNKNOWN",
        relationship_confidence=raw_rels[0].get("confidence") if raw_rels else "LOW",
        has_reliable_predecessor=timeline_data.get("has_reliable_predecessor", False),
        chronology_uncertain=timeline_data.get("chronology_uncertain", False),
        timeline=events_out,
        events=events_out,
        relationships=rels_out
    )


@router.get("/document/{document_id}/relationships", response_model=List[DocumentRelationshipResponse], summary="Get Document Relationships")
def get_document_relationships_endpoint(document_id: str) -> List[DocumentRelationshipResponse]:
    """
    Returns explicit and inferred relationships (amendments, supersessions, corrigenda, references) for a document (Phase 58.11).
    """
    from app.versioning.timeline import get_document_relationships
    from app.schemas.responses import DocumentRelationshipResponse

    doc_dict = _load_doc_from_local_or_mongo(document_id)
    if not doc_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regulatory document with ID '{document_id}' not found."
        )

    rels = get_document_relationships(document_id)
    return [
        DocumentRelationshipResponse(
            source_document_id=r.get("source_document_id", ""),
            target_document_id=r.get("target_document_id", ""),
            relationship_type=r.get("relationship_type", "RELATED_TO"),
            confidence=r.get("confidence", "LOW"),
            evidence=r.get("evidence"),
            is_explicit=r.get("is_explicit", False)
        )
        for r in rels
    ]


@router.get("/latest", response_model=List[DocumentMetadataResponse], summary="List Latest Regulatory Documents")
def get_latest_documents(
    source: Optional[str] = Query(default=None, description="Filter by regulatory authority e.g. SEBI"),
    category: Optional[str] = Query(default=None, description="Filter by category e.g. Investment Adviser"),
    limit: int = Query(default=10, ge=1, le=50, description="Max documents to return")
) -> List[DocumentMetadataResponse]:
    """
    Returns recently published regulatory documents sorted by published_date descending.
    """
    all_docs_by_id: dict = {}

    # 1. Fetch from MongoDB first
    try:
        repo = get_doc_repo()
        mongo_docs = repo.list_documents(source=source, category=category, limit=max(limit * 2, 50))
        for d in mongo_docs:
            doc_id = d.get("document_id")
            if doc_id:
                all_docs_by_id[doc_id] = d
    except Exception as e:
        logger.warning(f"Error querying MongoDB in get_latest_documents: {e}")

    # 2. Check local processed directory as fallback/supplement
    if settings.processed_data_dir.exists():
        for f in settings.processed_data_dir.glob("*.json"):
            if f.name.endswith("_chunks.json"):
                continue
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    doc = json.load(jf)
                    if isinstance(doc, dict) and "document_id" in doc:
                        doc_id = doc.get("document_id")
                        if doc_id and doc_id not in all_docs_by_id:
                            all_docs_by_id[doc_id] = doc
            except Exception:
                continue

    # Filter
    filtered: List[dict] = []
    clean_source = source.strip() if source and source.strip() and source.strip() != "All" else None
    clean_cat = category.strip() if category and category.strip() and category.strip() != "All" else None

    for d in all_docs_by_id.values():
        meta = d.get("metadata", {})
        d_src = d.get("source") or meta.get("source", "SEBI")
        d_cat = d.get("category") or meta.get("category", "")

        if clean_source and d_src.upper() != clean_source.upper():
            continue
        if clean_cat and clean_cat.lower() not in (d_cat or "").lower():
            continue
        filtered.append(d)

    # Sort descending by published_date (fallback scraped_at)
    filtered.sort(
        key=lambda x: (
            str(x.get("published_date") or x.get("metadata", {}).get("published_date") or "1970-01-01"),
            str(x.get("scraped_at", ""))
        ),
        reverse=True
    )

    out: List[DocumentMetadataResponse] = []
    for d in filtered[:limit]:
        meta = d.get("metadata", {})
        out.append(DocumentMetadataResponse(
            document_id=d.get("document_id", ""),
            title=d.get("title"),
            source=d.get("source", "SEBI"),
            category=d.get("category") or meta.get("category"),
            document_type=d.get("document_type") or meta.get("document_type"),
            circular_number=d.get("circular_number") or meta.get("circular_number"),
            published_date=d.get("published_date") or meta.get("published_date"),
            effective_date=d.get("effective_date") or meta.get("effective_date"),
            status=d.get("status") or meta.get("status", "unknown"),
            url=d.get("url", ""),
            supersedes=d.get("supersedes") or meta.get("supersedes"),
            superseded_by=d.get("superseded_by") or meta.get("superseded_by"),
            document_version=d.get("document_version") or meta.get("document_version", "1.0"),
            content_hash=d.get("content_hash") or meta.get("content_hash"),
            relationship_type=d.get("relationship_type") or meta.get("relationship_type"),
            relationship_confidence=d.get("relationship_confidence") or meta.get("relationship_confidence")
        ))

    return out
