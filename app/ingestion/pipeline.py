"""
Automated Incremental Document Ingestion & Change-Aware Processing Pipeline (Phase 55).

Orchestrates end-to-end regulatory data processing:
1. Discover & Canonicalize URLs
2. Deduplicate Candidates
3. Compare Content Hash (NEW vs. UNCHANGED vs. CHANGED)
4. UNCHANGED: Immediately skip (0 re-chunking, 0 embeddings, 0 version churn)
5. NEW / CHANGED:
   - Structure-aware chunking
   - Chunk-level content hashing
   - Embedding reuse (100% reuse for unchanged chunks with valid 768d vectors)
   - Embed only new/changed chunks via Gemini API
   - Version tracking (predecessor alignment)
   - Change detection (diff analysis for CHANGED documents)
   - Safe persistence to MongoDB repository & local storage
   - Non-destructive missing source handling (SOURCE_MISSING)
   - Comprehensive audit logging and structured reporting
"""

import os
import sys
import math
import json
import logging
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.config import settings
from app.ingestion.models import (
    RegulatoryDocument,
    DocumentMetadata,
    DocumentChunk,
    IngestionRunSummary,
    DocumentProcessingStatus,
    canonicalize_url,
    generate_document_id,
    compute_content_hash
)
from app.ingestion.cleaner import clean_markdown
from app.ingestion.metadata import extract_document_metadata
from app.ingestion.chunker import chunk_document
from app.ingestion.chunk_validator import validate_chunks
from app.ingestion.version_tracker import VersionTracker
from app.ingestion.repository import DocumentRepository
from app.rag.embeddings import GeminiEmbeddingService
from app.change_detection.document_comparator import DocumentComparator
from scraper.sebi_sources import get_curated_documents

logger = logging.getLogger("regintel.ingestion")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


REPORTS_DIR = Path("evaluation/results/ingestion")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def is_valid_embedding(embedding: Any, expected_dim: int = 768) -> bool:
    """
    Validates that an embedding vector is reusable (Phase 55.12).
    - Exists and is list
    - Dimension equals expected_dim (768)
    - All elements numeric finite floats
    - No NaN, no Inf, not all zeros
    """
    if not isinstance(embedding, list) or len(embedding) != expected_dim:
        return False
    for val in embedding:
        if not isinstance(val, (int, float)):
            return False
        if math.isnan(val) or math.isinf(val):
            return False
    if all(val == 0.0 for val in embedding):
        return False
    return True


class IngestionPipeline:
    """
    Production-grade incremental ingestion orchestrator.
    Guarantees idempotency, minimal Gemini API costs, and non-destructive persistence.
    """

    def __init__(
        self,
        repository: Optional[DocumentRepository] = None,
        embedding_service: Optional[GeminiEmbeddingService] = None,
        version_tracker: Optional[VersionTracker] = None,
        comparator: Optional[DocumentComparator] = None
    ):
        self.repository = repository or DocumentRepository()
        self.embedding_service = embedding_service or GeminiEmbeddingService()
        self.version_tracker = version_tracker or VersionTracker(repository=self.repository)
        self.comparator = comparator or DocumentComparator()

    def _load_stored_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Loads existing document record from local files or MongoDB."""
        # 1. Check local processed files
        for candidate_name in [f"{document_id}.json", f"sebi_{document_id}.json"]:
            local_path = settings.processed_data_dir / candidate_name
            if local_path.exists():
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass

        # 2. Check MongoDB
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
                            chash = c.get("content_hash")
                            if cid:
                                chunk_map[cid] = c
                            if chash:
                                chunk_map[chash] = c
                except Exception:
                    pass

        # Also query MongoDB chunks for this document
        try:
            db_chunks = self.repository.get_chunks_by_document(document_id)
            for dc in db_chunks:
                cid = dc.get("chunk_id")
                chash = dc.get("content_hash")
                if cid and cid not in chunk_map:
                    chunk_map[cid] = dc
                if chash and chash not in chunk_map:
                    chunk_map[chash] = dc
        except Exception:
            pass

        return chunk_map

    def discover_candidates(
        self,
        source: str = "sebi",
        limit: Optional[int] = None,
        retry_run_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Discovers candidate documents using raw corpus, scraper artifacts, and curated seeds.
        If retry_run_id is specified, loads failed candidates from that run.
        Returns (unique_candidates, duplicate_count).
        """
        raw_candidates: List[Dict[str, Any]] = []

        # If retrying failed items
        if retry_run_id:
            fail_path = REPORTS_DIR / "failed_items.json"
            if fail_path.exists():
                try:
                    with open(fail_path, "r", encoding="utf-8") as f:
                        all_failures = json.load(f)
                    for item in all_failures:
                        if item.get("run_id") == retry_run_id:
                            raw_candidates.append(item)
                    logger.info(f"Loaded {len(raw_candidates)} failed items for retry from run {retry_run_id}")
                except Exception as e:
                    logger.warning(f"Error loading retry failures: {e}")

        # 1. From local data/raw/ directory
        if not raw_candidates and settings.raw_data_dir.exists():
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

        # 2. From curated seed documents if raw directory has fewer than expected (and not retrying failed items)
        if not retry_run_id and source.lower() == "sebi":
            curated = get_curated_documents()
            existing_urls = {c.get("url") for c in raw_candidates if isinstance(c, dict)}
            for item in curated:
                if item["url"] not in existing_urls:
                    raw_candidates.append(item)

        # 3. Canonicalize & Deduplicate
        seen_urls: Set[str] = set()
        unique_candidates: List[Dict[str, Any]] = []
        duplicate_count = 0

        for c in raw_candidates:
            c_url = canonicalize_url(c.get("url", ""))
            if not c_url:
                continue
            if c_url in seen_urls:
                duplicate_count += 1
            else:
                seen_urls.add(c_url)
                # Ensure canonical URL stored
                c_copy = dict(c)
                c_copy["url"] = c_url
                unique_candidates.append(c_copy)

        if limit and limit > 0:
            return unique_candidates[:limit], duplicate_count
        return unique_candidates, duplicate_count

    def run(
        self,
        source: str = "sebi",
        limit: Optional[int] = None,
        dry_run: bool = False,
        force: bool = False,
        retry_run_id: Optional[str] = None
    ) -> IngestionRunSummary:
        """
        Executes end-to-end incremental ingestion run with content-hash checks,
        chunk-level embedding reuse, version tracking, and change detection.
        """
        run_id = f"SEBI_INGEST_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.utcnow().isoformat()

        logger.info(
            f"source={source.upper()} stage=ingest action=start run_id={run_id} "
            f"limit={limit} dry_run={dry_run} force={force} retry_run_id={retry_run_id}"
        )

        res = self.discover_candidates(
            source=source,
            limit=limit,
            retry_run_id=retry_run_id
        )
        if isinstance(res, tuple) and len(res) == 2:
            candidates, duplicate_count = res
        elif isinstance(res, list):
            candidates = res
            duplicate_count = 0
        else:
            candidates = []
            duplicate_count = 0

        summary = IngestionRunSummary(
            run_id=run_id,
            source=source.upper(),
            started_at=start_time,
            discovered=len(candidates) + duplicate_count,
            unique=len(candidates),
            duplicate=duplicate_count
        )

        logger.info(f"Discovered {len(candidates)} unique documents ({duplicate_count} duplicates).")

        # Track discovered document IDs to identify missing documents
        discovered_doc_ids: Set[str] = set()

        for idx, item in enumerate(candidates, start=1):
            url = item.get("url", "")
            title = item.get("title", "")
            raw_content = item.get("content") or item.get("markdown") or ""

            # Check for missing URL or missing content upfront
            if not url or not url.strip() or not raw_content or not raw_content.strip():
                summary.failed += 1
                summary.failures.append({
                    "run_id": run_id,
                    "url": url,
                    "stage": "discovery",
                    "error_type": "MissingData",
                    "message": "Missing URL or raw markdown content"
                })
                continue

            doc_id = generate_document_id(source=source.upper(), url=url)
            discovered_doc_ids.add(doc_id)

            cleaned_content = clean_markdown(raw_content)
            new_hash = compute_content_hash(cleaned_content)

            # Check existing document
            existing_doc = self._load_stored_document(doc_id)

            if existing_doc:
                old_hash = existing_doc.get("content_hash") or existing_doc.get("metadata", {}).get("content_hash")
                if not old_hash:
                    old_hash = compute_content_hash(existing_doc.get("content", ""))

                if old_hash == new_hash and not force:
                    # UNCHANGED document (Phase 55.4 & 55.8)
                    summary.unchanged += 1
                    if dry_run:
                        logger.info(f"[DRY RUN] UNCHANGED: {title or doc_id[:16]} ({url})")
                    continue
                else:
                    # CHANGED document (Phase 55.5)
                    classification: DocumentProcessingStatus = "CHANGED"
                    summary.changed += 1
            else:
                # NEW document (Phase 55.7)
                classification = "NEW"
                summary.new += 1

            if dry_run:
                logger.info(f"[DRY RUN] {classification}: {title or doc_id[:16]} ({url})")
                continue

            # Process NEW or CHANGED document
            try:
                # 1. Metadata Extraction
                meta_dict = extract_document_metadata(raw_content, url=url, source=source.upper())
                meta_dict["content_hash"] = new_hash
                meta_dict["document_version"] = "1.1" if classification == "CHANGED" else "1.0"

                metadata_obj = DocumentMetadata(
                    document_type=meta_dict.get("document_type") or item.get("expected_document_type", "Circular"),
                    category=meta_dict.get("category") or item.get("expected_category", "General"),
                    circular_number=meta_dict.get("circular_number"),
                    published_date=meta_dict.get("published_date") or item.get("date_hint"),
                    effective_date=meta_dict.get("effective_date"),
                    section=meta_dict.get("section"),
                    status="current",
                    source_status="SOURCE_CURRENT",
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
                    source_status=metadata_obj.source_status,
                    content_hash=new_hash,
                    document_version=metadata_obj.document_version,
                    content=cleaned_content,
                    metadata=metadata_obj
                )

                # 3. Structure-aware Chunking
                chunks: List[DocumentChunk] = chunk_document(reg_doc)
                if not chunks:
                    logger.warning(f"No chunks generated for {doc_id}.")
                    summary.failed += 1
                    summary.failures.append({
                        "run_id": run_id,
                        "document_id": doc_id,
                        "url": url,
                        "stage": "chunking",
                        "error_type": "ZeroChunks",
                        "message": "Zero chunks produced by structure-aware chunker"
                    })
                    continue

                summary.chunks_created += len(chunks)

                # 4. Chunk Quality Validation
                val_report = validate_chunks(chunks)
                if hasattr(val_report, "status") and val_report.status == "FAIL":
                    logger.warning(f"Chunk quality warning for {doc_id}: {getattr(val_report, 'details', [])}")

                # 5. Chunk Hashing & Embedding Reuse (Phases 55.9 - 55.12)
                existing_chunks_map = self._load_stored_chunk_hashes(doc_id)
                existing_hash_map = {
                    c.get("content_hash"): c
                    for c in existing_chunks_map.values()
                    if isinstance(c, dict) and c.get("content_hash") and c.get("embedding")
                }
                chunks_to_embed: List[DocumentChunk] = []

                for chunk in chunks:
                    chunk.content_hash = compute_content_hash(chunk.content)

                    # Look for cached chunk strictly matching content_hash (Phases 55.9 - 55.11)
                    cached_chunk = existing_hash_map.get(chunk.content_hash)
                    if not cached_chunk and chunk.chunk_id in existing_chunks_map:
                        candidate_chunk = existing_chunks_map[chunk.chunk_id]
                        if isinstance(candidate_chunk, dict) and candidate_chunk.get("content_hash") == chunk.content_hash:
                            cached_chunk = candidate_chunk

                    if not cached_chunk:
                        cached_chunk = self.repository.get_chunk_by_hash(chunk.content_hash)

                    if (
                        cached_chunk and
                        cached_chunk.get("content_hash") == chunk.content_hash and
                        cached_chunk.get("embedding") and
                        is_valid_embedding(cached_chunk["embedding"], expected_dim=settings.embedding_dimension)
                    ):
                        # 100% REUSE embedding (Zero Gemini calls)
                        chunk.embedding = cached_chunk["embedding"]
                        chunk.embedding_model = cached_chunk.get("embedding_model", settings.embedding_model)
                        chunk.embedding_dimensions = len(chunk.embedding)
                        summary.chunks_reused += 1
                        summary.embeddings_reused += 1
                    else:
                        chunks_to_embed.append(chunk)

                # Embed only new/changed chunks
                if chunks_to_embed:
                    logger.info(f"Generating embeddings for {len(chunks_to_embed)} new/changed chunks of {doc_id}...")
                    try:
                        embedded_chunks = self.embedding_service.embed_chunks_batch(chunks_to_embed)
                        summary.embeddings_created += len(embedded_chunks)
                        if classification == "CHANGED":
                            summary.chunks_changed += len(chunks_to_embed)
                    except Exception as emb_err:
                        logger.error(f"Embedding error for {doc_id}: {emb_err}")
                        summary.embeddings_failed += len(chunks_to_embed)
                        summary.failures.append({
                            "run_id": run_id,
                            "document_id": doc_id,
                            "url": url,
                            "stage": "embedding",
                            "error_type": "EmbeddingFailure",
                            "message": str(emb_err)
                        })

                # 6. Version Tracking Integration (Phase 55.31)
                version_info = self.version_tracker.resolve_document_relationships(doc_id)
                reg_doc.supersedes = version_info.get("predecessor_id")
                reg_doc.superseded_by = version_info.get("successor_id")
                reg_doc.predecessor_candidates = version_info.get("predecessor_candidates", [])
                reg_doc.relationship_confidence = version_info.get("relationship_confidence")
                reg_doc.relationship_type = version_info.get("relationship_type")
                reg_doc.status = version_info.get("status", "current")

                if reg_doc.supersedes:
                    summary.version_relationships_created += 1

                # 7. Change Detection Integration (Phase 55.32)
                if classification == "CHANGED" and reg_doc.supersedes:
                    try:
                        logger.info(f"Triggering Change Detection: {reg_doc.supersedes} -> {doc_id}")
                        comp_report = self.comparator.compare_documents(reg_doc.supersedes, doc_id)
                        if comp_report and comp_report.status == "SUCCESS":
                            summary.change_analyses_created += 1
                    except Exception as cd_err:
                        logger.warning(f"Change detection warning for {doc_id}: {cd_err}")

                # 8. Safe Persistence (Phase 55.22)
                # Local JSON files
                doc_file = settings.processed_data_dir / f"sebi_{doc_id}.json"
                with open(doc_file, "w", encoding="utf-8") as df:
                    json.dump(reg_doc.model_dump(), df, indent=2, ensure_ascii=False)

                chunk_file = settings.chunks_data_dir / f"sebi_{doc_id}_chunks.json"
                with open(chunk_file, "w", encoding="utf-8") as cf:
                    json.dump([c.model_dump() for c in chunks], cf, indent=2, ensure_ascii=False)

                # MongoDB persistence (graceful fallback if offline)
                try:
                    self.repository.save_document(reg_doc)
                    self.repository.save_chunks(chunks)
                except Exception as me:
                    logger.warning(f"MongoDB persistence offline during ingestion: {me}. Local files saved.")

            except Exception as e:
                logger.error(f"Error ingesting document {url}: {e}", exc_info=True)
                summary.failed += 1
                summary.failures.append({
                    "run_id": run_id,
                    "document_id": doc_id,
                    "url": url,
                    "stage": "processing",
                    "error_type": type(e).__name__,
                    "message": str(e)
                })

        # Check for disappeared documents when running full ingestion (Phase 55.17)
        if not dry_run and limit is None:
            self._check_missing_documents(discovered_doc_ids, source=source.upper())

        summary.completed_at = datetime.utcnow().isoformat()
        if summary.failed > 0:
            summary.status = "PARTIAL" if (summary.new + summary.changed + summary.unchanged > 0) else "FAILED"
        else:
            summary.status = "COMPLETED"

        # Save reports and audit logs
        self._save_reports(summary, dry_run=dry_run)
        self._print_summary_report(summary, dry_run=dry_run)

        return summary

    def _check_missing_documents(self, discovered_doc_ids: Set[str], source: str) -> None:
        """
        Safely identifies previously stored documents missing from the current listing.
        Marks them as SOURCE_MISSING in MongoDB. Never deletes historical records (Phase 55.17).
        """
        if not discovered_doc_ids:
            return

        try:
            existing_docs = self.repository.list_documents(source=source, limit=1000)
            for ed in existing_docs:
                eid = ed.get("document_id")
                if eid and eid not in discovered_doc_ids:
                    # Update status to SOURCE_MISSING without deleting
                    self.repository.mark_document_missing(eid)
                    logger.info(f"source={source} document_id={eid} marked as SOURCE_MISSING (not deleted)")
        except Exception as e:
            logger.debug(f"Missing document check skipped or offline: {e}")

    def _save_reports(self, summary: IngestionRunSummary, dry_run: bool = False) -> None:
        """Saves run_summary.json, run_summary.md, and failed_items.json (Phase 55.29)."""
        if dry_run:
            return

        # 1. Save JSON report
        report_json_path = REPORTS_DIR / f"run_{summary.run_id}.json"
        with open(report_json_path, "w", encoding="utf-8") as jf:
            json.dump(summary.model_dump(), jf, indent=2)

        # 2. Save Markdown report
        report_md_path = REPORTS_DIR / f"run_{summary.run_id}.md"
        md_content = (
            f"# REGINTEL INGESTION RUN REPORT\n\n"
            f"- **Run ID**: `{summary.run_id}`\n"
            f"- **Source**: {summary.source}\n"
            f"- **Status**: {summary.status}\n"
            f"- **Started At**: {summary.started_at}\n"
            f"- **Completed At**: {summary.completed_at}\n\n"
            f"## Document Metrics\n"
            f"| Metric | Count |\n"
            f"| :--- | :--- |\n"
            f"| Discovered | {summary.discovered} |\n"
            f"| Unique | {summary.unique} |\n"
            f"| New | {summary.new} |\n"
            f"| Changed | {summary.changed} |\n"
            f"| Unchanged | {summary.unchanged} |\n"
            f"| Duplicate | {summary.duplicate} |\n"
            f"| Failed | {summary.failed} |\n\n"
            f"## Chunk & Embedding Metrics\n"
            f"| Metric | Count |\n"
            f"| :--- | :--- |\n"
            f"| Chunks Created | {summary.chunks_created} |\n"
            f"| Chunks Reused | {summary.chunks_reused} |\n"
            f"| Chunks Changed | {summary.chunks_changed} |\n"
            f"| Embeddings Generated | {summary.embeddings_created} |\n"
            f"| Embeddings Reused | {summary.embeddings_reused} |\n"
            f"| Embeddings Failed | {summary.embeddings_failed} |\n\n"
            f"## Versioning & Change Analysis\n"
            f"- Version relationships created: {summary.version_relationships_created}\n"
            f"- Change analyses created: {summary.change_analyses_created}\n"
        )
        with open(report_md_path, "w", encoding="utf-8") as mf:
            mf.write(md_content)

        # 3. Update cumulative failed_items.json if failures occurred
        if summary.failures:
            fail_path = REPORTS_DIR / "failed_items.json"
            existing_fails = []
            if fail_path.exists():
                try:
                    with open(fail_path, "r", encoding="utf-8") as ff:
                        existing_fails = json.load(ff)
                except Exception:
                    pass
            existing_fails.extend(summary.failures)
            with open(fail_path, "w", encoding="utf-8") as ff:
                json.dump(existing_fails, ff, indent=2)

    def _print_summary_report(self, summary: IngestionRunSummary, dry_run: bool = False) -> None:
        """Prints formatted summary per Phase 55.30."""
        if dry_run:
            print("\n# INGESTION DRY RUN\n")
            print(f"Discovered: {summary.discovered}")
            print(f"Unique: {summary.unique}\n")
            print(f"## NEW\n{summary.new}\n")
            print(f"## CHANGED\n{summary.changed}\n")
            print(f"## UNCHANGED\n{summary.unchanged}\n")
            print(f"## DUPLICATE\n{summary.duplicate}\n")
            print(f"## FAILED\n{summary.failed}\n")
            print("No database modifications performed.\n")
        else:
            print("\n" + "=" * 40)
            print("# REGINTEL INGESTION RUN")
            print("=" * 40)
            print(f"Run ID: {summary.run_id}")
            print(f"Source: {summary.source}")
            print(f"Status: {summary.status}")
            print(f"Discovered: {summary.discovered}")
            print(f"Unique: {summary.unique}")
            print(f"New: {summary.new}")
            print(f"Changed: {summary.changed}")
            print(f"Unchanged: {summary.unchanged}")
            print(f"Duplicate: {summary.duplicate}")
            print(f"Failed: {summary.failed}")
            print("-" * 40)
            print(f"Chunks created: {summary.chunks_created}")
            print(f"Chunks reused: {summary.chunks_reused}")
            print(f"Chunks changed: {summary.chunks_changed}")
            print(f"Embeddings generated: {summary.embeddings_created}")
            print(f"Embeddings reused: {summary.embeddings_reused}")
            print(f"Version relationships: {summary.version_relationships_created}")
            print(f"Change analyses: {summary.change_analyses_created}")
            print("=" * 40 + "\n")


def main():
    parser = argparse.ArgumentParser(description="RegIntel Incremental Document Ingestion Pipeline (Phase 55)")
    parser.add_argument("--source", default="sebi", help="Regulatory source authority (default: sebi)")
    parser.add_argument("--limit", type=int, default=None, help="Maximum candidate documents to process")
    parser.add_argument("--dry-run", action="store_true", help="Inspect candidate changes without modifying database")
    parser.add_argument("--force", action="store_true", help="Force reprocessing while preserving version lineage")
    parser.add_argument("--retry-failed", type=str, default=None, help="Retry failed items from a previous run ID")

    args = parser.parse_args()
    pipeline = IngestionPipeline()
    pipeline.run(
        source=args.source,
        limit=args.limit,
        dry_run=args.dry_run,
        force=args.force,
        retry_run_id=args.retry_failed
    )


if __name__ == "__main__":
    main()
