"""
Document and Version Management API Routes for RegIntel FastAPI.
"""

import json
import logging
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.responses import DocumentMetadataResponse, DocumentVersionResponse
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


@router.get("/document/{document_id}/versions", response_model=DocumentVersionResponse, summary="Get Version Relationships")
def get_document_versions(document_id: str) -> DocumentVersionResponse:
    """
    Returns explicit version relationships, predecessor, successor, related documents, and chronological timeline.
    """
    from app.ingestion.version_tracker import VersionTracker
    from app.schemas.responses import TimelineNodeResponse

    doc_dict = _load_doc_from_local_or_mongo(document_id)
    if not doc_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regulatory document with ID '{document_id}' not found."
        )

    tracker = VersionTracker()
    version_info = tracker.get_document_versions(document_id)

    pred_doc = None
    if version_info.get("predecessor"):
        pred_dict = version_info["predecessor"]
        pred_meta = pred_dict.get("metadata", {})
        pred_doc = DocumentMetadataResponse(
            document_id=pred_dict.get("document_id", ""),
            title=pred_dict.get("title"),
            source=pred_dict.get("source", "SEBI"),
            category=pred_dict.get("category") or pred_meta.get("category"),
            document_type=pred_dict.get("document_type") or pred_meta.get("document_type"),
            circular_number=pred_dict.get("circular_number") or pred_meta.get("circular_number"),
            published_date=pred_dict.get("published_date") or pred_meta.get("published_date"),
            effective_date=pred_dict.get("effective_date") or pred_meta.get("effective_date"),
            status=pred_dict.get("status") or pred_meta.get("status", "historical"),
            url=pred_dict.get("url", "")
        )

    succ_doc = None
    if version_info.get("successor"):
        succ_dict = version_info["successor"]
        succ_meta = succ_dict.get("metadata", {})
        succ_doc = DocumentMetadataResponse(
            document_id=succ_dict.get("document_id", ""),
            title=succ_dict.get("title"),
            source=succ_dict.get("source", "SEBI"),
            category=succ_dict.get("category") or succ_meta.get("category"),
            document_type=succ_dict.get("document_type") or succ_meta.get("document_type"),
            circular_number=succ_dict.get("circular_number") or succ_meta.get("circular_number"),
            published_date=succ_dict.get("published_date") or succ_meta.get("published_date"),
            effective_date=succ_dict.get("effective_date") or succ_meta.get("effective_date"),
            status=succ_dict.get("status") or succ_meta.get("status", "current"),
            url=succ_dict.get("url", "")
        )

    timeline_nodes: List[TimelineNodeResponse] = [
        TimelineNodeResponse(
            document_id=n.get("document_id", ""),
            title=n.get("title"),
            published_date=n.get("published_date"),
            status=n.get("status", "unknown"),
            relationship=n.get("relationship", "related")
        )
        for n in version_info.get("timeline", [])
    ]

    return DocumentVersionResponse(
        document_id=document_id,
        title=doc_dict.get("title"),
        status=version_info.get("status", "unknown"),
        document_version=version_info.get("document_version", "1.0"),
        supersedes=pred_doc.document_id if pred_doc else None,
        superseded_by=succ_doc.document_id if succ_doc else None,
        predecessor=pred_doc,
        successor=succ_doc,
        predecessor_candidates=[d.get("document_id") for d in version_info.get("related_documents", []) if d.get("document_id")],
        relationship_type=version_info.get("relationship_type"),
        relationship_confidence=version_info.get("relationship_confidence"),
        timeline=timeline_nodes
    )


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
