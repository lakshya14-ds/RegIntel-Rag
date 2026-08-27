"""
Predecessor Document Matching and Regulatory Lineage Module.

Identifies defensible previous versions or predecessor circulars for a current regulatory document
using metadata alignment, date ordering, and explicit superseding circular references.
"""

import re
import logging
from typing import List, Optional, Tuple, Literal
from pydantic import BaseModel

from app.ingestion.models import RegulatoryDocument
from app.retrieval.temporal import parse_date_safe

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class PredecessorMatch(BaseModel):
    """Represents an identified predecessor regulatory document with relationship provenance."""
    predecessor: RegulatoryDocument
    confidence: Literal["high", "medium", "low", "possible_predecessor"]
    match_reason: str


def compute_title_overlap(title_a: Optional[str], title_b: Optional[str]) -> float:
    """Computes Jaccard word token similarity between two titles."""
    if not title_a or not title_b:
        return 0.0
    words_a = set(re.findall(r"\b[a-zA-Z0-9]+\b", title_a.lower()))
    words_b = set(re.findall(r"\b[a-zA-Z0-9]+\b", title_b.lower()))
    # Exclude common boilerplate words
    stopwords = {"master", "circular", "for", "the", "with", "of", "and", "in", "by", "to", "on"}
    words_a = words_a - stopwords
    words_b = words_b - stopwords
    if not words_a or not words_b:
        return 0.0
    intersection = words_a.intersection(words_b)
    union = words_a.union(words_b)
    return len(intersection) / len(union)


class DocumentMatcher:
    """
    Identifies the most defensible predecessor regulatory document for comparative change analysis.
    """

    @classmethod
    def find_predecessor(
        cls,
        current_doc: RegulatoryDocument,
        candidate_docs: List[RegulatoryDocument]
    ) -> Optional[PredecessorMatch]:
        """
        Selects the best predecessor document from candidate documents.
        Returns None if no defensible relationship is identified.
        """
        if not current_doc or not candidate_docs:
            return None

        curr_date = parse_date_safe(current_doc.published_date) or parse_date_safe(current_doc.effective_date)
        valid_candidates = []

        for cand in candidate_docs:
            # 1. Skip self
            if cand.document_id == current_doc.document_id:
                continue

            # 2. Must share category or source
            if cand.category and current_doc.category and cand.category != current_doc.category:
                continue

            # 3. Check chronological ordering
            cand_date = parse_date_safe(cand.published_date) or parse_date_safe(cand.effective_date)
            if curr_date and cand_date and cand_date >= curr_date:
                # Candidate is newer than or same date as current document
                continue

            valid_candidates.append((cand, cand_date))

        if not valid_candidates:
            return None

        # Check explicit reference in text
        for cand, c_date in valid_candidates:
            if cand.circular_number and cand.circular_number.lower() in current_doc.content.lower():
                return PredecessorMatch(
                    predecessor=cand,
                    confidence="high",
                    match_reason=f"Current document explicitly references predecessor circular number '{cand.circular_number}'."
                )

        # Check for matching document type and high title overlap
        scored_matches = []
        for cand, c_date in valid_candidates:
            title_score = compute_title_overlap(current_doc.title, cand.title)
            same_type = (cand.document_type == current_doc.document_type) if (cand.document_type and current_doc.document_type) else False
            
            # Composite score
            score = title_score * 0.7 + (0.3 if same_type else 0.0)
            scored_matches.append((cand, c_date, score, title_score, same_type))

        scored_matches.sort(key=lambda x: x[2], reverse=True)
        best_cand, best_date, best_score, title_sim, same_type = scored_matches[0]

        if best_score >= 0.50:
            confidence = "medium"
            reason = f"Same regulatory category ('{current_doc.category}') with high title similarity ({title_sim:.2f}) and prior publication date."
        elif best_score >= 0.25:
            confidence = "possible_predecessor"
            reason = f"Same regulatory domain with partial title overlap ({title_sim:.2f})."
        else:
            confidence = "low"
            reason = f"Older document in category '{current_doc.category}', but title alignment is weak ({title_sim:.2f})."

        return PredecessorMatch(
            predecessor=best_cand,
            confidence=confidence,
            match_reason=reason
        )
