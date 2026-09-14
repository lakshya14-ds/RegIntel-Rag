"""
Base Scraper Module for Regulatory Intelligence (Phase 54).

Provides reusable, production-ready abstractions for regulatory document scrapers:
- CrawlResult data model
- URL canonicalization and domain filtering
- Retryable vs. non-retryable failure classification
- Content validation
- Raw/processed document saving and transformation
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Literal, Tuple
from datetime import datetime
from urllib.parse import urlparse
from pydantic import BaseModel, Field

from app.config import settings
from app.ingestion.models import (
    RawDocument,
    RegulatoryDocument,
    canonicalize_url,
    generate_document_id,
    to_mongo,
    from_mongo
)
from app.ingestion.cleaner import clean_markdown
from app.ingestion.metadata import MetadataExtractor, derive_title_from_url_or_content
from app.ingestion.repository import save_document

logger = logging.getLogger(__name__)


class CrawlResult(BaseModel):
    """Structured result model for an individual crawled page or document (Phase 54.4)."""
    url: str
    final_url: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    status_code: int = 200
    content_type: str = "HTML"  # "HTML", "PDF", "UNSUPPORTED"
    crawled_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    success: bool = True
    error: Optional[str] = None
    response_time_ms: Optional[float] = None
    source_page: Optional[str] = None
    discovered_from: Optional[str] = None
    retry_count: int = 0


# Non-retryable HTTP status codes and error markers
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 405, 410, 422}
NON_RETRYABLE_ERROR_SUBSTRINGS = [
    "404 not found",
    "unsupported document",
    "invalid url",
    "access denied",
    "forbidden",
    "blocked by robots"
]


class BaseScraper:
    """
    Base reusable scraper orchestrating discovery, rate-limited crawling,
    validation, metadata extraction, and local/database persistence.
    """

    def __init__(
        self,
        source_name: str,
        allowed_domains: Optional[List[str]] = None,
        raw_dir: Optional[Path] = None,
        processed_dir: Optional[Path] = None,
        crawl_delay_seconds: float = 1.0,
        max_concurrency: int = 3,
        max_retries: int = 3
    ):
        self.source_name = source_name.strip().upper()
        self.allowed_domains = [d.lower().lstrip("www.") for d in (allowed_domains or [])]
        self.raw_dir = raw_dir or settings.raw_data_dir
        self.processed_dir = processed_dir or settings.processed_data_dir
        self.crawl_delay_seconds = crawl_delay_seconds
        self.max_concurrency = max_concurrency
        self.max_retries = max_retries
        
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def canonicalize(self, url: str) -> str:
        """Applies deterministic URL normalization."""
        return canonicalize_url(url)

    def is_allowed_domain(self, url: str) -> bool:
        """
        Validates whether the URL's domain is in the configured allowed list (Phase 54.9).
        If allowed_domains is empty, allows all domains.
        """
        if not self.allowed_domains:
            return True
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower().lstrip("www.")
            # Strip port if present
            if ":" in host:
                host = host.split(":")[0]
            return any(host == d or host.endswith("." + d) for d in self.allowed_domains)
        except Exception:
            return False

    def classify_document_type(self, url: str, content_type_header: Optional[str] = None) -> str:
        """
        Determines whether the document is HTML, PDF, or UNSUPPORTED (Phase 54.11).
        """
        lower_url = (url or "").lower()
        if content_type_header:
            ch = content_type_header.lower()
            if "application/pdf" in ch:
                return "PDF"
            if "text/html" in ch or "application/xhtml+xml" in ch:
                return "HTML"

        if lower_url.endswith(".pdf") or "/pdf/" in lower_url:
            return "PDF"
        if lower_url.endswith((".html", ".htm", ".do", ".jsp", ".aspx", "/")):
            return "HTML"
        if not Path(urlparse(url).path).suffix:
            return "HTML"

        # Check for explicitly unsupported binaries
        if lower_url.endswith((".zip", ".exe", ".mp4", ".mp3", ".avi", ".xlsx", ".csv", ".docx")):
            return "UNSUPPORTED"

        return "HTML"

    def is_retryable_error(self, error_msg: Optional[str], status_code: Optional[int] = None) -> bool:
        """
        Distinguishes transient retryable errors from permanent non-retryable errors (Phase 54.15).
        """
        if status_code and status_code in NON_RETRYABLE_STATUS_CODES:
            return False
        if not error_msg:
            return True

        err_lower = error_msg.lower()
        for marker in NON_RETRYABLE_ERROR_SUBSTRINGS:
            if marker in err_lower:
                return False
        return True

    def validate_content(self, content: Optional[str], title: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validates crawled content quality (Phase 54.22).
        Checks:
        - Content exists and is non-empty
        - Minimum length threshold (> 50 characters)
        - No 'Access Denied', generic 403/404, or blank responses
        """
        if not content or not content.strip():
            return False, "CRAWL_INVALID: Content is empty or blank"

        clean_text = content.strip()
        if len(clean_text) < 50:
            return False, f"CRAWL_INVALID: Content length ({len(clean_text)}) is below minimum threshold (50 chars)"

        sample_lower = clean_text[:500].lower()
        if "access denied" in sample_lower or "403 forbidden" in sample_lower:
            return False, "CRAWL_INVALID: Access Denied or Forbidden page detected"
        if "page not found" in sample_lower or "404 not found" in sample_lower:
            return False, "CRAWL_INVALID: 404 Not Found page detected"

        return True, None

    def save_raw_document(self, raw_doc: RawDocument) -> Path:
        """Saves a raw scraped document locally in JSON format."""
        file_path = self.raw_dir / f"{self.source_name.lower()}_{raw_doc.document_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(raw_doc.model_dump(), f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved raw document to {file_path}")
        return file_path

    def save_processed_document(self, processed_doc: RegulatoryDocument) -> Path:
        """Saves a processed regulatory document locally in JSON format."""
        file_path = self.processed_dir / f"{self.source_name.lower()}_{processed_doc.document_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(processed_doc.model_dump(), f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved processed document to {file_path}")
        return file_path

    def process_raw_document(self, raw_doc: RawDocument, persist_db: bool = False) -> RegulatoryDocument:
        """
        Cleans raw markdown text, extracts metadata deterministically, and produces a RegulatoryDocument.
        Optionally persists to MongoDB.
        """
        # 1. Clean markdown text
        cleaned_text = clean_markdown(raw_doc.content)

        # 2. Derive descriptive title if generic
        resolved_title = derive_title_from_url_or_content(
            url=raw_doc.url,
            text=cleaned_text,
            generic_title=raw_doc.title
        )

        # 3. Extract metadata deterministically (rule-based, no LLM)
        metadata = MetadataExtractor.extract(
            text=cleaned_text,
            title=resolved_title,
            url=raw_doc.url
        )

        # 4. Construct RegulatoryDocument
        processed_doc = RegulatoryDocument(
            document_id=raw_doc.document_id,
            url=raw_doc.url,
            title=resolved_title,
            source=raw_doc.source,
            document_type=metadata.document_type,
            category=metadata.category,
            circular_number=metadata.circular_number,
            published_date=metadata.published_date,
            effective_date=metadata.effective_date,
            section=metadata.section,
            content=cleaned_text,
            scraped_at=raw_doc.scraped_at,
            metadata=metadata
        )

        # 5. Save to local data/processed directory
        self.save_processed_document(processed_doc)

        # 6. Optionally save to MongoDB
        if persist_db:
            try:
                save_document(processed_doc)
                logger.info(f"Persisted document {processed_doc.document_id} to MongoDB Atlas")
            except Exception as e:
                logger.warning(f"MongoDB persistence skipped or failed for {processed_doc.document_id}: {e}")

        return processed_doc

    def reprocess_all_raw_documents(self, persist_db: bool = False) -> int:
        """Reprocesses all raw JSON files from data/raw/ into data/processed/."""
        raw_files = list(self.raw_dir.glob(f"{self.source_name.lower()}_*.json"))
        count = 0
        for rf in raw_files:
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                raw_doc = from_mongo(RawDocument, data)
                self.process_raw_document(raw_doc, persist_db=persist_db)
                count += 1
            except Exception as e:
                logger.error(f"Failed to reprocess {rf.name}: {e}")
        return count
