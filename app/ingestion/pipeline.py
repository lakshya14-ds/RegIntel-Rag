"""
Automated Regulatory Document Ingestion Pipeline.

Orchestrates end-to-end incremental ingestion:
Discovery -> Canonicalization -> Deduplication -> Check Database -> Crawl ->
Cleaning -> Metadata Extraction -> Content Hash -> Classify -> Chunk ->
Chunk Hash -> Embed only new/changed chunks -> Persist -> Version Tracking -> Report.
"""

import sys
import json
import logging
import hashlib
import argparse
from datetime import datetime
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
        for candidate_name in [f"{document_id}.json", f"sebi_{document_id}.json"]:
            local_path = settings.processed_data_dir / candidate_name
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
        for chunk_name in [f"{document_id}_chunks.json", f"sebi_{document_id}_chunks.json"]:
            chunk_file = settings.chunks_data_dir / chunk_name
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

    def discover_candidates(self, source: str = "sebi", limit: Optional[int] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Discovers candidate documents using raw corpus / scraper artifacts.
        Returns (unique_candidates, duplicate_count).
        """
        raw_candidates: List[Dict[str, Any]] = []

        if settings.raw_data_dir.exists():
            for f in sorted(settings.raw_data_dir.glob("*.json")):
                try:
                    with open(f, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and item.get("url"):
                                    raw_candidates.append(item)
                        elif isinstance(data, dict) and data.get("url"):
                            raw_candidates.append(data)
                except Exception as e:
                    logger.warning(f"Error reading raw candidate file {f.name}: {e}")

        # Deduplicate candidates by canonical URL
        seen_urls = set()
        unique_candidates = []
        duplicate_count = 0
        for c in raw_candidates:
            c_url = canonicalize_url(c.get("url", ""))
            if not c_url:
                continue
            if c_url in seen_urls:
                duplicate_count += 1
            else:
                seen_urls.add(c_url)
                unique_candidates.append(c)

        if limit and limit > 0:
            return unique_candidates[:limit], duplicate_count
        return unique_candidates, duplicate_count

    def run(
        self,
        source: str = "sebi",
        limit: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Executes the ingestion run with deduplication, change detection, and metrics tracking.
        """
        run_id = f"ingest_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.utcnow().isoformat()

        logger.info(f"Starting Ingestion Run '{run_id}' | Source: {source.upper()} | Limit: {limit} | Dry Run: {dry_run}")

        res = self.discover_candidates(source=source, limit=limit)
        if isinstance(res, tuple) and len(res) == 2:
            candidates, duplicate_count = res
        elif isinstance(res, list):
            candidates = res
            duplicate_count = 0
        else:
            candidates = []
            duplicate_count = 0

        logger.info(f"Discovered {len(candidates)} unique candidates ({duplicate_count} duplicates).")

        stats = {
            "run_id": run_id,
            "source": source.upper(),
            "started_at": start_time,
            "finished_at": None,
            "discovered": len(candidates),
            "new": 0,
            "updated": 0,
            "unchanged": 0,
            "failed": 0,
            "duplicates": duplicate_count,
            "documents_chunked": 0,
            "new_chunks": 0,
            "updated_chunks": 0,
            "embeddings_generated": 0,
            "embeddings_skipped": 0,
            "embeddings_failed": 0,
            "version_relationships_created": 0,
            "failures": []
        }

        for idx, item in enumerate(candidates, start=1):
            if isinstance(item, dict):
                url = item.get("url", "")
                title = item.get("title", "")
                raw_content = item.get("content") or item.get("markdown", "")
            elif isinstance(item, str):
                url = item
                title = ""
                raw_content = ""
            else:
                url = ""
                title = ""
                raw_content = ""

            if not url or not raw_content:
                stats["failed"] += 1
                stats["failures"].append({
                    "run_id": run_id,
                    "url": url,
                    "stage": "discovery",
                    "error_type": "MissingData",
                    "message": "Missing URL or raw markdown content"
                })
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
                    stats["failures"].append({
                        "run_id": run_id,
                        "url": url,
                        "stage": "chunking",
                        "error_type": "ZeroChunks",
                        "message": "Zero chunks produced by structure-aware chunker"
                    })
                    continue

                stats["documents_chunked"] += 1

                # 4. Chunk validation
                val_report = validate_chunks(chunks)
                if hasattr(val_report, "status") and val_report.status == "FAIL":
                    logger.warning(f"Chunk quality FAIL for {doc_id}: {getattr(val_report, 'details', [])}")
                elif isinstance(val_report, dict) and not val_report.get("is_valid", True):
                    logger.warning(f"Chunk quality warning for {doc_id}: {val_report.get('warnings')}")

                # 5. Embeddings generation with chunk hash cache
                existing_chunks_map = self._load_stored_chunk_hashes(doc_id)
                existing_hash_map = {
                    c.get("content_hash"): c
                    for c in existing_chunks_map.values()
                    if c.get("content_hash") and c.get("embedding")
                }
                chunks_to_embed: List[DocumentChunk] = []

                for chunk in chunks:
                    chunk.content_hash = compute_content_hash(chunk.content)
                    cached_chunk = existing_chunks_map.get(chunk.chunk_id) or existing_hash_map.get(chunk.content_hash)

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
                    try:
                        embedded_chunks = self.embedding_service.embed_chunks_batch(chunks_to_embed)
                        stats["embeddings_generated"] += len(embedded_chunks)
                    except Exception as emb_err:
                        logger.error(f"Embedding error for {doc_id}: {emb_err}")
                        stats["embeddings_failed"] += len(chunks_to_embed)
                        stats["failures"].append({
                            "run_id": run_id,
                            "url": url,
                            "stage": "embedding",
                            "error_type": "EmbeddingFailure",
                            "message": str(emb_err)
                        })

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
                # Local JSON files
                doc_file = settings.processed_data_dir / f"sebi_{doc_id}.json"
                with open(doc_file, "w", encoding="utf-8") as df:
                    json.dump(reg_doc.model_dump(), df, indent=2, ensure_ascii=False)

                chunk_file = settings.chunks_data_dir / f"sebi_{doc_id}_chunks.json"
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
                stats["failures"].append({
                    "run_id": run_id,
                    "url": url,
                    "stage": "processing",
                    "error_type": type(e).__name__,
                    "message": str(e)
                })

        stats["finished_at"] = datetime.utcnow().isoformat()

        # Save failure and run log artifacts
        self._save_run_logs(stats, dry_run=dry_run)
        self._print_ingestion_report(stats, dry_run=dry_run)

        return stats

    def _save_run_logs(self, stats: Dict[str, Any], dry_run: bool = False) -> None:
        """Saves ingestion run logs and failure records."""
        if dry_run:
            return

        # 1. Failures log
        if stats["failures"]:
            fail_path = Path(__file__).resolve().parent.parent.parent / "evaluation" / "results" / "ingestion_failures.json"
            fail_path.parent.mkdir(parents=True, exist_ok=True)
            existing_fails = []
            if fail_path.exists():
                try:
                    with open(fail_path, "r", encoding="utf-8") as f:
                        existing_fails = json.load(f)
                except Exception:
                    pass
            existing_fails.extend(stats["failures"])
            try:
                with open(fail_path, "w", encoding="utf-8") as f:
                    json.dump(existing_fails, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to write ingestion failures log: {e}")

        # 2. Ingestion Run record
        run_record = {
            "run_id": stats["run_id"],
            "source": stats["source"],
            "started_at": stats["started_at"],
            "finished_at": stats["finished_at"],
            "discovered": stats["discovered"],
            "new": stats["new"],
            "changed": stats["updated"],
            "unchanged": stats["unchanged"],
            "duplicate": stats["duplicates"],
            "failed": stats["failed"],
            "chunks_created": stats["new_chunks"],
            "chunks_reused": stats["embeddings_skipped"],
            "embeddings_created": stats["embeddings_generated"],
            "embeddings_reused": stats["embeddings_skipped"]
        }
        run_log_path = Path(__file__).resolve().parent.parent.parent / "evaluation" / "results" / "ingestion_runs.json"
        run_log_path.parent.mkdir(parents=True, exist_ok=True)
        existing_runs = []
        if run_log_path.exists():
            try:
                with open(run_log_path, "r", encoding="utf-8") as f:
                    existing_runs = json.load(f)
            except Exception:
                pass
        existing_runs.append(run_record)
        try:
            with open(run_log_path, "w", encoding="utf-8") as f:
                json.dump(existing_runs, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write ingestion run log: {e}")

    def _print_ingestion_report(self, stats: Dict[str, Any], dry_run: bool = False):
        """Prints the structured Ingestion Report according to project specification."""
        if dry_run:
            print("\n# INGESTION DRY RUN\n")
            print(f"Discovered: {stats['discovered']}\n")
            print(f"## NEW\n{stats['new']}\n")
            print(f"## CHANGED\n{stats['updated']}\n")
            print(f"## UNCHANGED\n{stats['unchanged']}\n")
            print(f"## DUPLICATE\n{stats['duplicates']}\n")
            print(f"## FAILED\n{stats['failed']}\n")
            print("No database modifications performed.\n")
        else:
            print("\n# INGESTION SUMMARY\n")
            print(f"Source: {stats['source']}\n")
            print(f"Discovered: {stats['discovered']}")
            print(f"Processed: {stats['new'] + stats['updated']}")
            print(f"Unchanged: {stats['unchanged']}")
            print(f"Duplicates: {stats['duplicates']}")
            print(f"Failed: {stats['failed']}\n")
            print("Documents:")
            print(f"New: {stats['new']}")
            print(f"Changed: {stats['updated']}\n")
            print("Chunks:")
            print(f"Created: {stats['new_chunks']}")
            print(f"Reused: {stats['embeddings_skipped']}")
            print(f"Changed: {stats['updated_chunks']}\n")
            print("Embeddings:")
            print(f"Generated: {stats['embeddings_generated']}")
            print(f"Reused: {stats['embeddings_skipped']}")
            print(f"Failed: {stats['embeddings_failed']}\n")
            print("Version relationships:")
            print(f"Created/updated: {stats['version_relationships_created']}\n")


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
