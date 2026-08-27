"""
Citation and Grounding Validation System for RegIntel RAG.

Provides deterministic source ID mapping ([1], [2], ...), verifies citation integrity,
detects hallucinated source tags, and builds structured SourceCitation records.
"""

import re
from typing import List, Dict, Any, Set, Tuple, Optional
from pydantic import BaseModel, Field

from app.retrieval.mongodb_vector import RetrievedChunk


class SourceCitation(BaseModel):
    """Structured citation attached to a grounded regulatory response."""
    source_id: int
    chunk_id: str
    document_id: str
    source: str
    title: str
    section: Optional[str] = "General"
    published_date: Optional[str] = "N/A"
    effective_date: Optional[str] = "N/A"
    url: str
    score: float


def extract_citation_indices(text: str) -> Set[int]:
    """Extracts all referenced bracketed numbers e.g. [1], [2], [1, 2], [3-4]."""
    if not text:
        return set()

    found_ids: Set[int] = set()
    # Match patterns like [1], [2, 3], [1-3]
    matches = re.findall(r"\[([\d\s,\-]+)\]", text)
    for match in matches:
        # Handle comma-separated
        for part in match.split(","):
            part = part.strip()
            if "-" in part:
                range_parts = part.split("-")
                if len(range_parts) == 2 and range_parts[0].strip().isdigit() and range_parts[1].strip().isdigit():
                    start_i = int(range_parts[0].strip())
                    end_i = int(range_parts[1].strip())
                    for num in range(start_i, end_i + 1):
                        found_ids.add(num)
            elif part.isdigit():
                found_ids.add(int(part))

    return found_ids


class CitationManager:
    """Manages citation mapping and verifies that LLM answers adhere strictly to retrieved sources."""

    @staticmethod
    def extract_citation_indices(text: str) -> Set[int]:
        return extract_citation_indices(text)

    @staticmethod
    def build_source_citations(retrieved_chunks: List[RetrievedChunk]) -> List[SourceCitation]:
        """Maps retrieved chunks to sequential source citations [1], [2], etc."""
        citations: List[SourceCitation] = []
        for idx, chunk in enumerate(retrieved_chunks, start=1):
            citations.append(SourceCitation(
                source_id=idx,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source=chunk.source,
                title=chunk.title or "SEBI Document",
                section=chunk.section or "General",
                published_date=chunk.published_date or "N/A",
                effective_date=chunk.effective_date or "N/A",
                url=chunk.url,
                score=round(chunk.score, 4)
            ))
        return citations

    @staticmethod
    def validate_answer_citations(
        generated_answer: str,
        retrieved_chunks: List[RetrievedChunk]
    ) -> Tuple[List[SourceCitation], bool, List[int]]:
        """
        Validates that every citation tag in the answer maps to a real retrieved chunk [1..N].
        Returns:
            - validated_citations: List of SourceCitation objects corresponding to used sources
            - is_valid: False if out-of-bounds citations (e.g. [99]) were present
            - invalid_ids: List of invalid IDs found
        """
        total_sources = len(retrieved_chunks)
        cited_ids = extract_citation_indices(generated_answer)

        invalid_ids = [sid for sid in cited_ids if sid < 1 or sid > total_sources]
        is_valid = len(invalid_ids) == 0

        # Build citations for valid IDs
        all_citations = CitationManager.build_source_citations(retrieved_chunks)
        
        # If model didn't output explicit brackets, include all retrieved sources that were in context
        if not cited_ids and retrieved_chunks:
            return all_citations, True, []

        used_citations = [c for c in all_citations if c.source_id in cited_ids]
        return used_citations, is_valid, invalid_ids

    @staticmethod
    def sanitize_invalid_citations(answer: str, max_valid_id: int) -> str:
        """Strips out invalid citation tags like [99] when max is 5."""
        def _replace_tag(match):
            inner = match.group(1)
            valid_nums = []
            for num_str in re.findall(r"\d+", inner):
                num = int(num_str)
                if 1 <= num <= max_valid_id:
                    valid_nums.append(str(num))
            if valid_nums:
                return f"[{', '.join(valid_nums)}]"
            return ""

        sanitized = re.sub(r"\[([\d\s,\-]+)\]", _replace_tag, answer)
        return re.sub(r"\s+", " ", sanitized).strip()


# Convenience functions
def validate_citations(
    generated_answer: str,
    retrieved_chunks: List[RetrievedChunk]
) -> List[SourceCitation]:
    citations, _, _ = CitationManager.validate_answer_citations(generated_answer, retrieved_chunks)
    return citations
