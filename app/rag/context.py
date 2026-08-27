"""
Context formatting and evidence construction module for RegIntel RAG.
Converts retrieved regulatory chunks into numbered evidence blocks with clear metadata labels.
"""

from typing import List
from app.retrieval.mongodb_vector import RetrievedChunk


def build_evidence_context(retrieved_chunks: List[RetrievedChunk]) -> str:
    """
    Formats a list of RetrievedChunk objects into clean, numbered evidence blocks.
    Excludes embeddings and unnecessary internal parameters.
    """
    if not retrieved_chunks:
        return "No relevant regulatory documents found."

    blocks = []
    for idx, chunk in enumerate(retrieved_chunks, start=1):
        lines = [
            f"SOURCE [{idx}]",
            f"Title: {chunk.title or 'Untitled'}",
            f"Source: {chunk.source}",
            f"Section: {chunk.section or 'General'}",
            f"Category: {chunk.category or 'General'}",
            f"Published Date: {chunk.published_date or 'Not specified'}",
            f"Effective Date: {chunk.effective_date or 'Not specified'}",
            f"URL: {chunk.url}",
            "",
            "Content:",
            chunk.content.strip()
        ]
        blocks.append("\n".join(lines))

    return "\n\n" + ("-" * 40) + "\n\n".join(blocks) + "\n" + ("-" * 40)
