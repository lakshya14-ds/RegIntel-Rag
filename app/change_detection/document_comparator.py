"""
Document Comparison Service and Engine for Direct Regulatory Document Diffing.

Provides structured, evidence-grounded comparison between two regulatory documents:
- Validates documents and content presence before processing
- Resolves chronological order (Older vs. Newer) with confidence scoring
- Aligns sections via 4-tier structural matching (Section Number > Heading > Fuzzy > Content)
- Classifies changes into ADDED, REMOVED, MODIFIED, and UNCHANGED
- Distinguishes superficial formatting differences from substantive regulatory changes
- Invokes Gemini only for candidate modified sections requiring semantic analysis
- Provides strict evidence mapping (old_source, new_source) for every change
- Maintains deterministic content-hash caching for instant repeated queries
"""

import sys
import json
import hashlib
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Literal
from pydantic import BaseModel, Field

from app.config import settings
from app.ingestion.models import RegulatoryDocument, from_mongo
from app.change_detection.normalizer import (
    normalize_regulatory_text,
    normalize_heading,
    are_texts_substantively_equal
)
from app.change_detection.section_matcher import (
    SectionMatcher,
    ExtractedSection,
    MatchedSectionPair
)
from app.change_detection.prompts import (
    build_structured_comparison_prompt,
    build_section_comparison_prompt
)

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# =========================================================================
# DATA MODELS
# =========================================================================

class EvidenceSource(BaseModel):
    """Source reference for evidence backing a regulatory change."""
    document_id: str
    section_id: str
    heading: str
    section_number: Optional[str] = None
    url: Optional[str] = None
    published_date: Optional[str] = None


class DetailedSectionChange(BaseModel):
    """Detailed change description for a single regulatory section."""
    section: str
    heading: str
    change_type: Literal["ADDED", "REMOVED", "MODIFIED", "UNCHANGED"]
    substantive_change: bool = False
    modification_category: Optional[str] = None
    matching_method: Optional[str] = None
    matching_confidence: Optional[str] = None
    previous_text: Optional[str] = None
    current_text: Optional[str] = None
    summary: Optional[str] = None
    old_requirement: Optional[str] = None
    new_requirement: Optional[str] = None
    impact: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    old_source: Optional[EvidenceSource] = None
    new_source: Optional[EvidenceSource] = None


class ComparisonReport(BaseModel):
    """Comprehensive, structured regulatory comparison report."""
    status: str = Field(default="SUCCESS")  # SUCCESS, ERROR, NO_RELIABLE_PREDECESSOR
    message: Optional[str] = None
    older_document: Dict[str, Any] = Field(default_factory=dict)
    newer_document: Dict[str, Any] = Field(default_factory=dict)
    document_order_confidence: str = "unknown"  # high, medium, low, unknown
    version_relationship: str = "UNKNOWN"       # SUPERSEDES, SUPERSEDED, UPDATE, RELATED, NEW, UNKNOWN
    relationship_confidence: str = "unknown"   # high, medium, low, unknown
    match_reason: Optional[str] = None
    summary_counts: Dict[str, int] = Field(default_factory=lambda: {"added": 0, "removed": 0, "modified": 0, "unchanged": 0})
    executive_summary: str = ""
    key_changes: List[str] = Field(default_factory=list)
    changes: List[DetailedSectionChange] = Field(default_factory=list)
    statistics: Dict[str, int] = Field(default_factory=lambda: {
        "older_sections": 0,
        "newer_sections": 0,
        "added": 0,
        "removed": 0,
        "modified": 0,
        "unchanged": 0
    })
    cached: bool = False

    # Backward compatibility properties for Phase 24 callers
    @property
    def total_sections_compared(self) -> int:
        return sum(self.summary_counts.values())

    @property
    def added_count(self) -> int:
        return self.summary_counts.get("added", 0)

    @property
    def removed_count(self) -> int:
        return self.summary_counts.get("removed", 0)

    @property
    def modified_count(self) -> int:
        return self.summary_counts.get("modified", 0)

    @property
    def unchanged_count(self) -> int:
        return self.summary_counts.get("unchanged", 0)

    def print_formatted(self):
        """Prints formatted terminal representation of comparison report."""
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"

        def _safe(t: Any) -> str:
            return str(t).encode(encoding, errors="replace").decode(encoding)

        print("\n" + "=" * 75)
        print("REGINTEL REGULATORY COMPARISON REPORT")
        print("=" * 75)

        if self.status != "SUCCESS":
            print(f"Status  : {self.status}")
            print(f"Message : {_safe(self.message or 'No details.')}\n")
            return

        old_title = self.older_document.get("title", "Untitled Older")
        new_title = self.newer_document.get("title", "Untitled Newer")
        old_date = self.older_document.get("published_date", "N/A")
        new_date = self.newer_document.get("published_date", "N/A")

        print(f"Older Document  : {_safe(old_title)} (Date: {old_date})")
        print(f"Newer Document  : {_safe(new_title)} (Date: {new_date})")
        print(f"Chronology Conf : {self.document_order_confidence.upper()}")
        print(f"Relationship    : {self.version_relationship} (Confidence: {self.relationship_confidence.upper()})")
        if self.cached:
            print("Cache Status    : HIT (Reused cached comparison)")

        print("\n" + "-" * 75)
        print("EXECUTIVE SUMMARY OF KEY CHANGES")
        print("-" * 75)
        print(_safe(self.executive_summary))

        print("\n" + "-" * 75)
        stats = self.statistics
        print(f"STATISTICS: Older Sections: {stats.get('older_sections')} | Newer Sections: {stats.get('newer_sections')} | Added: {stats.get('added')} | Modified: {stats.get('modified')} | Removed: {stats.get('removed')} | Unchanged: {stats.get('unchanged')}")
        print("-" * 75)

        for idx, ch in enumerate(self.changes, start=1):
            if ch.change_type == "UNCHANGED":
                continue
            badge = f"[{ch.change_type}]"
            subcat = f"({ch.modification_category.upper()})" if ch.modification_category else ""
            print(f"\n{idx}. {badge} {subcat} {_safe(ch.heading)}")
            if ch.summary:
                print(f"   Summary   : {_safe(ch.summary)}")
            if ch.impact:
                print(f"   Impact    : {_safe(ch.impact)}")
            if ch.old_requirement and ch.old_requirement != "N/A":
                print(f"   Previous  : {_safe(ch.old_requirement)}")
            if ch.new_requirement and ch.new_requirement != "N/A":
                print(f"   Current   : {_safe(ch.new_requirement)}")
            if ch.evidence:
                print(f"   Evidence  : {ch.evidence}")

        print("\n" + "=" * 75 + "\n")


# =========================================================================
# THREAD-SAFE IN-MEMORY COMPARISON CACHE
# =========================================================================

class ComparisonCache:
    """Thread-safe in-memory cache for comparison reports keyed by document content hashes."""

    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, ComparisonReport] = {}
        self._lock = threading.Lock()
        self._max_size = max_size

    def make_key(self, doc_a_id: str, doc_b_id: str, hash_a: str, hash_b: str) -> str:
        """Generates deterministic cache key from document IDs and content hashes."""
        sorted_pairs = sorted([(doc_a_id, hash_a), (doc_b_id, hash_b)])
        raw_key = f"{sorted_pairs[0][0]}:{sorted_pairs[0][1]}|{sorted_pairs[1][0]}:{sorted_pairs[1][1]}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[ComparisonReport]:
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, report: ComparisonReport) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Remove oldest entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            self._cache[key] = report

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


# Global comparison cache instance
_global_comparison_cache = ComparisonCache()


# =========================================================================
# DOCUMENT COMPARATOR SERVICE
# =========================================================================

class DocumentComparator:
    """
    Core Regulatory Document Comparison Engine (Phases 39–41).
    """

    def __init__(
        self,
        processed_data_dir: Optional[Path] = None,
        generator_client: Optional[Any] = None,
        cache: Optional[ComparisonCache] = None
    ):
        self.processed_dir = processed_data_dir or settings.processed_data_dir
        self._generator_client = generator_client
        self._cache = cache or _global_comparison_cache

    def _get_generator(self) -> Optional[Any]:
        """Lazy-loads existing Google Gemini client."""
        if self._generator_client is not None:
            return self._generator_client
        try:
            from google import genai
            api_key = getattr(settings, "effective_gemini_key", None) or getattr(settings, "gemini_api_key", None)
            if api_key:
                self._generator_client = genai.Client(api_key=api_key)
                return self._generator_client
        except Exception as e:
            logger.warning(f"Could not initialize Gemini Client for document comparison: {e}")
        return None

    def load_document(self, document_id: str) -> Optional[RegulatoryDocument]:
        """Loads a single processed regulatory document by ID from MongoDB or local store."""
        if not document_id or not document_id.strip():
            return None

        clean_id = document_id.strip()

        # 1. Try local processed files
        candidates = [
            self.processed_dir / f"{clean_id}.json",
            self.processed_dir / f"sebi_{clean_id}.json"
        ]
        for c in candidates:
            if c.exists():
                try:
                    with open(c, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return from_mongo(RegulatoryDocument, data)
                except Exception as e:
                    logger.warning(f"Failed to parse {c}: {e}")

        # 2. Try glob search in processed directory
        if self.processed_dir.exists():
            for f in self.processed_dir.glob("*.json"):
                if f.name.endswith("_chunks.json"):
                    continue
                if clean_id in f.name:
                    try:
                        with open(f, "r", encoding="utf-8") as jf:
                            data = json.load(jf)
                        if data.get("document_id") == clean_id:
                            return from_mongo(RegulatoryDocument, data)
                    except Exception:
                        continue

        # 3. Fallback to MongoDB repository
        try:
            from app.ingestion.repository import DocumentRepository
            repo = DocumentRepository()
            doc_model = repo.get_document(clean_id)
            if doc_model:
                return doc_model
        except Exception:
            pass

        return None

    def determine_chronology(
        self,
        doc_a: RegulatoryDocument,
        doc_b: RegulatoryDocument
    ) -> Tuple[RegulatoryDocument, RegulatoryDocument, str]:
        """
        Determines which document is older vs. newer with confidence scoring.
        Returns: (older_doc, newer_doc, confidence) where confidence is 'high', 'medium', 'low', 'unknown'.
        """
        date_a = doc_a.published_date or (doc_a.metadata.published_date if doc_a.metadata else None)
        date_b = doc_b.published_date or (doc_b.metadata.published_date if doc_b.metadata else None)

        # 1. Publication date comparison (High confidence if valid distinct dates)
        if date_a and date_b and date_a != date_b:
            try:
                if date_a < date_b:
                    return doc_a, doc_b, "high"
                else:
                    return doc_b, doc_a, "high"
            except Exception:
                pass

        # 2. Effective date comparison
        eff_a = doc_a.effective_date or (doc_a.metadata.effective_date if doc_a.metadata else None)
        eff_b = doc_b.effective_date or (doc_b.metadata.effective_date if doc_b.metadata else None)
        if eff_a and eff_b and eff_a != eff_b:
            if eff_a < eff_b:
                return doc_a, doc_b, "high"
            else:
                return doc_b, doc_a, "high"

        # 3. Document type / version metadata heuristic (Medium confidence)
        type_a = (doc_a.document_type or "").lower()
        type_b = (doc_b.document_type or "").lower()

        # If one is Master Circular and other is Circular, Master Circular is often newer
        if "master" in type_b and "master" not in type_a:
            return doc_a, doc_b, "medium"
        if "master" in type_a and "master" not in type_b:
            return doc_b, doc_a, "medium"

        # 4. Explicit supersedes reference in doc_b content pointing to doc_a
        from app.ingestion.version_tracker import VersionTracker
        vt = VersionTracker()
        supersedes_ref = vt.detect_explicit_supersession(doc_b.content)
        if supersedes_ref:
            return doc_a, doc_b, "high"

        # 5. Default fallback: treat Document A as older with unknown/low confidence
        return doc_a, doc_b, "unknown"

    def determine_version_relationship(
        self,
        older_doc: RegulatoryDocument,
        newer_doc: RegulatoryDocument
    ) -> Tuple[str, str, Optional[str]]:
        """
        Determines the regulatory relationship type and confidence between two documents.
        Returns: (relationship_type, relationship_confidence, match_reason)
        """
        from app.ingestion.version_tracker import VersionTracker
        vt = VersionTracker()

        # Priority 1: Explicit supersession text in newer document
        ref = vt.detect_explicit_supersession(newer_doc.content)
        if ref:
            circ_a = older_doc.circular_number or (older_doc.metadata.circular_number if older_doc.metadata else "")
            if circ_a and (ref.lower() in circ_a.lower() or circ_a.lower() in ref.lower()):
                return "SUPERSEDES", "high", f"Newer circular explicitly supersedes circular {ref}"
            return "SUPERSEDES", "high", f"Newer circular contains explicit supersession clause referencing {ref}"

        # Priority 2: Same category and high title similarity
        cat_old = (older_doc.category or (older_doc.metadata.category if older_doc.metadata else "")).lower()
        cat_new = (newer_doc.category or (newer_doc.metadata.category if newer_doc.metadata else "")).lower()

        from app.change_detection.document_matcher import compute_title_similarity
        sim = compute_title_similarity(older_doc.title, newer_doc.title)

        if cat_old and cat_new and cat_old == cat_new and sim >= 0.65:
            return "UPDATE", "medium", f"Shared category '{older_doc.category}' with {sim*100:.0f}% title similarity"

        if sim >= 0.75:
            return "UPDATE", "medium", f"High title similarity ({sim*100:.0f}%) across document versions"

        if cat_old and cat_new and cat_old == cat_new:
            return "RELATED", "low", f"Shared regulatory category '{older_doc.category}'"

        return "UNKNOWN", "unknown", "No explicit supersession or strong taxonomy linkage detected"

    def compare_documents(
        self,
        document_a_id: str,
        document_b_id: str,
        generate_summaries: bool = True
    ) -> ComparisonReport:
        """
        Compares two regulatory documents by ID and returns a structured ComparisonReport.
        """
        # 1. Validation
        if not document_a_id or not document_a_id.strip():
            return ComparisonReport(status="ERROR", message="Document A ID must be provided.")
        if not document_b_id or not document_b_id.strip():
            return ComparisonReport(status="ERROR", message="Document B ID must be provided.")

        doc_a = self.load_document(document_a_id)
        if not doc_a:
            return ComparisonReport(
                status="ERROR",
                message=f"Document A with ID '{document_a_id}' was not found in the corpus."
            )

        doc_b = self.load_document(document_b_id)
        if not doc_b:
            return ComparisonReport(
                status="ERROR",
                message=f"Document B with ID '{document_b_id}' was not found in the corpus."
            )

        if not doc_a.content or not doc_a.content.strip():
            return ComparisonReport(
                status="ERROR",
                message=f"Document A ('{doc_a.title}') has no usable textual content."
            )

        if not doc_b.content or not doc_b.content.strip():
            return ComparisonReport(
                status="ERROR",
                message=f"Document B ('{doc_b.title}') has no usable textual content."
            )

        # 2. Chronology Determination
        older_doc, newer_doc, order_conf = self.determine_chronology(doc_a, doc_b)

        # 3. Cache Check (Deterministic key based on IDs and content hashes)
        hash_old = older_doc.content_hash or hashlib.sha256(older_doc.content.encode("utf-8")).hexdigest()
        hash_new = newer_doc.content_hash or hashlib.sha256(newer_doc.content.encode("utf-8")).hexdigest()
        cache_key = self._cache.make_key(older_doc.document_id, newer_doc.document_id, hash_old, hash_new)

        cached_report = self._cache.get(cache_key)
        if cached_report is not None:
            logger.info(f"Comparison cache hit for key {cache_key[:12]}")
            # Return copy with cached=True
            res = cached_report.model_copy(deep=True)
            res.cached = True
            return res

        # 4. Version Relationship Determination
        rel_type, rel_conf, match_reason = self.determine_version_relationship(older_doc, newer_doc)

        # 5. Section Extraction
        older_sections = SectionMatcher.extract_sections(older_doc.content, document_id=older_doc.document_id)
        newer_sections = SectionMatcher.extract_sections(newer_doc.content, document_id=newer_doc.document_id)

        # 6. Section Matching (4-Tier)
        matched_pairs: List[MatchedSectionPair] = SectionMatcher.match_sections(older_sections, newer_sections)

        # 7. Section Difference Analysis & Delta Classification
        changes: List[DetailedSectionChange] = []
        counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}

        client = self._get_generator() if generate_summaries else None

        for pair in matched_pairs:
            change_obj = self._analyze_section_pair(
                pair=pair,
                older_doc=older_doc,
                newer_doc=newer_doc,
                client=client
            )
            changes.append(change_obj)
            c_type = change_obj.change_type.lower()
            if c_type in counts:
                counts[c_type] += 1

        # 8. Deterministic Executive Key Changes Generation
        key_changes = self._generate_key_changes(changes)
        executive_summary = self._compose_executive_summary(
            older_doc=older_doc,
            newer_doc=newer_doc,
            counts=counts,
            key_changes=key_changes,
            rel_type=rel_type,
            order_conf=order_conf
        )

        # Prepare Document Metadata Dictionaries
        def _doc_meta(d: RegulatoryDocument) -> Dict[str, Any]:
            meta = d.metadata.model_dump() if d.metadata else {}
            return {
                "document_id": d.document_id,
                "title": d.title,
                "source": d.source or "SEBI",
                "category": d.category or meta.get("category"),
                "document_type": d.document_type or meta.get("document_type"),
                "circular_number": d.circular_number or meta.get("circular_number"),
                "published_date": d.published_date or meta.get("published_date"),
                "effective_date": d.effective_date or meta.get("effective_date"),
                "status": d.status or meta.get("status", "unknown"),
                "url": d.url or "",
                "content_hash": d.content_hash or meta.get("content_hash")
            }

        report = ComparisonReport(
            status="SUCCESS",
            older_document=_doc_meta(older_doc),
            newer_document=_doc_meta(newer_doc),
            document_order_confidence=order_conf,
            version_relationship=rel_type,
            relationship_confidence=rel_conf,
            match_reason=match_reason,
            summary_counts=counts,
            executive_summary=executive_summary,
            key_changes=key_changes,
            changes=changes,
            statistics={
                "older_sections": len(older_sections),
                "newer_sections": len(newer_sections),
                "added": counts["added"],
                "removed": counts["removed"],
                "modified": counts["modified"],
                "unchanged": counts["unchanged"]
            },
            cached=False
        )

        # Store in cache
        self._cache.set(cache_key, report)
        return report

    def _analyze_section_pair(
        self,
        pair: MatchedSectionPair,
        older_doc: RegulatoryDocument,
        newer_doc: RegulatoryDocument,
        client: Optional[Any]
    ) -> DetailedSectionChange:
        """
        Analyzes a single aligned pair of sections, categorizes deltas,
        and optionally invokes Gemini for candidate substantive modifications.
        """
        old_s = pair.older_section
        new_s = pair.newer_section

        # Case 1: ADDED Section (Exists only in Newer Document)
        if old_s is None and new_s is not None:
            new_src = EvidenceSource(
                document_id=newer_doc.document_id,
                section_id=new_s.section_id,
                heading=new_s.heading,
                section_number=new_s.section_number,
                url=newer_doc.url,
                published_date=newer_doc.published_date
            )
            return DetailedSectionChange(
                section=new_s.section_number or str(new_s.order),
                heading=new_s.heading,
                change_type="ADDED",
                substantive_change=True,
                modification_category="applicability",
                matching_method=pair.matching_method,
                matching_confidence=pair.matching_confidence,
                previous_text=None,
                current_text=new_s.content,
                summary=f"New regulatory section '{new_s.heading}' introduced in the revised circular.",
                old_requirement="N/A (Section did not exist in previous version)",
                new_requirement=new_s.content[:300] + ("..." if len(new_s.content) > 300 else ""),
                impact=f"Regulated entities must review and implement new requirements under '{new_s.heading}'.",
                evidence=[new_s.content[:200]],
                old_source=None,
                new_source=new_src
            )

        # Case 2: REMOVED Section (Exists only in Older Document)
        if old_s is not None and new_s is None:
            old_src = EvidenceSource(
                document_id=older_doc.document_id,
                section_id=old_s.section_id,
                heading=old_s.heading,
                section_number=old_s.section_number,
                url=older_doc.url,
                published_date=older_doc.published_date
            )
            return DetailedSectionChange(
                section=old_s.section_number or str(old_s.order),
                heading=old_s.heading,
                change_type="REMOVED",
                substantive_change=True,
                modification_category="applicability",
                matching_method=pair.matching_method,
                matching_confidence=pair.matching_confidence,
                previous_text=old_s.content,
                current_text=None,
                summary=f"Section '{old_s.heading}' omitted or repealed in the revised version.",
                old_requirement=old_s.content[:300] + ("..." if len(old_s.content) > 300 else ""),
                new_requirement="N/A (Section omitted in revised version)",
                impact=f"Prior requirements under '{old_s.heading}' are no longer mandated in the current circular.",
                evidence=[old_s.content[:200]],
                old_source=old_src,
                new_source=None
            )

        # Case 3: Matched Pair (Both old_s and new_s exist)
        assert old_s is not None and new_s is not None

        old_src = EvidenceSource(
            document_id=older_doc.document_id,
            section_id=old_s.section_id,
            heading=old_s.heading,
            section_number=old_s.section_number,
            url=older_doc.url,
            published_date=older_doc.published_date
        )
        new_src = EvidenceSource(
            document_id=newer_doc.document_id,
            section_id=new_s.section_id,
            heading=new_s.heading,
            section_number=new_s.section_number,
            url=newer_doc.url,
            published_date=newer_doc.published_date
        )

        # 3A. Exact or Normalized Equivalence -> UNCHANGED (Skip Gemini)
        if are_texts_substantively_equal(old_s.content, new_s.content):
            return DetailedSectionChange(
                section=new_s.section_number or old_s.section_number or str(new_s.order),
                heading=new_s.heading,
                change_type="UNCHANGED",
                substantive_change=False,
                modification_category=None,
                matching_method=pair.matching_method,
                matching_confidence=pair.matching_confidence,
                previous_text=old_s.content,
                current_text=new_s.content,
                summary="Wording and regulatory requirements retained verbatim with no substantive changes.",
                old_requirement=old_s.content[:250],
                new_requirement=new_s.content[:250],
                impact="No compliance modification required.",
                evidence=[],
                old_source=old_src,
                new_source=new_src
            )

        # 3B. Candidate Substantive Modification
        # Infer regulatory category from keywords
        from app.change_detection.section_comparer import SectionComparer
        mod_cat = SectionComparer.infer_modification_category(f"{new_s.content} {new_s.heading}")

        # If LLM client is available, generate structured assessment
        if client:
            llm_res = self._call_gemini_section_diff(
                client=client,
                section_title=new_s.heading,
                previous_text=old_s.content,
                current_text=new_s.content
            )
            if llm_res:
                return DetailedSectionChange(
                    section=new_s.section_number or old_s.section_number or str(new_s.order),
                    heading=new_s.heading,
                    change_type=llm_res.get("change_type", "MODIFIED"),
                    substantive_change=llm_res.get("substantive_change", True),
                    modification_category=mod_cat,
                    matching_method=pair.matching_method,
                    matching_confidence=pair.matching_confidence,
                    previous_text=old_s.content,
                    current_text=new_s.content,
                    summary=llm_res.get("summary", "Section provisions amended."),
                    old_requirement=llm_res.get("old_requirement"),
                    new_requirement=llm_res.get("new_requirement"),
                    impact=llm_res.get("impact"),
                    evidence=llm_res.get("evidence", [new_s.content[:200]]),
                    old_source=old_src,
                    new_source=new_src
                )

        # Deterministic fallback if Gemini is offline or not requested
        return DetailedSectionChange(
            section=new_s.section_number or old_s.section_number or str(new_s.order),
            heading=new_s.heading,
            change_type="MODIFIED",
            substantive_change=True,
            modification_category=mod_cat,
            matching_method=pair.matching_method,
            matching_confidence=pair.matching_confidence,
            previous_text=old_s.content,
            current_text=new_s.content,
            summary=f"Section '{new_s.heading}' amended ({mod_cat}).",
            old_requirement=old_s.content[:250],
            new_requirement=new_s.content[:250],
            impact=f"Review updated '{new_s.heading}' requirements.",
            evidence=[new_s.content[:200]],
            old_source=old_src,
            new_source=new_src
        )

    def _call_gemini_section_diff(
        self,
        client: Any,
        section_title: str,
        previous_text: str,
        current_text: str
    ) -> Optional[Dict[str, Any]]:
        """Invokes Gemini with structured JSON output and strict grounding rules."""
        prompt = build_structured_comparison_prompt(
            section_title=section_title,
            previous_text=previous_text,
            current_text=current_text
        )

        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=settings.gemini_generation_model,
                    contents=prompt
                )
                raw_text = response.text.strip() if response and response.text else ""
                # Strip optional json code fence
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("\n", 1)[-1]
                    if raw_text.endswith("```"):
                        raw_text = raw_text.rsplit("```", 1)[0]
                    raw_text = raw_text.strip()

                data = json.loads(raw_text)
                if isinstance(data, dict) and "change_type" in data:
                    return data
            except Exception as e:
                logger.debug(f"Gemini section diff parse error (attempt {attempt+1}): {e}")

        return None

    def _generate_key_changes(self, changes: List[DetailedSectionChange]) -> List[str]:
        """Deterministically aggregates 3–6 key change bullet points from structured delta objects."""
        bullets: List[str] = []

        substantive = [c for c in changes if c.change_type != "UNCHANGED"]

        # Prioritize Modified and Added sections
        for c in substantive:
            if len(bullets) >= 6:
                break
            if c.change_type == "MODIFIED" and c.summary:
                bullets.append(f"[{c.heading}]: {c.summary}")
            elif c.change_type == "ADDED":
                bullets.append(f"[New Section Added]: '{c.heading}' introduced in the revised framework.")
            elif c.change_type == "REMOVED":
                bullets.append(f"[Section Repealed]: '{c.heading}' omitted from the revised circular.")

        if not bullets:
            bullets.append("All extracted sections match with no substantive regulatory modifications.")

        return bullets

    def _compose_executive_summary(
        self,
        older_doc: RegulatoryDocument,
        newer_doc: RegulatoryDocument,
        counts: Dict[str, int],
        key_changes: List[str],
        rel_type: str,
        order_conf: str
    ) -> str:
        """Composes clean executive summary text."""
        total = sum(counts.values())
        summary_lines = [
            f"Regulatory comparison between **{older_doc.title}** ({older_doc.published_date or 'N/A'}) "
            f"and **{newer_doc.title}** ({newer_doc.published_date or 'N/A'}).",
            f"**Relationship**: `{rel_type}` (Chronology Confidence: `{order_conf.upper()}`).",
            f"**Section Delta Summary**: Total Analyzed: {total} | Added: {counts['added']} | Modified: {counts['modified']} | Removed: {counts['removed']} | Unchanged: {counts['unchanged']}.",
            "",
            "**Key Regulatory Modifications**:"
        ]
        for idx, k in enumerate(key_changes, start=1):
            summary_lines.append(f"{idx}. {k}")

        return "\n".join(summary_lines)

    def compare(self, doc_a_id: str, doc_b_id: str, generate_summaries: bool = True) -> Dict[str, Any]:
        """Convenience method returning dictionary or raising error on missing docs."""
        report = self.compare_documents(doc_a_id, doc_b_id, generate_summaries=generate_summaries)
        if report.status == "ERROR":
            raise FileNotFoundError(report.message)
        return report.model_dump()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Direct Regulatory Document Comparison CLI.")
    parser.add_argument("--document-a", type=str, required=True, help="Document A ID")
    parser.add_argument("--document-b", type=str, required=True, help="Document B ID")
    args = parser.parse_args()

    comparator = DocumentComparator()
    report = comparator.compare_documents(args.document_a, args.document_b)
    report.print_formatted()


if __name__ == "__main__":
    main()
