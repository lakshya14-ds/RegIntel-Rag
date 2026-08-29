"""
Regulatory Document Version Tracking, Lineage Graph, and Predecessor Resolution Module.

Detects explicit legal supersession references ("supersedes", "replaces", "in supersession of"),
identifies candidate predecessors using taxonomy alignment and title similarity,
maintains version timeline relationships (Current vs. Historical), and determines comparison eligibility.
"""

import re
import json
import logging
import argparse
from typing import List, Dict, Any, Optional, Tuple, Literal
from pathlib import Path

from app.config import settings
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.ingestion.repository import DocumentRepository

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Explicit legal supersession regex patterns
EXPLICIT_SUPERSESSION_PATTERNS = [
    r"supersedes\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)",
    r"in\s+supersession\s+of\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)",
    r"replaces\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)",
    r"shall\s+replace\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)",
    r"rescinds\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)",
    r"amends\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)",
    r"earlier\s+circular\s*(?:no\.?|number)?\s*([A-Za-z0-9\/\-_]+)"
]


class VersionTracker:
    """
    Manages document version relationships, lineage graph, and comparison eligibility.
    """

    def __init__(self, repository: Optional[DocumentRepository] = None):
        self.repository = repository or DocumentRepository()

    def _load_all_documents(self) -> List[Dict[str, Any]]:
        """Loads all available document records from MongoDB or local processed JSON files."""
        docs: List[Dict[str, Any]] = []

        # From local JSON
        if settings.processed_data_dir.exists():
            for f in settings.processed_data_dir.glob("*.json"):
                if f.name.endswith("_chunks.json"):
                    continue
                try:
                    with open(f, "r", encoding="utf-8") as jf:
                        d = json.load(jf)
                        if isinstance(d, dict) and "document_id" in d:
                            docs.append(d)
                except Exception:
                    continue
        return docs

    def _get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Loads a single document by ID from MongoDB or local store."""
        try:
            doc_model = self.repository.get_document(document_id)
            if doc_model:
                return doc_model.model_dump()
        except Exception:
            pass

        # Check local files with multiple naming conventions
        for candidate_name in [f"{document_id}.json", f"sebi_{document_id}.json"]:
            json_path = settings.processed_data_dir / candidate_name
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass

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

    def detect_explicit_supersession(self, content: str) -> Optional[str]:
        """
        Scans document text for explicit supersession clauses and extracts referenced circular numbers.
        """
        if not content:
            return None

        for pat in EXPLICIT_SUPERSESSION_PATTERNS:
            match = re.search(pat, content, re.IGNORECASE)
            if match:
                ref_num = match.group(1).strip().rstrip(".,;:")
                if len(ref_num) >= 4:
                    return ref_num
        return None

    def find_predecessor_candidates(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Discovers candidate predecessors for a target document using:
        1. Explicit circular references in text (Highest Priority)
        2. Circular / reference number matching
        3. Same source + same category + temporal plausibility (candidate date <= target date)
        4. Title token overlap / similarity
        """
        target_doc = self._get_document(document_id)
        if not target_doc:
            return []

        target_meta = target_doc.get("metadata", {})
        target_date = target_doc.get("published_date") or target_meta.get("published_date") or "9999-99-99"
        target_cat = (target_doc.get("category") or target_meta.get("category") or "").lower()
        target_src = target_doc.get("source") or target_meta.get("source", "SEBI")
        target_title = (target_doc.get("title") or "").lower()
        target_content = target_doc.get("content", "")

        # Check explicit reference in text
        explicit_ref = self.detect_explicit_supersession(target_content)

        all_docs = self._load_all_documents()
        candidates: List[Tuple[float, Dict[str, Any]]] = []

        target_title_words = set(re.findall(r"\b\w{3,}\b", target_title))

        for cand in all_docs:
            cand_id = cand.get("document_id")
            if not cand_id or cand_id == document_id:
                continue

            cand_meta = cand.get("metadata", {})
            cand_date = cand.get("published_date") or cand_meta.get("published_date") or "1970-01-01"
            cand_src = cand.get("source") or cand_meta.get("source", "SEBI")
            cand_cat = (cand.get("category") or cand_meta.get("category") or "").lower()
            cand_circ = cand.get("circular_number") or cand_meta.get("circular_number")
            cand_title = (cand.get("title") or "").lower()

            # Must be older or same date for predecessor
            if cand_date > target_date:
                continue

            score = 0.0

            # Priority 1: Explicit circular match
            if explicit_ref and cand_circ and explicit_ref.lower() in cand_circ.lower():
                score += 10.0

            # Priority 2: Source match
            if cand_src.upper() == target_src.upper():
                score += 1.0

            # Priority 3: Category match
            if target_cat and cand_cat and (target_cat in cand_cat or cand_cat in target_cat):
                score += 2.0

            # Priority 4: Title similarity overlap
            cand_title_words = set(re.findall(r"\b\w{3,}\b", cand_title))
            if target_title_words and cand_title_words:
                overlap = len(target_title_words.intersection(cand_title_words))
                union = len(target_title_words.union(cand_title_words))
                jaccard = overlap / union if union > 0 else 0.0
                score += jaccard * 3.0

            if score > 1.5:
                candidates.append((score, cand))

        # Sort descending by score, then by published_date descending
        candidates.sort(
            key=lambda x: (
                x[0],
                x[1].get("published_date") or x[1].get("metadata", {}).get("published_date") or "1970-01-01"
            ),
            reverse=True
        )

        return [c[1] for c in candidates[:5]]

    def resolve_document_relationships(self, document_id: str) -> Dict[str, Any]:
        """
        Resolves version relationships, predecessor, successor, status, and confidence for a document.
        """
        target_doc = self._get_document(document_id)
        if not target_doc:
            return {
                "document_id": document_id,
                "status": "unknown",
                "document_version": "1.0",
                "relationship_type": "UNKNOWN",
                "relationship_confidence": "low",
                "predecessor_id": None,
                "successor_id": None,
                "predecessor_candidates": []
            }

        target_meta = target_doc.get("metadata", {})
        content = target_doc.get("content", "")
        explicit_ref = self.detect_explicit_supersession(content)

        candidates = self.find_predecessor_candidates(document_id)
        candidate_ids = [c.get("document_id") for c in candidates if c.get("document_id")]

        predecessor_id: Optional[str] = None
        relationship_type = "NEW"
        relationship_confidence = "low"
        status_val = target_doc.get("status") or target_meta.get("status") or "current"

        if explicit_ref:
            # Check if any candidate matches the explicit circular number
            for cand in candidates:
                cand_circ = cand.get("circular_number") or cand.get("metadata", {}).get("circular_number")
                if cand_circ and explicit_ref.lower() in cand_circ.lower():
                    predecessor_id = cand.get("document_id")
                    break

            relationship_type = "SUPERSEDES"
            relationship_confidence = "high"
            if not predecessor_id and candidate_ids:
                predecessor_id = candidate_ids[0]

        elif candidates:
            # Candidate match based on high taxonomy + title overlap
            top_cand = candidates[0]
            predecessor_id = top_cand.get("document_id")
            relationship_type = "UPDATE"
            relationship_confidence = "medium"

        # Check if any other document supersedes this target document
        all_docs = self._load_all_documents()
        successor_id: Optional[str] = None
        for other in all_docs:
            if other.get("document_id") == document_id:
                continue
            other_meta = other.get("metadata", {})
            other_sup = other.get("supersedes") or other_meta.get("supersedes")
            if other_sup == document_id or (target_doc.get("circular_number") and other_sup == target_doc.get("circular_number")):
                successor_id = other.get("document_id")
                status_val = "historical"
                break

        return {
            "document_id": document_id,
            "title": target_doc.get("title"),
            "status": status_val,
            "document_version": target_doc.get("document_version") or target_meta.get("document_version", "1.0"),
            "relationship_type": relationship_type,
            "relationship_confidence": relationship_confidence,
            "predecessor_id": predecessor_id,
            "successor_id": successor_id,
            "predecessor_candidates": candidate_ids
        }

    def get_document_versions(self, document_id: str) -> Dict[str, Any]:
        """
        Builds a full version graph and chronological timeline for a regulatory document.
        """
        rel_info = self.resolve_document_relationships(document_id)
        all_docs = self._load_all_documents()
        all_by_id = {d.get("document_id"): d for d in all_docs if d.get("document_id")}

        # 1. Predecessor doc info
        pred_doc = all_by_id.get(rel_info.get("predecessor_id")) if rel_info.get("predecessor_id") else None

        # 2. Successor docs info
        succ_doc = all_by_id.get(rel_info.get("successor_id")) if rel_info.get("successor_id") else None

        # 3. Related documents (same category)
        target_doc = all_by_id.get(document_id, {})
        target_cat = (target_doc.get("category") or target_doc.get("metadata", {}).get("category") or "").lower()

        related: List[Dict[str, Any]] = []
        if target_cat:
            for d in all_docs:
                if d.get("document_id") == document_id:
                    continue
                d_cat = (d.get("category") or d.get("metadata", {}).get("category") or "").lower()
                if d_cat == target_cat:
                    related.append(d)

        # 4. Construct Chronological Timeline
        timeline_nodes: List[Dict[str, Any]] = []
        visited = set()

        # Follow predecessor chain backwards
        curr_pred_id = rel_info.get("predecessor_id")
        while curr_pred_id and curr_pred_id in all_by_id and curr_pred_id not in visited:
            visited.add(curr_pred_id)
            d = all_by_id[curr_pred_id]
            timeline_nodes.insert(0, {
                "document_id": d.get("document_id"),
                "title": d.get("title"),
                "published_date": d.get("published_date") or d.get("metadata", {}).get("published_date"),
                "status": "historical",
                "relationship": "predecessor"
            })
            p_info = self.resolve_document_relationships(curr_pred_id)
            curr_pred_id = p_info.get("predecessor_id")

        # Add target doc
        timeline_nodes.append({
            "document_id": document_id,
            "title": target_doc.get("title"),
            "published_date": target_doc.get("published_date") or target_doc.get("metadata", {}).get("published_date"),
            "status": rel_info.get("status", "current"),
            "relationship": "target"
        })

        # Follow successor chain forwards
        curr_succ_id = rel_info.get("successor_id")
        while curr_succ_id and curr_succ_id in all_by_id and curr_succ_id not in visited:
            visited.add(curr_succ_id)
            d = all_by_id[curr_succ_id]
            timeline_nodes.append({
                "document_id": d.get("document_id"),
                "title": d.get("title"),
                "published_date": d.get("published_date") or d.get("metadata", {}).get("published_date"),
                "status": "current",
                "relationship": "successor"
            })
            s_info = self.resolve_document_relationships(curr_succ_id)
            curr_succ_id = s_info.get("successor_id")

        return {
            "document_id": document_id,
            "status": rel_info.get("status", "unknown"),
            "document_version": rel_info.get("document_version", "1.0"),
            "relationship_type": rel_info.get("relationship_type", "UNKNOWN"),
            "relationship_confidence": rel_info.get("relationship_confidence", "low"),
            "predecessor": pred_doc,
            "successor": succ_doc,
            "related_documents": related[:5],
            "timeline": timeline_nodes
        }

    def determine_comparison_eligibility(self, doc_a_id: str, doc_b_id: str) -> Tuple[str, Optional[str]]:
        """
        Determines if two documents are eligible for automatic comparison:
        - 'high': direct version lineage (supersedes)
        - 'medium': related category with high similarity
        - 'low': explicit comparison allowed but warning displayed
        - 'unknown': no clear taxonomy relation
        """
        doc_a = self._get_document(doc_a_id)
        doc_b = self._get_document(doc_b_id)

        if not doc_a or not doc_b:
            return "unknown", "One or both documents not found."

        # Check explicit supersession
        exp_a = self.detect_explicit_supersession(doc_a.get("content", ""))
        exp_b = self.detect_explicit_supersession(doc_b.get("content", ""))
        circ_a = doc_a.get("circular_number") or doc_a.get("metadata", {}).get("circular_number", "")
        circ_b = doc_b.get("circular_number") or doc_b.get("metadata", {}).get("circular_number", "")

        if (exp_b and circ_a and exp_b.lower() in circ_a.lower()) or (exp_a and circ_b and exp_a.lower() in circ_b.lower()):
            return "high", None

        # Check category alignment
        cat_a = (doc_a.get("category") or doc_a.get("metadata", {}).get("category") or "").lower()
        cat_b = (doc_b.get("category") or doc_b.get("metadata", {}).get("category") or "").lower()

        if cat_a and cat_b and cat_a == cat_b:
            return "medium", f"Both circulars belong to '{doc_a.get('category')}'. Verify specific clause applicability."

        return "low", "Documents do not share the same regulatory category. Comparison is manual."


def main():
    parser = argparse.ArgumentParser(description="RegIntel Document Version Tracker CLI")
    parser.add_argument("--document", required=True, help="Document ID to inspect version lineage")
    args = parser.parse_args()

    tracker = VersionTracker()
    info = tracker.get_document_versions(args.document)

    print("\n" + "=" * 65)
    print("REGULATORY DOCUMENT VERSION RELATIONSHIP & TIMELINE")
    print("=" * 65)
    print(f"Document ID             : {info.get('document_id')}")
    print(f"Current Status          : {info.get('status', '').upper()}")
    print(f"Document Version        : {info.get('document_version')}")
    print(f"Relationship Type       : {info.get('relationship_type')}")
    print(f"Confidence Level        : {info.get('relationship_confidence', '').upper()}")
    print(f"Supersedes (Predecessor): {info.get('predecessor', {}).get('title') if info.get('predecessor') else 'None'}")
    print(f"Superseded By (Successor): {info.get('successor', {}).get('title') if info.get('successor') else 'None (Current)'}")
    print("\nTIMELINE:")
    for node in info.get("timeline", []):
        print(f"  - [{node.get('status').upper()}] {node.get('title')} ({node.get('published_date') or 'N/A'})")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
