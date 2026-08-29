"""
Regulatory Document Version Tracking and Predecessor Resolution Module.

Detects explicit supersession references ("supersedes", "replaces", "earlier circular"),
identifies candidate predecessors using title similarity and taxonomy alignment,
and maintains version graph relationships (current vs. historical) without unjustified legal claims.
"""

import re
import json
import logging
import argparse
from typing import List, Dict, Any, Optional, Tuple
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
    Manages document version relationships and lineage graph.
    """

    def __init__(self, repository: Optional[DocumentRepository] = None):
        self.repository = repository or DocumentRepository()

    def _load_all_documents(self) -> List[Dict[str, Any]]:
        """Loads all available document records from MongoDB or local processed JSON files."""
        docs: List[Dict[str, Any]] = []

        # From local JSON
        if settings.processed_data_dir.exists():
            for f in settings.processed_data_dir.glob("*.json"):
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
        Scans document text for explicit supersession clauses and extracts the referenced circular number.
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
        1. Explicit circular references in text
        2. Same source + same category match
        3. Title token overlap / similarity
        4. Publication date (candidate must be older than target)
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

            # Must be older or same date
            if cand_date > target_date:
                continue

            score = 0.0

            # 1. Explicit circular match
            if explicit_ref and cand_circ and explicit_ref.lower() in cand_circ.lower():
                score += 10.0

            # 2. Source match
            if cand_src.upper() == target_src.upper():
                score += 1.0

            # 3. Category match
            if target_cat and cand_cat and (target_cat in cand_cat or cand_cat in target_cat):
                score += 2.0

            # 4. Title similarity overlap
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
            if other_sup == document_id or other_sup == target_doc.get("circular_number"):
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


def main():
    parser = argparse.ArgumentParser(description="RegIntel Document Version Tracker CLI")
    parser.add_argument("--document", required=True, help="Document ID to inspect version lineage")
    args = parser.parse_args()

    tracker = VersionTracker()
    info = tracker.resolve_document_relationships(args.document)

    print("\n" + "=" * 65)
    print("REGULATORY DOCUMENT VERSION RELATIONSHIP")
    print("=" * 65)
    print(f"Document ID             : {info.get('document_id')}")
    print(f"Title                   : {info.get('title')}")
    print(f"Current Status          : {info.get('status', '').upper()}")
    print(f"Document Version        : {info.get('document_version')}")
    print(f"Relationship Type       : {info.get('relationship_type')}")
    print(f"Confidence Level        : {info.get('relationship_confidence', '').upper()}")
    print(f"Supersedes (Predecessor): {info.get('predecessor_id') or 'None identified'}")
    print(f"Superseded By (Successor): {info.get('successor_id') or 'None (Current)'}")
    print(f"Candidate Predecessors  : {len(info.get('predecessor_candidates', []))} found")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
