import os
import sys
import asyncio
import logging
import argparse
from typing import Optional, List, Dict, Any, Set
from datetime import datetime

# Add project root to sys.path if invoked directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

from app.config import settings
from app.ingestion.models import (
    RawDocument,
    RegulatoryDocument,
    canonicalize_url,
    generate_document_id
)
from scraper.base_scraper import BaseScraper
from scraper.sebi_sources import SEBI_DOCUMENT_URLS, get_seed_urls

logger = logging.getLogger("scraper.sebi_scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class SEBIScraper(BaseScraper):
    """
    Asynchronous SEBI Scraper powered by Crawl4AI.
    Extracts authoritative regulatory circulars, orders, and master circulars.
    """

    def __init__(self, raw_dir=None, processed_dir=None):
        super().__init__(source_name="SEBI", raw_dir=raw_dir, processed_dir=processed_dir)
        self.browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            extra_args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
        )
        self.run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10,
            page_timeout=30000,
            delay_before_return_html=1.5
        )

    async def crawl_url(self, url: str, crawler: Optional[AsyncWebCrawler] = None, retries: int = 2) -> Optional[RawDocument]:
        """
        Crawls a single SEBI URL with retry logic.
        Extracts content, title, and metadata into a RawDocument.
        """
        canonical_url = canonicalize_url(url)
        if not canonical_url:
            logger.error(f"Invalid URL provided: {url}")
            return None

        doc_id = generate_document_id(source="SEBI", url=canonical_url)
        logger.info(f"Crawling URL: {canonical_url} (ID: {doc_id[:8]}...)")

        should_close_crawler = False
        if crawler is None:
            crawler = AsyncWebCrawler(config=self.browser_config)
            await crawler.start()
            should_close_crawler = True

        try:
            for attempt in range(1, retries + 1):
                try:
                    result = await crawler.arun(url=canonical_url, config=self.run_config)
                    
                    if not result or not result.success:
                        error_msg = getattr(result, "error_message", "Unknown crawl error")
                        logger.warning(f"Crawl attempt {attempt}/{retries} failed for {canonical_url}: {error_msg}")
                        if attempt < retries:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        logger.error(f"Crawl failed after {retries} attempts: {canonical_url}")
                        return None

                    # Extract markdown/text content
                    content = ""
                    if hasattr(result, "markdown") and result.markdown:
                        if hasattr(result.markdown, "raw_markdown"):
                            content = result.markdown.raw_markdown
                        else:
                            content = str(result.markdown)
                    elif hasattr(result, "cleaned_html") and result.cleaned_html:
                        content = result.cleaned_html

                    if not content or not content.strip():
                        logger.warning(f"Empty content returned for {canonical_url}")
                        if attempt < retries:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return None

                    # Extract title
                    title = None
                    if hasattr(result, "metadata") and isinstance(result.metadata, dict):
                        title = result.metadata.get("title") or result.metadata.get("og:title")
                    if not title and hasattr(result, "page_title") and result.page_title:
                        title = result.page_title

                    raw_doc = RawDocument(
                        document_id=doc_id,
                        url=canonical_url,
                        title=title.strip() if title else None,
                        content=content.strip(),
                        source="SEBI",
                        scraped_at=datetime.utcnow().isoformat()
                    )

                    # Save locally to data/raw/
                    self.save_raw_document(raw_doc)
                    logger.info(f"Crawl succeeded: {canonical_url} -> Saved raw document {doc_id[:8]}...")
                    return raw_doc

                except Exception as ex:
                    logger.warning(f"Exception during crawl attempt {attempt} for {canonical_url}: {ex}")
                    if attempt < retries:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        logger.error(f"Crawl exception for {canonical_url}: {ex}")
                        return None
        finally:
            if should_close_crawler:
                await crawler.close()

        return None

    async def crawl_urls(
        self,
        urls: List[str],
        limit: Optional[int] = None,
        persist_db: bool = False
    ) -> Dict[str, Any]:
        """
        Crawls a list of URLs with deduplication, saves raw output,
        cleans, extracts metadata, and optionally stores in MongoDB.
        Returns a summary report.
        """
        # Deduplicate URLs using canonical representations
        seen_urls: Set[str] = set()
        unique_urls: List[str] = []
        duplicates_count = 0

        for u in urls:
            canon = canonicalize_url(u)
            if not canon:
                continue
            if canon in seen_urls:
                duplicates_count += 1
            else:
                seen_urls.add(canon)
                unique_urls.append(canon)

        if limit:
            target_urls = unique_urls[:limit]
        else:
            target_urls = unique_urls

        discovered = len(urls)
        attempted = len(target_urls)
        succeeded = 0
        failed = 0
        saved = 0

        logger.info(f"Initiating crawl batch: Discovered={discovered}, Unique Target={attempted}, Duplicates={duplicates_count}")

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            for i, target_url in enumerate(target_urls, start=1):
                logger.info(f"[{i}/{attempted}] Processing: {target_url}")
                raw_doc = await self.crawl_url(target_url, crawler=crawler)
                if raw_doc:
                    succeeded += 1
                    try:
                        # Clean, extract metadata, and save processed document
                        self.process_raw_document(raw_doc, persist_db=persist_db)
                        saved += 1
                    except Exception as e:
                        logger.error(f"Failed to process and save {raw_doc.document_id}: {e}")
                else:
                    failed += 1
                
                # Polite rate limiting between pages
                await asyncio.sleep(1.0)

        summary = {
            "Discovered": discovered,
            "Attempted": attempted,
            "Succeeded": succeeded,
            "Failed": failed,
            "Duplicates": duplicates_count,
            "Saved": saved
        }

        self.print_summary(summary)
        return summary

    def print_summary(self, summary: Dict[str, int]):
        """Prints a clean crawl summary."""
        print("\n" + "=" * 35)
        print("Crawl Summary")
        print("-" * 35)
        for k, v in summary.items():
            print(f"{k:<12}: {v}")
        print("=" * 35 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="SEBI Regulatory Document Crawler (Crawl4AI)")
    parser.add_argument("--url", type=str, help="Crawl a single SEBI document URL")
    parser.add_argument("--seed", action="store_true", help="Run controlled crawl using curated SEBI seed sources")
    parser.add_argument("--limit", type=int, default=30, help="Maximum number of documents to crawl (default: 30)")
    parser.add_argument("--store-db", action="store_true", help="Persist processed documents to MongoDB Atlas")

    args = parser.parse_args()
    scraper = SEBIScraper()

    if args.url:
        logger.info(f"Single URL mode: {args.url}")
        raw_doc = await scraper.crawl_url(args.url)
        if raw_doc:
            processed_doc = scraper.process_raw_document(raw_doc, persist_db=args.store_db)
            print("\n--- Processed Document Result ---")
            print(f"ID             : {processed_doc.document_id}")
            print(f"Title          : {processed_doc.title}")
            print(f"Category       : {processed_doc.category}")
            print(f"Document Type  : {processed_doc.document_type}")
            print(f"Circular Number: {processed_doc.circular_number}")
            print(f"Published Date : {processed_doc.published_date}")
            print(f"Effective Date : {processed_doc.effective_date}")
            print(f"Content Length : {len(processed_doc.content)} chars")
            print("---------------------------------")
        else:
            logger.error("Failed to crawl the provided URL.")
    elif args.seed:
        seed_urls = get_seed_urls()
        await scraper.crawl_urls(seed_urls, limit=args.limit, persist_db=args.store_db)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
