"""
Regulatory Document Version Timeline 2.0 Service (Phase 58).

Provides evidence-grounded, multi-branch regulatory history and document lineage:
- Distinguishes relationship types: SUPERSEDES, AMENDS, CORRIGENDUM_OF, REPLACES, CLARIFIES, REFERENCES, RELATED_TO
- Follows strict relationship evidence priority:
    1. Explicit regulatory relationship
    2. Exact referenced document number
    3. High-confidence relationship
    4. Medium-confidence relationship
    5. Low-confidence candidate
- Sorts chronologically: primarily by effective_date when reliable, otherwise published_date
- Evaluates evidence-based status: CURRENT, HISTORICAL, NOT_YET_EFFECTIVE, UNKNOWN, SUPERSEDED
- Supports multi-branch lineages (base circulars amended by circulars or affected by corrigenda)
- Thread-safe caching with deterministic invalidation
"""

import re
import hashlib
import logging
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Literal
from pydantic import BaseModel, Field

from app.ingestion.version_tracker import VersionTracker

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# =========================================================================
# TIMELINE DATA MODELS
# =========================================================================

TimelineStatus = Literal["CURRENT", "HISTORICAL", "NOT_YET_EFFECTIVE", "UNKNOWN", "SUPERSEDED"]
TimelineRelationshipType = Literal[
    "SUPERSEDES", "AMENDS", "CORRIGENDUM_OF", "REPLACES", "CLARIFIES", "REFERENCES", "RELATED_TO", "TARGET"
]
ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]


class TimelineEvent(BaseModel):
    """Represents an atomic regulatory event in a document's evolutionary lineage."""
    document_id: str
    title: Optional[str] = None
    published_date: Optional[str] = None
    effective_date: Optional[str] = None
    status: str = "UNKNOWN"
    relationship_to_previous: str = "RELATED_TO"
    relationship_confidence: str = "LOW"
    evidence: Optional[str] = None
    is_branch: bool = False
    parent_document_id: Optional[str] = None
    chronology_uncertain: bool = False
    order: int = 0


class DocumentRelationshipItem(BaseModel):
    """Direct relationship edge between two regulatory documents."""
    source_document_id: str
    target_document_id: str
    relationship_type: str
    confidence: str = "LOW"
    evidence: Optional[str] = None
    is_explicit: bool = False


class DocumentTimeline(BaseModel):
    """Complete structured timeline report for a regulatory document."""
    document_id: str
    status: str = "UNKNOWN"
    document: Dict[str, Any] = Field(default_factory=dict)
    events: List[TimelineEvent] = Field(default_factory=list)
    relationships: List[DocumentRelationshipItem] = Field(default_factory=list)
    predecessor_id: Optional[str] = None
    has_reliable_predecessor: bool = False
    chronology_uncertain: bool = False
    cached: bool = False


# =========================================================================
# TIMELINE CACHE
# =========================================================================

class TimelineCache:
    """Thread-safe memory cache for document timelines."""

    def __init__(self, max_size: int = 200):
        self._cache: Dict[str, DocumentTimeline] = {}
        self._lock = threading.Lock()
        self._max_size = max_size

    def make_key(self, document_id: str, state_fingerprint: str) -> str:
        raw = f"{document_id}:{state_fingerprint}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[DocumentTimeline]:
        with self._lock:
            val = self._cache.get(key)
            if val is not None:
                copied = val.model_copy(deep=True)
                copied.cached = True
                return copied
            return None

    def set(self, key: str, timeline: DocumentTimeline) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size:
                oldest_k = next(iter(self._cache))
                del self._cache[oldest_k]
            self._cache[key] = timeline.model_copy(deep=True)

    def invalidate(self, document_id: str) -> None:
        with self._lock:
            keys_to_del = [k for k in self._cache if document_id in k or self._cache[k].document_id == document_id]
            for k in keys_to_del:
                del self._cache[k]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


_global_timeline_cache = TimelineCache()


def clear_timeline_cache() -> None:
    """Utility to clear global timeline cache."""
    _global_timeline_cache.clear()


# =========================================================================
# STATUS DETERMINATION LOGIC (58.7)
# =========================================================================

def determine_document_status(
    doc_data: Dict[str, Any],
    is_superseded: bool = False,
    current_date: Optional[str] = None
) -> str:
    """
    Evaluates evidence-based regulatory document status.
    Rules:
    - Explicit supersession: SUPERSEDED / HISTORICAL
    - Effective date in the future (relative to today): NOT_YET_EFFECTIVE
    - Known active document with no supersession and published in past: CURRENT (if explicit or verified)
    - No conclusive evidence: UNKNOWN
    Rule: Never assume newest == CURRENT without evidence.
    """
    if not doc_data:
        return "UNKNOWN"

    meta = doc_data.get("metadata", {}) if isinstance(doc_data.get("metadata"), dict) else {}
    ref_date = current_date or datetime.utcnow().strftime("%Y-%m-%d")

    # Rule 1: Explicitly superseded
    if is_superseded:
        return "SUPERSEDED"

    # Check superseded metadata
    if doc_data.get("superseded_by") or meta.get("superseded_by"):
        return "SUPERSEDED"

    # Rule 2: Future effective date check
    eff_date = doc_data.get("effective_date") or meta.get("effective_date")
    if eff_date and re.match(r"^\d{4}-\d{2}-\d{2}$", str(eff_date).strip()):
        if str(eff_date).strip() > ref_date:
            return "NOT_YET_EFFECTIVE"

    # Rule 3: Explicit status stated in source / metadata
    raw_status = (doc_data.get("status") or meta.get("status") or "").strip().upper()
    if raw_status in ("HISTORICAL", "SUPERSEDED"):
        return raw_status
    if raw_status == "CURRENT":
        return "CURRENT"

    # Rule 4: If marked as Master Circular or consolidated regulation, and not superseded
    doc_type = (doc_data.get("document_type") or meta.get("document_type") or "").lower()
    if "master" in doc_type and not is_superseded:
        return "CURRENT"

    # Default conservative rule: do NOT assume newest = CURRENT
    return "UNKNOWN"


# =========================================================================
# RELATIONSHIP PATTERN EXTRACTION (58.5, 58.9)
# =========================================================================

RELATIONSHIP_PATTERNS: List[Tuple[str, str, str]] = [
    # (regex_pattern, relationship_type, confidence)
    (r"supersedes\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "SUPERSEDES", "HIGH"),
    (r"in\s+supersession\s+of\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "SUPERSEDES", "HIGH"),
    (r"shall\s+replace\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "REPLACES", "HIGH"),
    (r"replaces\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "REPLACES", "HIGH"),
    (r"rescinds\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "SUPERSEDES", "HIGH"),
    (r"corrigendum\s+to\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "CORRIGENDUM_OF", "HIGH"),
    (r"corrigendum\s+dated\b", "CORRIGENDUM_OF", "HIGH"),
    (r"amends\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "AMENDS", "HIGH"),
    (r"amendment\s+to\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "AMENDS", "HIGH"),
    (r"in\s+clarification\s+of\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "CLARIFIES", "HIGH"),
    (r"clarifies\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "CLARIFIES", "HIGH"),
    (r"reference\s+is\s+drawn\s+to\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "REFERENCES", "MEDIUM"),
    (r"earlier\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)", "REFERENCES", "MEDIUM"),
]


def extract_explicit_relationships(content: str, source_doc_id: str) -> List[Dict[str, Any]]:
    """Scans content for explicit regulatory relationship references."""
    if not content:
        return []

    found: List[Dict[str, Any]] = []
    seen = set()

    for pat, rel_type, conf in RELATIONSHIP_PATTERNS:
        for m in re.finditer(pat, content, re.IGNORECASE):
            ref_id = m.group(1).strip().rstrip(".,;:") if m.groups() else ""
            key = (rel_type, ref_id)
            if key not in seen and (len(ref_id) >= 3 or not ref_id):
                seen.add(key)
                found.append({
                    "relationship_type": rel_type,
                    "target_ref": ref_id,
                    "confidence": conf,
                    "evidence": m.group(0).strip(),
                    "source_doc_id": source_doc_id
                })
    return found


# =========================================================================
# TIMELINE BUILDER SERVICE (58.4, 58.5, 58.6, 58.8)
# =========================================================================

class TimelineService:
    """Service to construct multi-branch chronological regulatory timelines."""

    def __init__(self, tracker: Optional[VersionTracker] = None, cache: Optional[TimelineCache] = None):
        self.tracker = tracker or VersionTracker()
        self.cache = cache or _global_timeline_cache

    def get_document_timeline(
        self,
        document_id: str,
        current_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Constructs a structured chronological timeline for a regulatory document.
        """
        if not document_id or not document_id.strip():
            return {
                "document_id": "",
                "status": "UNKNOWN",
                "document": {},
                "events": [],
                "relationships": [],
                "predecessor_id": None,
                "has_reliable_predecessor": False,
                "chronology_uncertain": False
            }

        clean_id = document_id.strip()

        # Load target document
        target_doc = self.tracker._get_document(clean_id)
        if not target_doc:
            return {
                "document_id": clean_id,
                "status": "UNKNOWN",
                "document": {},
                "events": [],
                "relationships": [],
                "predecessor_id": None,
                "has_reliable_predecessor": False,
                "chronology_uncertain": False
            }

        # Check Cache
        all_docs = self.tracker._load_all_documents()
        fingerprint = f"{len(all_docs)}:{target_doc.get('content_hash', '')}:{target_doc.get('status', '')}"
        cache_key = self.cache.make_key(clean_id, fingerprint)

        cached_val = self.cache.get(cache_key)
        if cached_val is not None:
            return cached_val.model_dump()

        target_meta = target_doc.get("metadata", {}) if isinstance(target_doc.get("metadata"), dict) else {}
        target_circ = target_doc.get("circular_number") or target_meta.get("circular_number")
        target_content = target_doc.get("content", "")

        # Build lookup table of all documents
        all_by_id = {d.get("document_id"): d for d in all_docs if d.get("document_id")}
        all_by_circ = {
            (d.get("circular_number") or d.get("metadata", {}).get("circular_number", "")).lower(): d
            for d in all_docs if (d.get("circular_number") or d.get("metadata", {}).get("circular_number"))
        }

        # 1. Discover explicit and inferred relationships
        relationships: List[DocumentRelationshipItem] = []
        is_target_superseded = False
        reliable_predecessor_id: Optional[str] = None

        # Check explicit relationships inside target doc text
        explicit_rels = extract_explicit_relationships(target_content, clean_id)
        for er in explicit_rels:
            ref_num = er.get("target_ref", "").lower()
            matched_doc = all_by_circ.get(ref_num)
            if matched_doc:
                target_matched_id = matched_doc.get("document_id")
                relationships.append(DocumentRelationshipItem(
                    source_document_id=clean_id,
                    target_document_id=target_matched_id,
                    relationship_type=er["relationship_type"],
                    confidence=er["confidence"],
                    evidence=er.get("evidence"),
                    is_explicit=True
                ))
                if er["relationship_type"] in ("SUPERSEDES", "REPLACES", "AMENDS"):
                    reliable_predecessor_id = target_matched_id

        # Check other documents that relate to target doc (supersede, amend, corrigendum)
        for other in all_docs:
            other_id = other.get("document_id")
            if not other_id or other_id == clean_id:
                continue

            other_meta = other.get("metadata", {}) if isinstance(other.get("metadata"), dict) else {}
            other_sup = other.get("supersedes") or other_meta.get("supersedes")
            other_amends = other.get("amends") or other_meta.get("amends")
            other_corrig = other.get("corrigendum_of") or other_meta.get("corrigendum_of")
            other_content = other.get("content", "")

            # Check metadata links
            if other_sup and (other_sup == clean_id or (target_circ and other_sup.lower() == target_circ.lower())):
                relationships.append(DocumentRelationshipItem(
                    source_document_id=other_id,
                    target_document_id=clean_id,
                    relationship_type="SUPERSEDES",
                    confidence="HIGH",
                    evidence=f"Document {other_id} explicitly declares supersession of target",
                    is_explicit=True
                ))
                is_target_superseded = True

            elif other_amends and (other_amends == clean_id or (target_circ and other_amends.lower() == target_circ.lower())):
                relationships.append(DocumentRelationshipItem(
                    source_document_id=other_id,
                    target_document_id=clean_id,
                    relationship_type="AMENDS",
                    confidence="HIGH",
                    evidence=f"Document {other_id} explicitly amends target",
                    is_explicit=True
                ))

            elif other_corrig and (other_corrig == clean_id or (target_circ and other_corrig.lower() == target_circ.lower())):
                relationships.append(DocumentRelationshipItem(
                    source_document_id=other_id,
                    target_document_id=clean_id,
                    relationship_type="CORRIGENDUM_OF",
                    confidence="HIGH",
                    evidence=f"Document {other_id} is a corrigendum of target",
                    is_explicit=True
                ))

            else:
                # Check other document's textual explicit references to target circular
                if target_circ:
                    other_explicit = extract_explicit_relationships(other_content, other_id)
                    for oe in other_explicit:
                        oe_ref = oe.get("target_ref", "").lower()
                        if oe_ref and (oe_ref in target_circ.lower() or target_circ.lower() in oe_ref):
                            relationships.append(DocumentRelationshipItem(
                                source_document_id=other_id,
                                target_document_id=clean_id,
                                relationship_type=oe["relationship_type"],
                                confidence=oe["confidence"],
                                evidence=oe.get("evidence"),
                                is_explicit=True
                            ))
                            if oe["relationship_type"] in ("SUPERSEDES", "REPLACES"):
                                is_target_superseded = True

        # Fallback to predecessor candidates from VersionTracker if no explicit predecessor
        if not reliable_predecessor_id:
            resolved = self.tracker.resolve_document_relationships(clean_id)
            cand_pred = resolved.get("predecessor_id")
            conf = (resolved.get("relationship_confidence") or "low").upper()
            if cand_pred and conf in ("HIGH", "MEDIUM"):
                reliable_predecessor_id = cand_pred
                relationships.append(DocumentRelationshipItem(
                    source_document_id=clean_id,
                    target_document_id=cand_pred,
                    relationship_type=resolved.get("relationship_type", "RELATED_TO"),
                    confidence=conf,
                    evidence="Determined by taxonomy and circular reference matching",
                    is_explicit=False
                ))

        # Determine target status
        target_status = determine_document_status(target_doc, is_superseded=is_target_superseded, current_date=current_date)

        # 2. Assemble Timeline Events (Multi-Branch, 58.8)
        connected_ids = {clean_id}
        for r in relationships:
            connected_ids.add(r.source_document_id)
            connected_ids.add(r.target_document_id)

        events: List[TimelineEvent] = []
        chronology_uncertain = False

        for cid in connected_ids:
            cdoc = all_by_id.get(cid)
            if not cdoc:
                continue

            cmeta = cdoc.get("metadata", {}) if isinstance(cdoc.get("metadata"), dict) else {}
            pub_date = cdoc.get("published_date") or cmeta.get("published_date")
            eff_date = cdoc.get("effective_date") or cmeta.get("effective_date")

            if not pub_date and not eff_date:
                chronology_uncertain = True

            # Determine relationship to target
            if cid == clean_id:
                rel_to_prev = "TARGET"
                rel_conf = "HIGH"
                is_br = False
                p_id = reliable_predecessor_id
                c_status = target_status
                ev_str = None
            else:
                direct_edge = next((r for r in relationships if r.source_document_id == cid and r.target_document_id == clean_id), None)
                reverse_edge = next((r for r in relationships if r.source_document_id == clean_id and r.target_document_id == cid), None)

                if direct_edge:
                    rel_to_prev = direct_edge.relationship_type
                    rel_conf = direct_edge.confidence
                    is_br = direct_edge.relationship_type in ("AMENDS", "CORRIGENDUM_OF", "CLARIFIES", "REFERENCES")
                    p_id = clean_id
                    ev_str = direct_edge.evidence
                elif reverse_edge:
                    rel_to_prev = reverse_edge.relationship_type
                    rel_conf = reverse_edge.confidence
                    is_br = False
                    p_id = cid
                    ev_str = reverse_edge.evidence
                else:
                    rel_to_prev = "RELATED_TO"
                    rel_conf = "LOW"
                    is_br = True
                    p_id = clean_id
                    ev_str = "Taxonomy category overlap"

                # Status for connected doc
                c_is_sup = any(r.target_document_id == cid and r.relationship_type in ("SUPERSEDES", "REPLACES") for r in relationships)
                c_status = determine_document_status(cdoc, is_superseded=c_is_sup, current_date=current_date)

            events.append(TimelineEvent(
                document_id=cid,
                title=cdoc.get("title") or "Regulatory Notice",
                published_date=pub_date,
                effective_date=eff_date,
                status=c_status,
                relationship_to_previous=rel_to_prev,
                relationship_confidence=rel_conf,
                evidence=ev_str,
                is_branch=is_br,
                parent_document_id=p_id,
                chronology_uncertain=(not pub_date and not eff_date)
            ))

        # 3. Chronological Order (58.6)
        # Sort primarily by effective_date when reliable, otherwise published_date
        def _sort_key(ev: TimelineEvent) -> Tuple[int, str]:
            if ev.effective_date and re.match(r"^\d{4}-\d{2}-\d{2}$", str(ev.effective_date)):
                return (0, str(ev.effective_date))
            if ev.published_date and re.match(r"^\d{4}-\d{2}-\d{2}$", str(ev.published_date)):
                return (1, str(ev.published_date))
            return (2, "9999-99-99")

        events.sort(key=_sort_key)
        for idx, ev in enumerate(events, start=1):
            ev.order = idx

        timeline_result = DocumentTimeline(
            document_id=clean_id,
            status=target_status,
            document={
                "document_id": clean_id,
                "title": target_doc.get("title"),
                "source": target_doc.get("source", "SEBI"),
                "category": target_doc.get("category") or target_meta.get("category"),
                "document_type": target_doc.get("document_type") or target_meta.get("document_type"),
                "circular_number": target_circ,
                "published_date": target_doc.get("published_date") or target_meta.get("published_date"),
                "effective_date": target_doc.get("effective_date") or target_meta.get("effective_date"),
                "status": target_status,
                "content_hash": target_doc.get("content_hash") or target_meta.get("content_hash"),
                "url": target_doc.get("url", "")
            },
            events=events,
            relationships=relationships,
            predecessor_id=reliable_predecessor_id,
            has_reliable_predecessor=(reliable_predecessor_id is not None),
            chronology_uncertain=chronology_uncertain,
            cached=False
        )

        self.cache.set(cache_key, timeline_result)
        return timeline_result.model_dump()

    def get_document_relationships(self, document_id: str) -> List[Dict[str, Any]]:
        """Returns direct relationships (amendments, supersessions, corrigenda, references)."""
        timeline = self.get_document_timeline(document_id)
        return timeline.get("relationships", [])


# Singleton instance
_timeline_service = TimelineService()


def get_timeline_service() -> TimelineService:
    """Returns the singleton TimelineService instance."""
    return _timeline_service


def get_document_timeline(document_id: str, tracker: Optional[VersionTracker] = None, current_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Public entry point for retrieving regulatory document timeline (Phase 58.4).
    """
    if tracker is not None:
        srv = TimelineService(tracker=tracker)
        return srv.get_document_timeline(document_id, current_date=current_date)
    return _timeline_service.get_document_timeline(document_id, current_date=current_date)


def get_document_relationships(document_id: str, tracker: Optional[VersionTracker] = None) -> List[Dict[str, Any]]:
    """
    Public entry point for retrieving regulatory document relationships (Phase 58.11).
    """
    if tracker is not None:
        srv = TimelineService(tracker=tracker)
        return srv.get_document_relationships(document_id)
    return _timeline_service.get_document_relationships(document_id)
