"""
Chunk Quality Validator for Regulatory Documents.

Validates that generated chunks meet strict quality standards for retrieval
before initiating embedding generation.
"""

import os
import sys
import re
import json
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal

from app.config import settings
from app.ingestion.models import DocumentChunk, RegulatoryDocument, from_mongo
from app.ingestion.chunker import count_tokens

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def safe_str(text: Optional[str]) -> str:
    """Safely converts text to printable string without crashing cp1252 consoles."""
    if not text:
        return ""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


@dataclass
class ChunkQualityReport:
    """Summary diagnostic report of chunk quality across the dataset."""
    documents_processed: int = 0
    total_chunks: int = 0
    avg_tokens_per_chunk: float = 0.0
    min_tokens: int = 0
    max_tokens: int = 0
    empty_chunks: int = 0
    duplicate_chunks: int = 0
    missing_section_metadata: int = 0
    content_loss_warnings: int = 0
    status: Literal["PASS", "WARNING", "FAIL"] = "PASS"
    details: List[str] = field(default_factory=list)

    def print_report(self):
        """Prints a human-readable quality report."""
        print("\n" + "=" * 45)
        print("Chunk Quality Report")
        print("-" * 45)
        print(f"Documents processed        : {self.documents_processed}")
        print(f"Total chunks               : {self.total_chunks}")
        print(f"Average tokens/chunk       : {self.avg_tokens_per_chunk:.1f}")
        print(f"Min tokens                 : {self.min_tokens}")
        print(f"Max tokens                 : {self.max_tokens}")
        print(f"Empty chunks               : {self.empty_chunks}")
        print(f"Duplicate chunks           : {self.duplicate_chunks}")
        print(f"Missing section metadata   : {self.missing_section_metadata}")
        print(f"Content-loss warnings      : {self.content_loss_warnings}")
        print(f"Overall status             : {self.status}")
        print("=" * 45)
        if self.details:
            print("\nDiagnostic Details:")
            for d in self.details[:10]:
                print(f"  * {safe_str(d)}")
            if len(self.details) > 10:
                print(f"  ... and {len(self.details) - 10} more items.")
        print()


class ChunkValidator:
    """
    Validates the integrity, token distributions, duplicate resistance,
    and semantic structure of generated regulatory chunks.
    """

    @staticmethod
    def _normalize_for_hash(text: str) -> str:
        """Strips whitespace and lowercase for duplicate detection."""
        return re.sub(r"\s+", " ", text).strip().lower()

    def validate_chunks(
        self,
        chunks: List[DocumentChunk],
        original_docs: Optional[Dict[str, RegulatoryDocument]] = None
    ) -> ChunkQualityReport:
        """
        Runs comprehensive validation across a collection of DocumentChunks.
        """
        report = ChunkQualityReport()
        if not chunks:
            report.status = "FAIL"
            report.details.append("No chunks provided for validation.")
            return report

        report.total_chunks = len(chunks)
        unique_docs = set(c.document_id for c in chunks)
        report.documents_processed = len(unique_docs)

        token_counts: List[int] = []
        seen_hashes: Dict[str, str] = {}  # hash -> chunk_id
        doc_chunk_tokens: Dict[str, int] = {}

        for c in chunks:
            # 1. Check non-empty content
            if not c.content or not c.content.strip():
                report.empty_chunks += 1
                report.details.append(f"Empty content in chunk: {c.chunk_id}")
                continue

            # 2. Check essential identifiers
            if not c.chunk_id or not c.document_id:
                report.details.append(f"Missing ID in chunk: {c.chunk_id} / doc: {c.document_id}")

            # 3. Check token count
            tok = c.token_count if c.token_count > 0 else count_tokens(c.content)
            token_counts.append(tok)
            doc_chunk_tokens[c.document_id] = doc_chunk_tokens.get(c.document_id, 0) + tok

            # 4. Check section metadata
            if not c.section:
                report.missing_section_metadata += 1

            # 5. Check for accidental HTML fragments
            if re.search(r"<(?:html|body|script|style|div|span|p|a)\b", c.content, re.IGNORECASE):
                report.details.append(f"Uncleaned HTML tag found in chunk: {c.chunk_id}")

            # 6. Duplicate check (within same document or cross-document)
            norm_hash = hashlib.sha256(self._normalize_for_hash(c.content).encode("utf-8")).hexdigest()
            if norm_hash in seen_hashes:
                report.duplicate_chunks += 1
                report.details.append(f"Duplicate chunk detected: {c.chunk_id} matches {seen_hashes[norm_hash]}")
            else:
                seen_hashes[norm_hash] = c.chunk_id

        # 7. Sizing statistics
        if token_counts:
            report.min_tokens = min(token_counts)
            report.max_tokens = max(token_counts)
            report.avg_tokens_per_chunk = sum(token_counts) / len(token_counts)

        # 8. Content loss check against original documents (if provided)
        if original_docs:
            for doc_id, orig_doc in original_docs.items():
                orig_tokens = count_tokens(orig_doc.content)
                chunk_tokens = doc_chunk_tokens.get(doc_id, 0)
                # If chunk tokens is less than 85% of original document, flag content loss
                if orig_tokens > 100 and chunk_tokens < (orig_tokens * 0.85):
                    report.content_loss_warnings += 1
                    report.details.append(
                        f"Potential content loss in doc {doc_id[:8]}... (Orig: {orig_tokens} tokens, Chunks: {chunk_tokens} tokens)"
                    )

        # 9. Determine overall status
        if report.empty_chunks > 0 or (token_counts and report.min_tokens == 0):
            report.status = "FAIL"
        elif report.content_loss_warnings > 0 or report.duplicate_chunks > 5:
            report.status = "WARNING"
        else:
            report.status = "PASS"

        return report


def validate_chunks(
    chunks: List[DocumentChunk],
    original_docs: Optional[Dict[str, RegulatoryDocument]] = None
) -> ChunkQualityReport:
    """Convenience wrapper for chunk validation."""
    validator = ChunkValidator()
    return validator.validate_chunks(chunks, original_docs=original_docs)


def load_all_chunks(chunks_dir: Optional[Path] = None) -> List[DocumentChunk]:
    """Loads all chunk JSON files from data/processed/chunks/."""
    c_dir = chunks_dir or settings.chunks_data_dir
    chunk_files = list(c_dir.glob("*_chunks.json"))
    
    all_chunks: List[DocumentChunk] = []
    for cf in chunk_files:
        try:
            with open(cf, "r", encoding="utf-8") as f:
                data = json.load(f)
            chunks_list = data.get("chunks", [])
            for c_dict in chunks_list:
                all_chunks.append(from_mongo(DocumentChunk, c_dict))
        except Exception as e:
            logger.error(f"Error reading chunk file {cf.name}: {e}")

    return all_chunks


def load_all_processed_documents(processed_dir: Optional[Path] = None) -> Dict[str, RegulatoryDocument]:
    """Loads all original processed document files for content fidelity verification."""
    p_dir = processed_dir or settings.processed_data_dir
    doc_files = [p for p in p_dir.glob("*.json") if not p.name.endswith("_chunks.json") and p.is_file()]

    docs: Dict[str, RegulatoryDocument] = {}
    for df in doc_files:
        try:
            with open(df, "r", encoding="utf-8") as f:
                data = json.load(f)
            doc = from_mongo(RegulatoryDocument, data)
            docs[doc.document_id] = doc
        except Exception as e:
            logger.error(f"Error reading document file {df.name}: {e}")

    return docs


def inspect_sample_chunks(chunks: List[DocumentChunk], sample_count: int = 5):
    """Prints formatted sample chunks for manual inspection."""
    if not chunks:
        print("No chunks available for inspection.")
        return

    print("\n" + "=" * 50)
    print(f"Sample Chunks Inspection ({min(sample_count, len(chunks))} samples)")
    print("=" * 50)

    for i, chunk in enumerate(chunks[:sample_count], start=1):
        print(f"\n[Sample {i}]")
        print(f"Chunk ID    : {safe_str(chunk.chunk_id)}")
        print(f"Document    : {safe_str(chunk.title)} ({chunk.source})")
        print(f"Section     : {safe_str(chunk.section) if chunk.section else 'General'}")
        print(f"Category    : {safe_str(chunk.category) if chunk.category else 'None'}")
        print(f"Token count : {chunk.token_count}")
        snippet = chunk.content.replace("\n", " ")[:200]
        print(f"Content     : {safe_str(snippet)}...")
        print("-" * 50)


def main():
    chunks = load_all_chunks()
    if not chunks:
        print("No chunks found in data/processed/chunks/. Run chunker first (python -m app.ingestion.chunker)")
        return

    original_docs = load_all_processed_documents()
    report = validate_chunks(chunks, original_docs=original_docs)
    report.print_report()
    inspect_sample_chunks(chunks, sample_count=5)


if __name__ == "__main__":
    main()
