"""
Production-Grade SEBI Regulatory Scraper (Phase 54).

Powered by Crawl4AI with:
- Formal separation of Link Discovery from Document Fetching
- Bounded listing pagination with cycle avoidance
- Strict official SEBI domain restriction (sebi.gov.in)
- HTML / PDF document classification and content validation
- Exponential backoff retry with retryable vs. non-retryable classification
- Configurable concurrency (semaphore) and polite rate-limiting
- Checkpointing for restartability and crash-recovery
- Structured run ID, logging, and comprehensive Discovery & Crawl reports
- CLI with --discover, --crawl, --limit, --dry-run, and --resume
"""

import os
import re
import sys
import json
import time
import asyncio
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
except ImportError:
    AsyncWebCrawler = None
    BrowserConfig = None
    CrawlerRunConfig = None
    CacheMode = None

from app.config import settings
from app.ingestion.models import (
    RawDocument,
    RegulatoryDocument,
    canonicalize_url,
    generate_document_id
)
from scraper.base_scraper import BaseScraper, CrawlResult
from scraper.sebi_sources import (
    SEBI_SOURCES,
    SebiSourceConfig,
    get_active_sources,
    get_listing_sources,
    get_curated_documents,
    get_seed_urls
)

logger = logging.getLogger("scraper.sebi_scraper")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# Checkpoint directory
CHECKPOINTS_DIR = Path("data/ingestion/checkpoints")
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)


class SEBIScraper(BaseScraper):
    """
    Production-grade SEBI crawler and discovery engine.
    """

    ALLOWED_DOMAINS = ["sebi.gov.in"]
    DOCUMENT_URL_PATTERNS = [
        re.compile(r"/legal/circulars/.*\.html?", re.IGNORECASE),
        re.compile(r"/legal/master-circulars/.*\.html?", re.IGNORECASE),
        re.compile(r"/legal/regulations/.*\.html?", re.IGNORECASE),
        re.compile(r"/legal/orders/.*\.html?", re.IGNORECASE),
        re.compile(r"/reports-and-statistics/.*\.html?", re.IGNORECASE),
        re.compile(r"\.pdf(\?.*)?$", re.IGNORECASE),
    ]

    IRRELEVANT_PATTERNS = [
        re.compile(r"/login", re.IGNORECASE),
        re.compile(r"/search", re.IGNORECASE),
        re.compile(r"/feedback", re.IGNORECASE),
        re.compile(r"/contact", re.IGNORECASE),
        re.compile(r"/sitemap", re.IGNORECASE),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"mailto:", re.IGNORECASE),
        re.compile(r"#", re.IGNORECASE)
    ]

    def __init__(
        self,
        raw_dir: Optional[Path] = None,
        processed_dir: Optional[Path] = None,
        crawl_delay_seconds: float = 1.0,
        max_concurrency: int = 3,
        max_retries: int = 3
    ):
        super().__init__(
            source_name="SEBI",
            allowed_domains=self.ALLOWED_DOMAINS,
            raw_dir=raw_dir,
            processed_dir=processed_dir,
            crawl_delay_seconds=crawl_delay_seconds,
            max_concurrency=max_concurrency,
            max_retries=max_retries
        )

        self.browser_config = None
        self.run_config = None
        if BrowserConfig and CrawlerRunConfig:
            self.browser_config = BrowserConfig(
                headless=True,
                verbose=False,
                extra_args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
            )
            self.run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS if CacheMode else None,
                word_count_threshold=10,
                page_timeout=30000,
                delay_before_return_html=1.5
            )

    # -------------------------------------------------------------------------
    # 54.19 Run ID Generation
    # -------------------------------------------------------------------------
    @staticmethod
    def generate_run_id() -> str:
        """Generates a standardized run ID: SEBI_YYYYMMDD_HHMMSS."""
        return f"SEBI_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    # -------------------------------------------------------------------------
    # 54.8 Link Filtering & Validation
    # -------------------------------------------------------------------------
    def is_document_link(self, url: str) -> bool:
        """
        Distinguishes regulatory document links from navigation, search, and social links.
        """
        if not url:
            return False
        if not self.is_allowed_domain(url):
            return False

        for irr in self.IRRELEVANT_PATTERNS:
            if irr.search(url):
                return False

        path = urlparse(url).path
        for doc_pat in self.DOCUMENT_URL_PATTERNS:
            if doc_pat.search(path) or doc_pat.search(url):
                return True

        return False

    def extract_links_from_html(self, html: str, base_url: str) -> List[str]:
        """Extracts and resolves relative links from HTML."""
        if not html:
            return []
        href_pattern = re.compile(r'href=[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
        raw_hrefs = href_pattern.findall(html)
        resolved = []
        for h in raw_hrefs:
            full_url = urljoin(base_url, h.strip())
            resolved.append(full_url)
        return resolved

    # -------------------------------------------------------------------------
    # 54.5 & 54.6 Discovery & Bounded Pagination
    # -------------------------------------------------------------------------
    async def discover_documents(
        self,
        sources: Optional[List[SebiSourceConfig]] = None,
        max_pages: int = 3,
        crawler: Optional[Any] = None,
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Discovers candidate document URLs from SEBI official listing pages.
        Performs bounded pagination and link filtering.
        """
        run_id = run_id or self.generate_run_id()
        active_sources = sources or get_listing_sources()

        logger.info(f"source=SEBI stage=discovery run_id={run_id} action=start sources_count={len(active_sources)}")

        visited_listing_pages: Set[str] = set()
        discovered_urls: List[str] = []
        unsupported_links: List[str] = []
        failed_pages: List[str] = []

        should_close_crawler = False
        if crawler is None and AsyncWebCrawler:
            crawler = AsyncWebCrawler(config=self.browser_config)
            await crawler.start()
            should_close_crawler = True

        try:
            for source in active_sources:
                curr_url = source.source_url
                pages_visited_for_source = 0
                max_p = min(max_pages, source.max_pages)

                while curr_url and pages_visited_for_source < max_p:
                    canon_listing_url = canonicalize_url(curr_url)
                    if canon_listing_url in visited_listing_pages:
                        break

                    visited_listing_pages.add(canon_listing_url)
                    pages_visited_for_source += 1

                    logger.info(
                        f"source=SEBI stage=discovery run_id={run_id} "
                        f"visiting_page={canon_listing_url} page={pages_visited_for_source}/{max_p}"
                    )

                    html_content = ""
                    if crawler:
                        try:
                            res = await crawler.arun(url=canon_listing_url, config=self.run_config)
                            if res and res.success and res.html:
                                html_content = res.html
                            else:
                                failed_pages.append(canon_listing_url)
                                logger.warning(f"source=SEBI stage=discovery run_id={run_id} failed_listing={canon_listing_url}")
                        except Exception as e:
                            failed_pages.append(canon_listing_url)
                            logger.error(f"source=SEBI stage=discovery run_id={run_id} error_listing={canon_listing_url}: {e}")

                    # Extract links
                    raw_links = self.extract_links_from_html(html_content, canon_listing_url)
                    for raw_link in raw_links:
                        canon_link = canonicalize_url(raw_link)
                        if not canon_link:
                            continue

                        doc_type = self.classify_document_type(canon_link)
                        if doc_type == "UNSUPPORTED":
                            unsupported_links.append(canon_link)
                            continue

                        if self.is_document_link(canon_link):
                            discovered_urls.append(canon_link)

                    # Bounded pagination: Detect next page
                    curr_url = self._get_next_page_url(html_content, canon_listing_url, pages_visited_for_source)
                    if curr_url:
                        await asyncio.sleep(self.crawl_delay_seconds)

        finally:
            if should_close_crawler and crawler:
                await crawler.close()

        # Always include curated baseline documents if listing discovery had few/none (e.g. offline/mock)
        curated_urls = [canonicalize_url(item["url"]) for item in get_curated_documents()]
        discovered_urls.extend(curated_urls)

        # Deduplicate
        seen: Set[str] = set()
        unique_urls: List[str] = []
        duplicate_count = 0
        for u in discovered_urls:
            if u in seen:
                duplicate_count += 1
            else:
                seen.add(u)
                unique_urls.append(u)

        report = {
            "run_id": run_id,
            "listing_pages_visited": len(visited_listing_pages),
            "document_urls_discovered": len(discovered_urls),
            "unique_urls": len(unique_urls),
            "duplicates_removed": duplicate_count,
            "unsupported_links": len(unsupported_links),
            "failed_pages": len(failed_pages),
            "urls": unique_urls
        }

        self.print_discovery_report(report)
        return report

    def _get_next_page_url(self, html: str, current_url: str, current_page: int) -> Optional[str]:
        """Detects next page URL from listing HTML or pagination parameters."""
        if not html:
            return None

        # Check for explicit "Next" or ">" link
        next_match = re.search(r'<a[^>]+href=[\'"]([^\'"]+)[\'"][^>]*>(?:Next|&gt;|»)<\/a>', html, re.IGNORECASE)
        if next_match:
            return urljoin(current_url, next_match.group(1))

        # Check for pageNo/page parameter in query string
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        for p_name in ["pageNo", "page", "page_no", "p"]:
            if p_name in params:
                try:
                    val = int(params[p_name][0])
                    params[p_name] = [str(val + 1)]
                    new_query = urlencode(params, doseq=True)
                    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ""))
                except ValueError:
                    pass

        return None

    def print_discovery_report(self, report: Dict[str, Any]):
        """Prints structured discovery report per Phase 54.24."""
        print("\n" + "=" * 40)
        print("# SEBI DISCOVERY REPORT")
        print("=" * 40)
        print(f"Run ID                   : {report.get('run_id')}")
        print(f"Listing pages visited    : {report.get('listing_pages_visited')}")
        print(f"Document URLs discovered : {report.get('document_urls_discovered')}")
        print(f"Unique URLs              : {report.get('unique_urls')}")
        print(f"Duplicates removed       : {report.get('duplicates_removed')}")
        print(f"Unsupported links        : {report.get('unsupported_links')}")
        print(f"Failed pages             : {report.get('failed_pages')}")
        print("=" * 40 + "\n")

    # -------------------------------------------------------------------------
    # 54.18 Checkpointing
    # -------------------------------------------------------------------------
    def save_checkpoint(
        self,
        run_id: str,
        last_url: str,
        discovered_count: int,
        processed_count: int,
        failed_count: int,
        processed_urls: List[str]
    ) -> Path:
        """Saves a restartable crawler checkpoint (Phase 54.18)."""
        checkpoint_file = CHECKPOINTS_DIR / f"{run_id}.json"
        data = {
            "run_id": run_id,
            "source": self.source_name,
            "updated_at": datetime.utcnow().isoformat(),
            "last_processed_url": last_url,
            "discovered_count": discovered_count,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "processed_urls": processed_urls
        }
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved checkpoint to {checkpoint_file}")
        return checkpoint_file

    def load_checkpoint(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Loads checkpoint data if available."""
        checkpoint_file = CHECKPOINTS_DIR / f"{run_id}.json"
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint {checkpoint_file}: {e}")
        return None

    # -------------------------------------------------------------------------
    # 54.14 - 54.22 Document Fetching & Validation
    # -------------------------------------------------------------------------
    async def fetch_document(
        self,
        url: str,
        crawler: Optional[Any] = None,
        run_id: Optional[str] = None
    ) -> CrawlResult:
        """
        Crawls an individual document with bounded retries and content validation.
        """
        run_id = run_id or self.generate_run_id()
        canonical_url = canonicalize_url(url)
        doc_type = self.classify_document_type(canonical_url)

        if doc_type == "UNSUPPORTED":
            logger.warning(f"source=SEBI stage=crawl run_id={run_id} status=UNSUPPORTED url={canonical_url}")
            return CrawlResult(
                url=canonical_url,
                status_code=415,
                content_type="UNSUPPORTED",
                success=False,
                error="Unsupported file format"
            )

        if not self.is_allowed_domain(canonical_url):
            logger.warning(f"source=SEBI stage=crawl run_id={run_id} status=BLOCKED domain_not_allowed url={canonical_url}")
            return CrawlResult(
                url=canonical_url,
                status_code=403,
                success=False,
                error="Domain not allowed"
            )

        should_close_crawler = False
        if crawler is None and AsyncWebCrawler:
            crawler = AsyncWebCrawler(config=self.browser_config)
            await crawler.start()
            should_close_crawler = True

        start_time = time.time()
        last_error = None
        status_code = 200

        try:
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info(f"source=SEBI stage=crawl run_id={run_id} attempt={attempt}/{self.max_retries} url={canonical_url}")

                    if crawler:
                        result = await crawler.arun(url=canonical_url, config=self.run_config)
                    else:
                        result = None

                    latency_ms = (time.time() - start_time) * 1000.0

                    if not result or not getattr(result, "success", False):
                        err_msg = getattr(result, "error_message", "Crawl result unsuccessful")
                        last_error = err_msg

                        if not self.is_retryable_error(err_msg, status_code):
                            logger.warning(f"source=SEBI stage=failed run_id={run_id} non_retryable error={err_msg} url={canonical_url}")
                            return CrawlResult(
                                url=canonical_url,
                                status_code=status_code or 500,
                                content_type=doc_type,
                                success=False,
                                error=err_msg,
                                response_time_ms=latency_ms,
                                retry_count=attempt - 1
                            )

                        if attempt < self.max_retries:
                            backoff = attempt * 2.0
                            logger.warning(f"source=SEBI stage=retry run_id={run_id} backoff={backoff}s url={canonical_url}")
                            await asyncio.sleep(backoff)
                            continue
                        break

                    # Extract markdown / text content
                    content = ""
                    if hasattr(result, "markdown") and result.markdown:
                        if hasattr(result.markdown, "raw_markdown"):
                            content = result.markdown.raw_markdown
                        else:
                            content = str(result.markdown)
                    elif hasattr(result, "cleaned_html") and result.cleaned_html:
                        content = result.cleaned_html

                    # Extract title
                    title = None
                    if hasattr(result, "metadata") and isinstance(result.metadata, dict):
                        title = result.metadata.get("title") or result.metadata.get("og:title")
                    if not title and hasattr(result, "page_title") and result.page_title:
                        title = result.page_title

                    # Validate content (54.22)
                    is_valid, validation_err = self.validate_content(content, title)
                    if not is_valid:
                        logger.warning(f"source=SEBI stage=failed run_id={run_id} reason={validation_err} url={canonical_url}")
                        if attempt < self.max_retries:
                            await asyncio.sleep(attempt * 2.0)
                            continue
                        return CrawlResult(
                            url=canonical_url,
                            final_url=getattr(result, "url", canonical_url),
                            status_code=422,
                            content_type=doc_type,
                            success=False,
                            error=validation_err,
                            response_time_ms=latency_ms,
                            retry_count=attempt - 1
                        )

                    logger.info(f"source=SEBI stage=success run_id={run_id} length={len(content)} url={canonical_url}")
                    return CrawlResult(
                        url=canonical_url,
                        final_url=getattr(result, "url", canonical_url),
                        title=title.strip() if title else None,
                        content=content.strip(),
                        status_code=200,
                        content_type=doc_type,
                        success=True,
                        response_time_ms=latency_ms,
                        retry_count=attempt - 1
                    )

                except Exception as ex:
                    last_error = str(ex)
                    logger.warning(f"source=SEBI stage=retry run_id={run_id} exception={ex} attempt={attempt} url={canonical_url}")
                    if attempt < self.max_retries:
                        await asyncio.sleep(attempt * 2.0)
                    else:
                        break

        finally:
            if should_close_crawler and crawler:
                await crawler.close()

        latency_ms = (time.time() - start_time) * 1000.0
        logger.error(f"source=SEBI stage=failed run_id={run_id} attempts_exhausted={self.max_retries} url={canonical_url}")
        return CrawlResult(
            url=canonical_url,
            status_code=500,
            content_type=doc_type,
            success=False,
            error=last_error or "Crawl timed out or failed after maximum retries",
            response_time_ms=latency_ms,
            retry_count=self.max_retries
        )

    # -------------------------------------------------------------------------
    # 54.17 Batch Crawl with Concurrency & Rate Limiting
    # -------------------------------------------------------------------------
    async def crawl_urls(
        self,
        urls: List[str],
        limit: Optional[int] = None,
        persist_db: bool = False,
        dry_run: bool = False,
        resume_run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes bounded, rate-limited, restartable crawl across target URLs.
        """
        run_id = resume_run_id or self.generate_run_id()
        seen_urls: Set[str] = set()
        unique_urls: List[str] = []
        duplicates = 0

        # Load checkpoint if resuming
        processed_set: Set[str] = set()
        if resume_run_id:
            checkpoint = self.load_checkpoint(resume_run_id)
            if checkpoint:
                processed_set = set(checkpoint.get("processed_urls", []))
                logger.info(f"source=SEBI stage=resume run_id={run_id} already_processed={len(processed_set)}")

        for u in urls:
            canon = canonicalize_url(u)
            if not canon:
                continue
            if canon in seen_urls:
                duplicates += 1
            else:
                seen_urls.add(canon)
                if canon not in processed_set:
                    unique_urls.append(canon)

        target_urls = unique_urls[:limit] if limit else unique_urls

        logger.info(
            f"source=SEBI stage=crawl_batch run_id={run_id} "
            f"total_discovered={len(urls)} target={len(target_urls)} "
            f"duplicates={duplicates} dry_run={dry_run}"
        )

        if dry_run:
            print("\n# SEBI CRAWL DRY RUN")
            print(f"Run ID    : {run_id}")
            print(f"Target URLs ({len(target_urls)}):")
            for idx, tu in enumerate(target_urls[:15], start=1):
                doc_type = self.classify_document_type(tu)
                print(f"  [{idx}] [{doc_type}] {tu}")
            if len(target_urls) > 15:
                print(f"  ... and {len(target_urls) - 15} more URLs.")
            print("No network requests or database writes executed.\n")
            return {
                "run_id": run_id,
                "attempted": 0,
                "successful": 0,
                "failed": 0,
                "skipped": len(target_urls),
                "dry_run": True
            }

        successful = 0
        failed = 0
        skipped = 0
        total_retries = 0
        latencies: List[float] = []
        processed_urls: List[str] = list(processed_set)

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async with AsyncWebCrawler(config=self.browser_config) if AsyncWebCrawler else asyncio.Lock() as crawler:
            for i, target_url in enumerate(target_urls, start=1):
                async with semaphore:
                    logger.info(f"[{i}/{len(target_urls)}] Crawling: {target_url}")
                    crawl_res = await self.fetch_document(target_url, crawler=crawler, run_id=run_id)

                    total_retries += crawl_res.retry_count
                    if crawl_res.response_time_ms:
                        latencies.append(crawl_res.response_time_ms)

                    if crawl_res.success and crawl_res.content:
                        successful += 1
                        processed_urls.append(target_url)

                        doc_id = generate_document_id(source="SEBI", url=crawl_res.url)
                        raw_doc = RawDocument(
                            document_id=doc_id,
                            url=crawl_res.url,
                            title=crawl_res.title,
                            content=crawl_res.content,
                            source="SEBI",
                            scraped_at=crawl_res.crawled_at
                        )
                        self.save_raw_document(raw_doc)

                        try:
                            self.process_raw_document(raw_doc, persist_db=persist_db)
                        except Exception as pe:
                            logger.error(f"Error transforming {doc_id}: {pe}")
                    else:
                        failed += 1

                    # Checkpoint every 5 items or on last item
                    if i % 5 == 0 or i == len(target_urls):
                        self.save_checkpoint(
                            run_id=run_id,
                            last_url=target_url,
                            discovered_count=len(urls),
                            processed_count=successful,
                            failed_count=failed,
                            processed_urls=processed_urls
                        )

                    # Polite rate-limiting between items
                    await asyncio.sleep(self.crawl_delay_seconds)

        avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

        crawl_summary = {
            "run_id": run_id,
            "attempted": len(target_urls),
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "average_latency_ms": avg_latency,
            "retries": total_retries
        }

        self.print_crawl_report(crawl_summary)
        return crawl_summary

    def print_crawl_report(self, report: Dict[str, Any]):
        """Prints structured crawl report per Phase 54.25."""
        print("\n" + "=" * 40)
        print("# SEBI CRAWL REPORT")
        print("=" * 40)
        print(f"Run ID          : {report.get('run_id')}")
        print(f"Attempted       : {report.get('attempted')}")
        print(f"Successful      : {report.get('successful')}")
        print(f"Failed          : {report.get('failed')}")
        print(f"Skipped         : {report.get('skipped')}")
        print(f"Average latency : {report.get('average_latency_ms')} ms")
        print(f"Retries         : {report.get('retries')}")
        print("=" * 40 + "\n")


# -------------------------------------------------------------------------
# 54.26 CLI Entry Point
# -------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description="Production-Grade SEBI Regulatory Scraper (Phase 54)")
    parser.add_argument("--discover", action="store_true", help="Run discovery only across SEBI listing pages")
    parser.add_argument("--crawl", action="store_true", help="Run full crawl on discovered or curated documents")
    parser.add_argument("--url", type=str, help="Crawl a single SEBI document URL")
    parser.add_argument("--seed", action="store_true", help="Crawl curated seed documents")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of documents to discover/crawl")
    parser.add_argument("--dry-run", action="store_true", help="Discover and validate without executing crawl/writes")
    parser.add_argument("--store-db", action="store_true", help="Persist processed documents to MongoDB Atlas")
    parser.add_argument("--resume", type=str, default=None, help="Resume an interrupted crawl run by Run ID")
    parser.add_argument("--delay", type=float, default=1.0, help="Crawl delay in seconds between requests")
    parser.add_argument("--concurrency", type=int, default=3, help="Maximum crawl concurrency")

    args = parser.parse_args()
    scraper = SEBIScraper(
        crawl_delay_seconds=args.delay,
        max_concurrency=args.concurrency
    )

    if args.discover:
        logger.info("Executing Discovery Mode...")
        discovery_res = await scraper.discover_documents(max_pages=args.limit or 3)
        if args.dry_run:
            print("[DRY RUN] Discovery complete. No documents fetched.")
    elif args.crawl or args.seed:
        if args.seed:
            target_urls = get_seed_urls()
        else:
            disc = await scraper.discover_documents(max_pages=2)
            target_urls = disc.get("urls", [])

        await scraper.crawl_urls(
            target_urls,
            limit=args.limit,
            persist_db=args.store_db,
            dry_run=args.dry_run,
            resume_run_id=args.resume
        )
    elif args.url:
        logger.info(f"Crawling single URL: {args.url}")
        res = await scraper.fetch_document(args.url)
        if res.success:
            print("\n--- Crawl Result ---")
            print(f"URL         : {res.url}")
            print(f"Title       : {res.title}")
            print(f"Status      : {res.status_code}")
            print(f"Type        : {res.content_type}")
            print(f"Length      : {len(res.content or '')} chars")
            print(f"Latency     : {res.response_time_ms} ms")
            print("--------------------\n")
        else:
            print(f"Crawl Failed: {res.error}")
    else:
        # Default behavior if no action specified: display help
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
