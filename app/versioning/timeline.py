"""
Timeline Service for Regulatory Document Lineage and Evolution (Phase 47).
"""

from typing import Dict, Any, List, Optional
from app.ingestion.version_tracker import VersionTracker


def get_document_timeline(document_id: str, tracker: Optional[VersionTracker] = None) -> Dict[str, Any]:
    """
    Constructs a structured chronological timeline for a regulatory document.
    """
    v_tracker = tracker or VersionTracker()
    v_info = v_tracker.get_document_versions(document_id)

    raw_timeline = v_info.get("timeline", [])
    rel_conf = v_info.get("relationship_confidence", "low").upper()
    rel_type = v_info.get("relationship_type", "RELATED")

    events: List[Dict[str, Any]] = []
    for node in raw_timeline:
        n_id = node.get("document_id", "")
        doc_data = v_tracker._get_document(n_id) if n_id else {}
        meta = doc_data.get("metadata", {}) if doc_data else {}

        node_rel = "TARGET" if n_id == document_id else (
            rel_type if node.get("relationship") == "predecessor" else "SUPERSEDED_BY"
        )

        events.append({
            "document_id": n_id,
            "title": node.get("title") or (doc_data.get("title") if doc_data else "Regulatory Notice"),
            "published_date": node.get("published_date") or doc_data.get("published_date") or meta.get("published_date"),
            "effective_date": doc_data.get("effective_date") or meta.get("effective_date"),
            "status": node.get("status", "unknown").upper(),
            "relationship": node_rel,
            "relationship_confidence": rel_conf
        })

    # Sort chronologically if published_date is available
    events.sort(key=lambda x: str(x.get("published_date") or "1970-01-01"))

    return {
        "document_id": document_id,
        "events": events
    }
