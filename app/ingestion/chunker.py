"""
Structure-Aware Regulatory Document Chunker.

Preserves legal/regulatory hierarchy (Chapters, Sections, Subsections, Clauses, Bullet points)
and enriches chunks with parent section metadata and deterministic chunk IDs.

Tokenizer note: Uses tiktoken (cl100k_base encoding) for reliable, fast token sizing.
"""

import os
import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Union

import tiktoken

from app.config import settings
from app.ingestion.models import RegulatoryDocument, DocumentChunk, from_mongo

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Global tokenizer instance (cl100k_base provides consistent token sizing for modern LLMs)
_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """
    Counts tokens for the given text using tiktoken cl100k_base encoding.
    Used for structure-aware boundary calculations and chunk sizing.
    """
    if not text:
        return 0
    return len(_ENCODING.encode(text, disallowed_special=()))


@dataclass
class ChunkerConfig:
    """Configurable sizing parameters for regulatory document chunking."""
    target_chunk_tokens: int = settings.target_chunk_tokens
    max_chunk_tokens: int = settings.max_chunk_tokens
    min_chunk_tokens: int = settings.min_chunk_tokens
    overlap_tokens: int = settings.overlap_tokens


# Regular expressions for detecting regulatory section boundaries
SECTION_PATTERNS = [
    # Markdown Headings (# Header, ## Header, ### Header)
    r"^(#{1,4}\s+.+)$",
    # Chapter / Part / Schedule headers (e.g., Chapter I, Part A, Schedule II)
    r"^(?:CHAPTER|PART|SCHEDULE|ANNEXURE|APPENDIX)\s+[IVXLCDM0-9A-Z]+(?:\s*[-–—:]\s*.+)?$",
    # Numbered clauses/sections (e.g., 1. Background, 4.2 Eligibility Requirements, 12.3.1 ...)
    r"^(?:\d+\.|\d+\.\d+|\d+\.\d+\.\d+)\s+[A-Z].*$",
]


def is_section_header(line: str) -> bool:
    """Checks if a single line represents a regulatory section heading."""
    line_clean = line.strip()
    if not line_clean or len(line_clean) > 200:
        return False
    for pat in SECTION_PATTERNS:
        if re.match(pat, line_clean, re.IGNORECASE):
            return True
    return False


def build_embedding_text(title: Optional[str], section: Optional[str], source: str, content: str) -> str:
    """
    Builds context-enriched text for embedding generation while preserving
    clean original content separately.
    """
    header_parts = []
    if title:
        header_parts.append(f"Title: {title.strip()}")
    if section:
        header_parts.append(f"Section: {section.strip()}")
    header_parts.append(f"Source: {source.strip()}")

    header_str = "\n".join(header_parts)
    return f"{header_str}\n\nContent:\n{content.strip()}"


class RegulatoryChunker:
    """
    Structure-aware chunker tailored for SEBI and regulatory documents.
    Preserves section headers, paragraph boundaries, and list structures.
    """

    def __init__(self, config: Optional[ChunkerConfig] = None, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        if config:
            self.config = config
        else:
            c = ChunkerConfig()
            if chunk_size:
                c.target_chunk_tokens = chunk_size
                c.max_chunk_tokens = int(chunk_size * 1.25)
            if chunk_overlap:
                c.overlap_tokens = chunk_overlap
            self.config = c

    def _split_into_sections(self, text: str) -> List[Tuple[Optional[str], str]]:
        """
        Splits raw text into logical section units (heading, body_text).
        """
        lines = text.split("\n")
        sections: List[Tuple[Optional[str], str]] = []
        current_heading: Optional[str] = None
        current_lines: List[str] = []

        for line in lines:
            if is_section_header(line):
                if current_lines:
                    body = "\n".join(current_lines).strip()
                    if body:
                        sections.append((current_heading, body))
                    current_lines = []
                current_heading = re.sub(r"^#+\s*", "", line).strip()
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_heading, body))

        if not sections and text.strip():
            sections.append((None, text.strip()))

        return sections

    def _split_oversized_text(self, text: str, max_tokens: int, overlap_tokens: int) -> List[str]:
        """
        Recursively splits an oversized text block into smaller paragraph/sentence/word units with overlap,
        strictly respecting max_tokens.
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        atomic_units: List[str] = []
        for p in paragraphs:
            p_tokens = count_tokens(p)
            if p_tokens <= max_tokens:
                atomic_units.append(p)
            else:
                lines_or_sentences = re.split(r"(?<=[.?!;])\s+|\n+", p)
                for item in lines_or_sentences:
                    item = item.strip()
                    if not item:
                        continue
                    item_tok = count_tokens(item)
                    if item_tok <= max_tokens:
                        atomic_units.append(item)
                    else:
                        words = item.split()
                        sub_word_acc = []
                        sub_len = 0
                        for w in words:
                            w_tok = count_tokens(w + " ")
                            if sub_len + w_tok > max_tokens and sub_word_acc:
                                atomic_units.append(" ".join(sub_word_acc))
                                sub_word_acc = [w]
                                sub_len = w_tok
                            else:
                                sub_word_acc.append(w)
                                sub_len += w_tok
                        if sub_word_acc:
                            atomic_units.append(" ".join(sub_word_acc))

        chunks: List[str] = []
        current_units: List[str] = []
        current_tokens = 0

        for unit in atomic_units:
            unit_tokens = count_tokens(unit)
            if current_tokens + unit_tokens > max_tokens and current_units:
                chunk_str = "\n\n".join(current_units).strip()
                if chunk_str:
                    chunks.append(chunk_str)
                overlap_units = []
                accumulated = 0
                for u in reversed(current_units):
                    u_tok = count_tokens(u)
                    if accumulated + u_tok <= overlap_tokens:
                        overlap_units.insert(0, u)
                        accumulated += u_tok
                    else:
                        break
                current_units = overlap_units + [unit]
                current_tokens = sum(count_tokens(u) for u in current_units)
            else:
                current_units.append(unit)
                current_tokens += unit_tokens

        if current_units:
            chunk_str = "\n\n".join(current_units).strip()
            if chunk_str:
                chunks.append(chunk_str)

        return chunks

    def chunk_document(self, document: Union[RegulatoryDocument, str], metadata: Optional[Dict[str, Any]] = None) -> Any:
        """
        Converts a RegulatoryDocument into a sequence of structure-aware DocumentChunks.
        Also supports string input with metadata dict for compatibility.
        """
        if isinstance(document, str):
            meta = metadata or {}
            doc_id = meta.get("document_id", "doc_001")
            raw_chunks = self._split_oversized_text(document, self.config.target_chunk_tokens, self.config.overlap_tokens)
            result = []
            for idx, c_text in enumerate(raw_chunks):
                cid = f"{doc_id}_chunk_{idx:04d}"
                result.append({
                    "chunk_id": cid,
                    "chunk_index": idx,
                    "document_id": doc_id,
                    "text": c_text,
                    "metadata": {**meta, "chunk_id": cid, "chunk_index": idx}
                })
            return result

        raw_sections = self._split_into_sections(document.content)
        intermediate_chunks: List[Tuple[Optional[str], str]] = []

        # 1. Process each section according to token boundaries
        for heading, section_text in raw_sections:
            sec_tokens = count_tokens(section_text)
            if sec_tokens <= self.config.max_chunk_tokens:
                intermediate_chunks.append((heading, section_text))
            else:
                sub_chunks = self._split_oversized_text(
                    text=section_text,
                    max_tokens=self.config.target_chunk_tokens,
                    overlap_tokens=self.config.overlap_tokens
                )
                for sub in sub_chunks:
                    intermediate_chunks.append((heading, sub))

        # 2. Merge undersized adjacent chunks when compatible
        merged_chunks: List[Tuple[Optional[str], str]] = []
        i = 0
        while i < len(intermediate_chunks):
            current_heading, current_text = intermediate_chunks[i]
            current_toks = count_tokens(current_text)

            if current_toks < self.config.min_chunk_tokens and i + 1 < len(intermediate_chunks):
                next_heading, next_text = intermediate_chunks[i + 1]
                combined_text = f"{current_text}\n\n{next_text}".strip()
                combined_toks = count_tokens(combined_text)

                if combined_toks <= self.config.max_chunk_tokens:
                    merged_heading = current_heading or next_heading
                    merged_chunks.append((merged_heading, combined_text))
                    i += 2
                    continue

            merged_chunks.append((current_heading, current_text))
            i += 1

        # 3. Create final DocumentChunk models with deterministic IDs
        document_chunks: List[DocumentChunk] = []
        for idx, (heading, chunk_content) in enumerate(merged_chunks):
            chunk_content = chunk_content.strip()
            if not chunk_content:
                continue

            tok_count = count_tokens(chunk_content)
            chunk_id = f"{document.document_id}_chunk_{idx:04d}"
            
            emb_text = build_embedding_text(
                title=document.title,
                section=heading,
                source=document.source,
                content=chunk_content
            )

            chunk = DocumentChunk(
                chunk_id=chunk_id,
                document_id=document.document_id,
                chunk_index=idx,
                content=chunk_content,
                title=document.title,
                section=heading,
                source=document.source,
                document_type=document.document_type,
                category=document.category,
                circular_number=document.circular_number,
                published_date=document.published_date,
                effective_date=document.effective_date,
                url=document.url,
                token_count=tok_count,
                embedding_text=emb_text,
                embedding=None,
                embedding_model=None,
                embedding_dimensions=None
            )
            document_chunks.append(chunk)

        return document_chunks


# Backward compatibility alias
DocumentChunker = RegulatoryChunker

# Convenience module-level API
_default_chunker = RegulatoryChunker()


def chunk_document(document: RegulatoryDocument, config: Optional[ChunkerConfig] = None) -> List[DocumentChunk]:
    """Chunk a single RegulatoryDocument into DocumentChunks."""
    chunker = RegulatoryChunker(config) if config else _default_chunker
    return chunker.chunk_document(document)


def chunk_documents(documents: List[RegulatoryDocument], config: Optional[ChunkerConfig] = None) -> List[DocumentChunk]:
    """Chunk a list of RegulatoryDocuments into DocumentChunks."""
    chunker = RegulatoryChunker(config) if config else _default_chunker
    all_chunks = []
    for doc in documents:
        all_chunks.extend(chunker.chunk_document(doc))
    return all_chunks


def save_chunks_to_file(chunks: List[DocumentChunk], output_dir: Optional[Path] = None) -> Dict[str, Path]:
    """
    Saves chunks grouped by document_id into data/processed/chunks/<document_id>_chunks.json.
    """
    target_dir = output_dir or settings.chunks_data_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    grouped: Dict[str, List[DocumentChunk]] = {}
    for c in chunks:
        grouped.setdefault(c.document_id, []).append(c)

    saved_files: Dict[str, Path] = {}
    for doc_id, doc_chunks in grouped.items():
        doc_chunks.sort(key=lambda x: x.chunk_index)
        payload = {
            "document_id": doc_id,
            "chunk_count": len(doc_chunks),
            "chunks": [c.model_dump() for c in doc_chunks]
        }
        file_path = target_dir / f"sebi_{doc_id}_chunks.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        saved_files[doc_id] = file_path

    return saved_files


def run_chunking_pipeline(processed_dir: Optional[Path] = None, output_dir: Optional[Path] = None) -> List[DocumentChunk]:
    """
    Loads all processed JSON documents from data/processed/, chunks them,
    and writes the chunk files to data/processed/chunks/.
    """
    in_dir = processed_dir or settings.processed_data_dir
    out_dir = output_dir or settings.chunks_data_dir

    json_files = [p for p in in_dir.glob("*.json") if not p.name.endswith("_chunks.json") and p.is_file()]
    logger.info(f"Discovered {len(json_files)} processed documents for chunking in {in_dir}")

    all_chunks: List[DocumentChunk] = []
    docs_processed = 0

    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            doc = from_mongo(RegulatoryDocument, data)
            chunks = chunk_document(doc)
            all_chunks.extend(chunks)
            docs_processed += 1
        except Exception as e:
            logger.error(f"Failed to chunk document from {jf.name}: {e}")

    saved_files = save_chunks_to_file(all_chunks, output_dir=out_dir)
    
    total_tokens = sum(c.token_count for c in all_chunks)
    avg_tokens = total_tokens / len(all_chunks) if all_chunks else 0
    min_tokens = min((c.token_count for c in all_chunks), default=0)
    max_tokens = max((c.token_count for c in all_chunks), default=0)

    print("\n" + "=" * 40)
    print("Chunking Pipeline Summary")
    print("-" * 40)
    print(f"Documents processed : {docs_processed}")
    print(f"Total chunks created: {len(all_chunks)}")
    print(f"Average tokens/chunk: {avg_tokens:.1f}")
    print(f"Min tokens / chunk  : {min_tokens}")
    print(f"Max tokens / chunk  : {max_tokens}")
    print(f"Chunk files saved to: {out_dir}")
    print("=" * 40 + "\n")

    return all_chunks


if __name__ == "__main__":
    run_chunking_pipeline()
