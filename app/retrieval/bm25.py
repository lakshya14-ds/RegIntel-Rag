"""
BM25 Keyword Retrieval Module for Regulatory Documents.

Implements lexical retrieval using BM25Plus, specifically preserving regulatory
identifiers, circular numbers, section clauses, and legal terminology.
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from rank_bm25 import BM25Plus

from app.config import settings
from app.ingestion.models import DocumentChunk, from_mongo
from app.retrieval.mongodb_vector import RetrievedChunk

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def tokenize_regulatory_text(text: str) -> List[str]:
    """
    Tokenizes regulatory text preserving circular numbers, slashed identifiers,
    section numbers (e.g. '15A', '4.2', 'SEBI/HO/MIRSD/2024/56'), and alphanumeric terms.
    """
    if not text or not isinstance(text, str):
        return []

    # Extract both full slashed/hyphenated tokens and individual alphanumeric terms
    # to maximize exact and partial phrase matching
    tokens = re.findall(r"[a-zA-Z0-9]+(?:[/\-_][a-zA-Z0-9]+)+|\b[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*\b", text.lower())
    sub_tokens = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
    combined = list(dict.fromkeys(tokens + sub_tokens))
    return [t for t in combined if len(t.strip()) > 1 or t.isalnum()]


class BM25Retriever:
    """
    Lexical search engine over regulatory chunks using BM25Plus.
    Built once during initialization and reused across queries.
    """

    def __init__(self, chunks_dir: Optional[Path] = None):
        self.chunks_dir = chunks_dir or settings.chunks_data_dir
        self.chunks: List[DocumentChunk] = []
        self.corpus_tokens: List[List[str]] = []
        self.bm25: Optional[BM25Plus] = None
        self._is_indexed = False

    def _build_searchable_text(self, chunk: DocumentChunk) -> str:
        """Constructs rich searchable text emphasizing title, section, and circular identifier."""
        parts = []
        if chunk.title:
            parts.append(chunk.title)
        if chunk.section:
            parts.append(chunk.section)
        if chunk.circular_number:
            parts.append(chunk.circular_number)
        if chunk.category:
            parts.append(chunk.category)
        if chunk.content:
            parts.append(chunk.content)
        return " ".join(parts)

    def load_chunks_from_disk(self) -> List[DocumentChunk]:
        """Loads all processed chunk files from disk."""
        chunk_files = list(self.chunks_dir.glob("*_chunks.json"))
        loaded_chunks: List[DocumentChunk] = []

        for cf in chunk_files:
            try:
                with open(cf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for c_dict in data.get("chunks", []):
                    loaded_chunks.append(from_mongo(DocumentChunk, c_dict))
            except Exception as e:
                logger.error(f"Failed to read chunk file {cf.name}: {e}")

        logger.info(f"Loaded {len(loaded_chunks)} chunks for BM25 indexing from {self.chunks_dir}")
        return loaded_chunks

    def build_index(self, chunks: Optional[List[DocumentChunk]] = None):
        """
        Builds the in-memory BM25 index from the given chunks or local disk corpus.
        """
        self.chunks = chunks if chunks is not None else self.load_chunks_from_disk()
        if not self.chunks:
            logger.warning("No chunks available to build BM25 index.")
            self.bm25 = None
            self._is_indexed = False
            return

        self.corpus_tokens = []
        for c in self.chunks:
            searchable_text = self._build_searchable_text(c)
            tokens = tokenize_regulatory_text(searchable_text)
            self.corpus_tokens.append(tokens)

        self.bm25 = BM25Plus(self.corpus_tokens)
        self._is_indexed = True
        logger.info(f"BM25 index successfully built for {len(self.chunks)} chunks.")

    def refresh_index(self):
        """Rebuilds the BM25 index from current storage."""
        self.build_index()

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        """
        Executes BM25 keyword search for the query, returning top-k RetrievedChunk items.
        """
        if not query or not query.strip():
            return []

        if not self._is_indexed or self.bm25 is None:
            logger.info("BM25 index not initialized. Building index now...")
            self.build_index()

        if not self.bm25 or not self.chunks:
            logger.warning("BM25 search invoked on empty corpus.")
            return []

        query_tokens = tokenize_regulatory_text(query.strip())
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # Pair scores with chunk indices
        scored_pairs = []
        for idx, score in enumerate(scores):
            if score <= 0.0:
                continue

            chunk = self.chunks[idx]

            # Apply metadata filter if provided
            if filter_dict:
                match = True
                for k, v in filter_dict.items():
                    if getattr(chunk, k, None) != v:
                        match = False
                        break
                if not match:
                    continue

            scored_pairs.append((idx, float(score)))

        # Sort descending by BM25 score
        scored_pairs.sort(key=lambda x: x[1], reverse=True)
        top_pairs = scored_pairs[:top_k]

        results: List[RetrievedChunk] = []
        for idx, score in top_pairs:
            c = self.chunks[idx]
            results.append(RetrievedChunk(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                title=c.title,
                content=c.content,
                section=c.section,
                source=c.source,
                category=c.category,
                document_type=c.document_type,
                published_date=c.published_date,
                effective_date=c.effective_date,
                url=c.url,
                score=round(score, 4)
            ))

        return results


# Default singleton instance
_default_bm25_retriever = BM25Retriever()


def search_bm25(query: str, top_k: int = 10, filter_dict: Optional[Dict[str, Any]] = None) -> List[RetrievedChunk]:
    return _default_bm25_retriever.search(query, top_k=top_k, filter_dict=filter_dict)


def build_bm25_index(chunks: Optional[List[DocumentChunk]] = None):
    _default_bm25_retriever.build_index(chunks)
