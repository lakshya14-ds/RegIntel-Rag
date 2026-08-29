"""
Automated Regulatory Document Ingestion Pipeline.

Orchestrates end-to-end incremental ingestion:
Discovery -> Canonicalization -> Content Hashing -> Change/Delta Detection ->
Cleaning -> Metadata Extraction -> Version Tracking -> Structure-Aware Chunking ->
Chunk Quality Validation -> Gemini Embedding Generation (with unchanged chunk caching) -> Persistence.
"""

import sys
import json
import logging
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings
from app.ingestion.models import (
    RegulatoryDocument,
    DocumentMetadata,
    DocumentChunk,
    canonicalize_url,
    generate_document_id
)
from app.ingestion.cleaner import clean_markdown
from app.ingestion.metadata import extract_document_metadata
from app.ingestion.chunker import chunk_document
from app.ingestion.chunk_validator import validate_chunks
from app.ingestion.version_tracker import VersionTracker
from app.ingestion.repository import DocumentRepository
from app.rag.embeddings import GeminiEmbeddingService

logger = logging.getLogger("regintel.ingestion")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def compute_content_hash(text: str) -> str:
    """Computes deterministic SHA-256 hash of normalized text content."""
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class IngestionPipeline:
    """
    Incremental, structure-aware, and version-tracking document ingestion orchestrator.
    """

    def __init__(
        self,
        repository: Optional[DocumentRepository] = None,
        embedding_service: Optional[GeminiEmbeddingService] = None,
        version_tracker: Optional[VersionTracker] = None
    ):
        self.repository = repository or DocumentRepository()
        self.embedding_service = embedding_service or GeminiEmbeddingService()
        self.version_tracker = version_tracker or VersionTracker(repository=self.repository)

    def _load_stored_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Checks local filesystem and MongoDB for existing document record."""
        local_path = settings.processed_data_dir / f"{document_id}.json"
        if local_path.exists():
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        try:
            doc = self.repository.get_document(document_id)
            if doc:
                return doc.model_dump()
        except Exception:
            pass
        return None

    def _load_stored_chunk_hashes(self, document_id: str) -> Dict[str, Dict[str, Any]]:
        """Loads existing chunks for a document to check for unchanged chunk content hashes."""
        chunk_map: Dict[str, Dict[str, Any]] = {}
        # From local chunks dir
        chunk_file = settings.chunks_data_dir / f"{document_id}_chunks.json"
        if chunk_file.exists():
            try:
                with open(chunk_file, "r", encoding="utf-8") as f:
                    chunks_data = json.load(f)
                    for c in chunks_data:
                        cid = c.get("chunk_id")
                        if cid:
                            chunk_map[cid] = c
            except Exception:
                pass
        return chunk_map

    def discover_candidates(self, source: str = "sebi", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Discovers candidate documents using raw corpus / scraper artifacts.
        """
        candidates: List[Dict[str, Any]] = []

        # Read raw data directory
        if settings.raw_data_dir.exists():
            for f in sorted(settings.raw_data_dir.glob("*.json")):
                try:
                    with open(f, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and item.get("url"):
                                    candidates.append(item)
                        elif isinstance(data, dict) and data.get("url"):
                            candidates.append(data)
                except Exception as e:
                    logger.warning(f"Error reading raw candidate file {f.name}: {e}")

        # Deduplicate candidates by canonical URL
        seen_urls = set()
        unique_candidates = []
        for c in candidates:
            c_url = canonicalize_url(c.get("url", ""))
            if c_url and c_url not in seen_urls:
                seen_urls.add(c_url)
                unique_candidates.append(c)

        if limit and limit > 0:
            return unique_candidates[:limit]
        return unique_candidates

    def run(
        self,
        source: str = "sebi",
        limit: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Executes the ingestion run with deduplication, change detection, and metrics tracking.
        """
        logger.info(f"Starting Ingestion Run | Source: {source.upper()} | Limit: {limit} | Dry Run: {dry_run}")

        candidates = self.discover_candidates(source=source, limit=limit)
        logger.info(f"Discovered {len(candidates)} unique candidate documents.")

        stats = {
            "discovered": len(candidates),
            "new": 0,
            "updated": 0,
            "unchanged": 0,
            "failed": 0,
            "duplicates": 0,
            "documents_chunked": 0,
            "new_chunks": 0,
            "updated_chunks": 0,
            "embeddings_generated": 0,
            "embeddings_skipped": 0,
            "version_relationships_created": 0,
            "failures": []
        }

        for idx, item in enumerate(candidates, start=1):
            url = item.get("url", "")
            title = item.get("title", "")
            raw_content = item.get("content") or item.get("markdown", "")

            if not url or not raw_content:
                stats["failed"] += 1
                stats["failures"].append({"url": url, "stage": "discovery", "error": "Missing URL or content"})
                continue

            doc_id = generate_document_id(source=source.upper(), url=url)
            cleaned_content = clean_markdown(raw_content)
            new_hash = compute_content_hash(cleaned_content)

            existing_doc = self._load_stored_document(doc_id)

            if existing_doc:
                old_hash = existing_doc.get("content_hash") or existing_doc.get("metadata", {}).get("content_hash")
                if not old_hash:
                    old_hash = compute_content_hash(existing_doc.get("content", ""))

                if old_hash == new_hash:
                    # Unchanged content
                    stats["unchanged"] += 1
                    if dry_run:
                        logger.info(f"[DRY RUN] UNCHANGED: {title or doc_id[:16]} ({url})")
                    continue
                else:
                    # Changed content -> update
                    doc_status_type = "CHANGED"
                    stats["updated"] += 1
            else:
                doc_status_type = "NEW"
                stats["new"] += 1

            if dry_run:
                logger.info(f"[DRY RUN] {doc_status_type}: {title or doc_id[:16]} ({url})")
                continue

            # Full ingestion processing
            try:
                # 1. Metadata extraction
                meta_dict = extract_document_metadata(raw_content, url=url, source=source.upper())
                meta_dict["content_hash"] = new_hash
                meta_dict["document_version"] = "1.1" if doc_status_type == "CHANGED" else "1.0"

                metadata_obj = DocumentMetadata(
                    document_type=meta_dict.get("document_type"),
                    category=meta_dict.get("category"),
                    circular_number=meta_dict.get("circular_number"),
                    published_date=meta_dict.get("published_date"),
                    effective_date=meta_dict.get("effective_date"),
                    section=meta_dict.get("section"),
                    status="current",
                    content_hash=new_hash,
                    document_version=meta_dict["document_version"]
                )

                # 2. Construct RegulatoryDocument
                reg_doc = RegulatoryDocument(
                    document_id=doc_id,
                    url=url,
                    title=title or meta_dict.get("title", f"Regulatory Notice {doc_id[:8]}"),
                    source=source.upper(),
                    document_type=metadata_obj.document_type,
                    category=metadata_obj.category,
                    circular_number=metadata_obj.circular_number,
                    published_date=metadata_obj.published_date,
                    effective_date=metadata_obj.effective_date,
                    section=metadata_obj.section,
                    status=metadata_obj.status,
                    content_hash=new_hash,
                    document_version=metadata_obj.document_version,
                    content=cleaned_content,
                    metadata=metadata_obj
                )

                # 3. Structure-aware chunking
                chunks: List[DocumentChunk] = chunk_document(reg_doc)
                if not chunks:
                    logger.warning(f"No chunks generated for {doc_id}.")
                    stats["failed"] += 1
                    stats["failures"].append({"url": url, "stage": "chunk", "error": "Zero chunks produced"})
                    continue

                stats["documents_chunked"] += 1

                # 4. Chunk validation
                val_report = validate_chunks(chunks)
                if not val_report.get("is_valid", True):
                    logger.warning(f"Chunk quality warning for {doc_id}: {val_report.get('warnings')}")

                # 5. Embeddings generation with chunk hash cache
                existing_chunks_map = self._load_stored_chunk_hashes(doc_id)
                chunks_to_embed: List[DocumentChunk] = []

                for chunk in chunks:
                    chunk.content_hash = compute_content_hash(chunk.content)
                    cached_chunk = existing_chunks_map.get(chunk.chunk_id)

                    if (
                        cached_chunk and
                        cached_chunk.get("content_hash") == chunk.content_hash and
                        cached_chunk.get("embedding") and
                        len(cached_chunk["embedding"]) == settings.embedding_dimension
                    ):
                        # Reuse cached embedding
                        chunk.embedding = cached_chunk["embedding"]
                        chunk.embedding_model = cached_chunk.get("embedding_model", settings.embedding_model)
                        chunk.embedding_dimensions = len(chunk.embedding)
                        stats["embeddings_skipped"] += 1
                    else:
                        chunks_to_embed.append(chunk)

                if chunks_to_embed:
                    logger.info(f"Generating embeddings for {len(chunks_to_embed)} new/modified chunks of {doc_id}...")
                    embedded_chunks = self.embedding_service.embed_chunks_batch(chunks_to_embed)
                    stats["embeddings_generated"] += len(embedded_chunks)
                    if doc_status_type == "NEW":
                        stats["new_chunks"] += len(chunks)
                    else:
                        stats["updated_chunks"] += len(chunks_to_embed)
                else:
                    stats["embeddings_skipped"] += len(chunks)

                # 6. Resolve version relationships
                version_info = self.version_tracker.resolve_document_relationships(doc_id)
                reg_doc.supersedes = version_info.get("predecessor_id")
                reg_doc.superseded_by = version_info.get("successor_id")
                reg_doc.predecessor_candidates = version_info.get("predecessor_candidates", [])
                reg_doc.relationship_confidence = version_info.get("relationship_confidence")
                reg_doc.relationship_type = version_info.get("relationship_type")
                reg_doc.status = version_info.get("status", "current")

                if reg_doc.supersedes:
                    stats["version_relationships_created"] += 1

                # 7. Persist document & chunks
                # Local JSON fallback files
                doc_file = settings.processed_data_dir / f"{doc_id}.json"
                with open(doc_file, "w", encoding="utf-8") as df:
                    json.dump(reg_doc.model_dump(), df, indent=2, ensure_ascii=False)

                chunk_file = settings.chunks_data_dir / f"{doc_id}_chunks.json"
                with open(chunk_file, "w", encoding="utf-8") as cf:
                    json.dump([c.model_dump() for c in chunks], cf, indent=2, ensure_ascii=False)

                # MongoDB persistence (graceful fallback)
                try:
                    self.repository.save_document(reg_doc)
                    self.repository.save_chunks(chunks)
                except Exception as me:
                    logger.warning(f"MongoDB persistence unavailable during ingestion ({me}). Local store updated.")

            except Exception as e:
                logger.error(f"Error processing document {url}: {e}", exc_info=True)
                stats["failed"] += 1
                stats["failures"].append({"url": url, "stage": "processing", "error": str(e)})

        self._print_ingestion_report(stats, dry_run=dry_run)
        return stats

    def _print_ingestion_report(self, stats: Dict[str, Any], dry_run: bool = False):
        """Prints the structured Ingestion Report."""
        prefix = "[DRY RUN] " if dry_run else ""
        print("\n" + "=" * 65)
        print(f"{prefix}INGESTION REPORT")
        print("=" * 65)
        print(f"Discovered Documents        : {stats['discovered']}")
        print(f"New Documents               : {stats['new']}")
        print(f"Updated Documents           : {stats['updated']}")
        print(f"Unchanged Documents         : {stats['unchanged']}")
        print(f"Failed Documents            : {stats['failed']}")
        print(f"Duplicates Skipped          : {stats['duplicates']}")
        print("-" * 65)
        print(f"Documents Chunked           : {stats['documents_chunked']}")
        print(f"New Chunks Created          : {stats['new_chunks']}")
        print(f"Updated Chunks              : {stats['updated_chunks']}")
        print(f"Embeddings Generated        : {stats['embeddings_generated']}")
        print(f"Embeddings Skipped (Cached) : {stats['embeddings_skipped']}")
        print(f"Version Links Created       : {stats['version_relationships_created']}")
        print("=" * 65)
        if stats["failures"]:
            print(f"Failures ({len(stats['failures'])}):")
            for f in stats["failures"][:5]:
                print(f"  - [{f['stage']}] {f['url']}: {f['error']}")
            print("=" * 65)
        print()


def main():
    parser = argparse.ArgumentParser(description="RegIntel Automated Document Ingestion Pipeline")
    parser.add_argument("--source", default="sebi", help="Regulatory source authority (e.g. sebi)")
    parser.add_argument("--limit", type=int, default=None, help="Maximum candidate documents to process")
    parser.add_argument("--dry-run", action="store_true", help="Inspect candidate changes without writing to DB")

    args = parser.parse_args()
    pipeline = IngestionPipeline()
    pipeline.run(source=args.source, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
