"""
SEBI Regulatory Connector (Phases 54 & 66).

Adapts the production-grade SEBI crawler under the generic RegulatoryConnector contract.
Zero breaking changes to existing SEBI ingestion.
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.connectors.authority import RegulatoryAuthority
from app.connectors.base import BaseRegulatoryConnector, CrawlResult
from app.connectors.registry import RegulatorySource, source_registry, connector_registry
from app.ingestion.models import RawDocument, RegulatoryDocument, DocumentMetadata
from app.ingestion.metadata import MetadataExtractor
from scraper.sebi_scraper import SEBIScraper
from scraper.sebi_sources import SEBI_SOURCES, get_curated_documents

logger = logging.getLogger("regintel.connectors.sebi")


class SEBIConnector(BaseRegulatoryConnector):
    """Connector adapter for the Securities and Exchange Board of India (SEBI)."""

    def __init__(
        self,
        crawl_delay_seconds: float = 1.0,
        max_concurrency: int = 3,
        max_retries: int = 3,
        raw_dir: Optional[Path] = None,
        processed_dir: Optional[Path] = None
    ):
        super().__init__(
            crawl_delay_seconds=crawl_delay_seconds,
            max_concurrency=max_concurrency,
            max_retries=max_retries,
            raw_dir=raw_dir,
            processed_dir=processed_dir
        )
        self._scraper = SEBIScraper(
            raw_dir=self.raw_dir,
            processed_dir=self.processed_dir,
            crawl_delay_seconds=self.crawl_delay_seconds,
            max_concurrency=self.max_concurrency,
            max_retries=self.max_retries
        )

    @property
    def authority(self) -> RegulatoryAuthority:
        return RegulatoryAuthority.SEBI

    @property
    def allowed_domains(self) -> List[str]:
        return ["sebi.gov.in"]

    async def discover_sources(self) -> List[RegulatorySource]:
        """Discovers or retrieves registered sources for SEBI."""
        return source_registry.get_sources(authority=self.authority, enabled_only=True)

    async def discover_documents(
        self,
        source: Optional[RegulatorySource] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Discovers candidate document URLs from SEBI listings and curated seeds."""
        candidates = []

        # 1. Curated documents
        for doc in get_curated_documents():
            candidates.append({
                "url": doc["url"],
                "title": doc.get("title"),
                "authority": self.authority.value,
                "document_type": doc.get("expected_document_type", "Circular"),
                "category": doc.get("expected_category", "General"),
                "source": "SEBI",
                "date_hint": doc.get("date_hint")
            })

        # 2. Dynamic discovery from scraper if requested
        if source:
            try:
                # Find matching SebiSourceConfig
                matching = [s for s in SEBI_SOURCES if s.source_url == source.listing_url]
                if matching:
                    discovered_urls = await self._scraper.discover_links_for_source(matching[0])
                    for u in discovered_urls:
                        candidates.append({
                            "url": u,
                            "authority": self.authority.value,
                            "source": "SEBI",
                            "document_type": source.document_types[0] if source.document_types else "Circular",
                            "category": source.category or "General"
                        })
            except Exception as e:
                logger.warning(f"Error discovering links from SEBI source {source.name}: {e}")

        if limit and limit > 0:
            return candidates[:limit]
        return candidates

    async def fetch_document(self, url: str) -> CrawlResult:
        """Fetches and processes an individual SEBI document."""
        canonical_url = self.canonicalize(url)
        if not self.is_allowed_domain(canonical_url):
            return CrawlResult(
                url=canonical_url,
                status_code=400,
                success=False,
                error=f"Domain not allowed for SEBI: {url}"
            )

        scrape_res = await self._scraper.crawl_document(canonical_url)
        return CrawlResult(
            url=scrape_res.url,
            final_url=scrape_res.final_url,
            title=scrape_res.title,
            content=scrape_res.content,
            status_code=scrape_res.status_code,
            content_type=scrape_res.content_type,
            success=scrape_res.success,
            error=scrape_res.error,
            response_time_ms=scrape_res.response_time_ms,
            retry_count=scrape_res.retry_count
        )

    def extract_metadata(
        self,
        text: str,
        title: Optional[str] = None,
        url: Optional[str] = None
    ) -> DocumentMetadata:
        """Extracts deterministic SEBI metadata."""
        meta = MetadataExtractor.extract(text=text, title=title, url=url)
        meta.authority = self.authority.value
        meta.source = self.authority.value
        return meta


# Instantiate and register
sebi_connector = SEBIConnector()
connector_registry.register(sebi_connector)
