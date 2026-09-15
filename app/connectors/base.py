"""
Base Connector Abstraction for Regulatory Intelligence (Phase 66).

Defines the contract and shared utilities for all official financial regulatory connectors:
- RegulatoryConnector (Abstract Base Class)
- BaseRegulatoryConnector (Common implementation with rate limiting, retries, and persistence)
- CrawlResult model
"""

import re
import json
import time
import logging
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional, Dict, Any, List, Tuple

from pydantic import BaseModel, Field

from app.config import settings
from app.connectors.authority import RegulatoryAuthority, get_authority_metadata
from app.ingestion.models import (
    RawDocument,
    RegulatoryDocument,
    DocumentMetadata,
    canonicalize_url,
    generate_document_id,
    compute_content_hash,
    to_mongo,
    from_mongo
)
from app.ingestion.cleaner import clean_markdown
from app.ingestion.metadata import derive_title_from_url_or_content
from app.ingestion.repository import save_document

logger = logging.getLogger("regintel.connectors.base")


class CrawlResult(BaseModel):
    """Structured result model for a crawled document or page."""
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
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Non-retryable HTTP status codes and markers
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 405, 410, 422}
NON_RETRYABLE_ERROR_SUBSTRINGS = [
    "404 not found",
    "unsupported document",
    "invalid url",
    "access denied",
    "forbidden",
    "blocked by robots"
]


class RegulatoryConnector(ABC):
    """
    Abstract Contract for an official regulatory connector.
    Guarantees consistent discovery, document retrieval, metadata extraction,
    and normalization across all regulatory authorities.
    """

    @property
    @abstractmethod
    def authority(self) -> RegulatoryAuthority:
        """The regulatory authority this connector handles (e.g. SEBI, RBI)."""
        pass

    @property
    @abstractmethod
    def allowed_domains(self) -> List[str]:
        """List of official domains allowed for crawling (e.g. ['rbi.org.in'])."""
        pass

    @abstractmethod
    async def discover_sources(self) -> List[Any]:
        """Discovers or retrieves registered sources for this authority."""
        pass

    @abstractmethod
    async def discover_documents(
        self,
        source: Any,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Discovers document links and candidate metadata from a regulatory source listing/archive."""
        pass

    @abstractmethod
    async def fetch_document(self, url: str) -> CrawlResult:
        """Fetches and extracts text content from an individual document (HTML or PDF)."""
        pass

    @abstractmethod
    def extract_metadata(
        self,
        text: str,
        title: Optional[str] = None,
        url: Optional[str] = None
    ) -> DocumentMetadata:
        """Extracts authority-specific structured metadata deterministically."""
        pass

    @abstractmethod
    def normalize_document(self, raw_doc: RawDocument) -> RegulatoryDocument:
        """Normalizes a raw document into the common RegulatoryDocument model."""
        pass


class BaseRegulatoryConnector(RegulatoryConnector):
    """
    Production-grade base implementation providing shared crawler politeness,
    rate-limiting, validation, and storage mechanisms.
    """

    def __init__(
        self,
        crawl_delay_seconds: float = 1.0,
        max_concurrency: int = 3,
        max_retries: int = 3,
        raw_dir: Optional[Path] = None,
        processed_dir: Optional[Path] = None
    ):
        self.crawl_delay_seconds = crawl_delay_seconds
        self.max_concurrency = max_concurrency
        self.max_retries = max_retries
        self.raw_dir = raw_dir or settings.raw_data_dir
        self.processed_dir = processed_dir or settings.processed_data_dir
        
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def canonicalize(self, url: str) -> str:
        """Normalizes a URL to its canonical form."""
        return canonicalize_url(url)

    def is_allowed_domain(self, url: str) -> bool:
        """Strictly validates if URL belongs to the official authority domain."""
        if not self.allowed_domains:
            return True
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower().lstrip("www.")
            if ":" in host:
                host = host.split(":")[0]
            return any(host == d.lower().lstrip("www.") or host.endswith("." + d.lower().lstrip("www.")) for d in self.allowed_domains)
        except Exception:
            return False

    def is_retryable_error(self, error_msg: Optional[str], status_code: Optional[int] = None) -> bool:
        """Determines if a crawl or download error is transient and retryable."""
        if status_code and status_code in NON_RETRYABLE_STATUS_CODES:
            return False
        if not error_msg:
            return True
        err_lower = error_msg.lower()
        return not any(marker in err_lower for marker in NON_RETRYABLE_ERROR_SUBSTRINGS)

    def validate_content(self, content: Optional[str], title: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validates content quality to prevent ingestion of error pages, access denials,
        or empty bodies.
        """
        if not content or not content.strip():
            return False, "CRAWL_INVALID: Content is empty or blank"

        clean_text = content.strip()
        if len(clean_text) < 50:
            return False, f"CRAWL_INVALID: Content length ({len(clean_text)}) is below 50 chars threshold"

        sample_lower = clean_text[:500].lower()
        if "access denied" in sample_lower or "403 forbidden" in sample_lower:
            return False, "CRAWL_INVALID: Access Denied or Forbidden page detected"
        if "page not found" in sample_lower or "404 not found" in sample_lower:
            return False, "CRAWL_INVALID: 404 Not Found page detected"

        return True, None

    def save_raw_document(self, raw_doc: RawDocument) -> Path:
        """Saves a raw scraped document locally in JSON format."""
        file_path = self.raw_dir / f"{self.authority.value.lower()}_{raw_doc.document_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(raw_doc.model_dump(), f, indent=2, ensure_ascii=False)
        return file_path

    def save_processed_document(self, processed_doc: RegulatoryDocument) -> Path:
        """Saves a processed regulatory document locally in JSON format."""
        file_path = self.processed_dir / f"{self.authority.value.lower()}_{processed_doc.document_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(processed_doc.model_dump(), f, indent=2, ensure_ascii=False)
        return file_path

    def normalize_document(self, raw_doc: RawDocument) -> RegulatoryDocument:
        """
        Default normalization logic:
        1. Clean markdown content
        2. Derive title
        3. Extract authority-specific metadata
        4. Produce RegulatoryDocument with authority context
        """
        cleaned_text = clean_markdown(raw_doc.content)
        resolved_title = derive_title_from_url_or_content(
            url=raw_doc.url,
            text=cleaned_text,
            generic_title=raw_doc.title
        )

        metadata = self.extract_metadata(
            text=cleaned_text,
            title=resolved_title,
            url=raw_doc.url
        )

        # Ensure content_hash is populated
        c_hash = compute_content_hash(cleaned_text)
        metadata.content_hash = c_hash

        processed_doc = RegulatoryDocument(
            document_id=raw_doc.document_id,
            url=raw_doc.url,
            title=resolved_title,
            source=self.authority.value,
            authority=self.authority.value,
            document_type=metadata.document_type,
            category=metadata.category,
            circular_number=metadata.circular_number,
            published_date=metadata.published_date,
            effective_date=metadata.effective_date,
            section=metadata.section,
            status=metadata.status or "unknown",
            source_status=metadata.source_status or "SOURCE_CURRENT",
            supersedes=metadata.supersedes,
            superseded_by=metadata.superseded_by,
            amends=metadata.amends,
            amended_by=metadata.amended_by or [],
            corrigendum_of=metadata.corrigendum_of,
            corrigenda=metadata.corrigenda or [],
            references=metadata.references or [],
            relationships=metadata.relationships or [],
            predecessor_candidates=metadata.predecessor_candidates or [],
            relationship_confidence=metadata.relationship_confidence,
            content_hash=c_hash,
            document_version=metadata.document_version or "1.0",
            relationship_type=metadata.relationship_type,
            department=getattr(metadata, "department", None) or metadata.section,
            content=cleaned_text,
            scraped_at=raw_doc.scraped_at,
            metadata=metadata
        )

        self.save_processed_document(processed_doc)
        return processed_doc
