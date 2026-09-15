"""
RBI Regulatory Connector (Phase 66).

Production-grade connector for the Reserve Bank of India (RBI).
Handles:
- Discovery across RBI notifications, master directions, and circular archives
- Extraction of RBI reference codes (e.g., RBI/2023-24/105, DOR.STR.REC.45/21.04.048/2023-24)
- Department resolution (Department of Regulation, DPSS, FMRD, FIDD, etc.)
- Normalization into common RegulatoryDocument model
- Relationship detection (amends, supersedes, clarifies, modifies)
- Polite Crawl4AI / HTTP fetching with backoff
"""

import re
import time
import logging
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse

from app.connectors.authority import RegulatoryAuthority
from app.connectors.base import BaseRegulatoryConnector, CrawlResult
from app.connectors.registry import RegulatorySource, source_registry, connector_registry
from app.ingestion.models import RawDocument, RegulatoryDocument, DocumentMetadata
from app.ingestion.cleaner import clean_markdown
from app.ingestion.metadata import derive_title_from_url_or_content

logger = logging.getLogger("regintel.connectors.rbi")

# Curated seed documents from RBI for high-value banking and fintech regulations
RBI_CURATED_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "url": "https://www.rbi.org.in/Scripts/BS_ViewMasterDirections.aspx?id=12030",
        "title": "Master Direction – Reserve Bank of India (Digital Payment Security Controls) Directions, 2021",
        "expected_document_type": "Master Direction",
        "expected_category": "Payment & Settlement Systems",
        "reference_number": "RBI/2020-21/74",
        "department": "Department of Payment and Settlement Systems",
        "date_hint": "2021-02-18"
    },
    {
        "url": "https://www.rbi.org.in/Scripts/BS_ViewMasterDirections.aspx?id=11566",
        "title": "Master Direction - Know Your Customer (KYC) Direction, 2016",
        "expected_document_type": "Master Direction",
        "expected_category": "Banking Regulation",
        "reference_number": "DBR.AML.BC.No.81/14.01.001/2015-16",
        "department": "Department of Regulation",
        "date_hint": "2016-02-25"
    },
    {
        "url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12530&Mode=0",
        "title": "Fair Lending Practice - Penal Charges in Loan Accounts",
        "expected_document_type": "Circular",
        "expected_category": "Banking Regulation",
        "reference_number": "RBI/2023-24/53",
        "department": "Department of Regulation",
        "date_hint": "2023-08-18"
    },
    {
        "url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12400&Mode=0",
        "title": "Guidelines on Default Loss Guarantee (DLG) in Digital Lending",
        "expected_document_type": "Guideline",
        "expected_category": "Banking Regulation",
        "reference_number": "RBI/2023-24/41",
        "department": "Department of Regulation",
        "date_hint": "2023-06-08"
    },
    {
        "url": "https://www.rbi.org.in/Scripts/BS_ViewMasterCirculardetails.aspx?id=12245",
        "title": "Master Circular - Prudential Norms on Income Recognition, Asset Classification and Provisioning pertaining to Advances",
        "expected_document_type": "Master Circular",
        "expected_category": "Banking Regulation",
        "reference_number": "RBI/2022-23/15",
        "department": "Department of Regulation",
        "date_hint": "2022-04-01"
    }
]

# Regex patterns for RBI reference numbers
RBI_REF_PATTERNS = [
    # Primary: RBI/2023-24/105
    re.compile(r"RBI/(?:20\d{2}-\d{2,4})/\d+", re.IGNORECASE),
    # Department specific circular codes
    re.compile(r"(?:DOR|DPSS|FIDD|FMRD|DBR|DNBR|FMD|IDMD|FED|DoS|DGBA)[\.\w\-/]+/\d{4}-\d{2,4}", re.IGNORECASE),
    re.compile(r"(?:DOR|DPSS|FIDD|FMRD|DBR|DNBR|FMD|IDMD|FED|DoS|DGBA)\.[\w\.\-/]+", re.IGNORECASE),
]

# Known RBI departments
RBI_DEPARTMENTS = [
    "Department of Regulation",
    "Department of Payment and Settlement Systems",
    "Financial Markets Regulation Department",
    "Financial Inclusion and Development Department",
    "Foreign Exchange Department",
    "Internal Debt Management Department",
    "Department of Supervision",
    "Monetary Policy Department",
    "Department of Government and Bank Accounts",
    "Financial Stability Department"
]

# Date patterns in RBI circular headers
RBI_DATE_PATTERNS = [
    re.compile(r"(?:Dated\s*:?\s*)?([A-Za-z]+ \d{1,2},? \d{4})", re.IGNORECASE),
    re.compile(r"(?:Dated\s*:?\s*)?(\d{1,2} [A-Za-z]+,? \d{4})", re.IGNORECASE),
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(\d{1,2}/\d{1,2}/\d{4})")
]


class RBIConnector(BaseRegulatoryConnector):
    """
    Official connector for the Reserve Bank of India (RBI).
    """

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

    @property
    def authority(self) -> RegulatoryAuthority:
        return RegulatoryAuthority.RBI

    @property
    def allowed_domains(self) -> List[str]:
        return ["rbi.org.in", "www.rbi.org.in"]

    async def discover_sources(self) -> List[RegulatorySource]:
        """Returns official registered sources for RBI."""
        return source_registry.get_sources(authority=self.authority, enabled_only=True)

    async def discover_documents(
        self,
        source: Optional[RegulatorySource] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Discovers candidate document URLs from curated seeds and RBI source listings."""
        candidates = []

        # 1. Curated documents
        for doc in RBI_CURATED_DOCUMENTS:
            candidates.append({
                "url": doc["url"],
                "title": doc.get("title"),
                "authority": self.authority.value,
                "source": self.authority.value,
                "document_type": doc.get("expected_document_type", "Notification"),
                "category": doc.get("expected_category", "Banking Regulation"),
                "reference_number": doc.get("reference_number"),
                "department": doc.get("department"),
                "date_hint": doc.get("date_hint")
            })

        # 2. Dynamic listing page crawl if source provided and crawler available
        if source and source.listing_url:
            try:
                # Discover links from listing HTML
                crawl_res = await self.fetch_document(source.listing_url)
                if crawl_res.success and crawl_res.content:
                    extracted_links = self._extract_links_from_html(crawl_res.content, source.listing_url)
                    for u in extracted_links:
                        candidates.append({
                            "url": u,
                            "authority": self.authority.value,
                            "source": self.authority.value,
                            "document_type": source.document_types[0] if source.document_types else "Notification",
                            "category": source.category or "Banking Regulation"
                        })
            except Exception as e:
                logger.warning(f"Failed dynamic link discovery on RBI source {source.name}: {e}")

        # Deduplicate candidates by canonical URL
        seen: Set[str] = set()
        unique_candidates = []
        for c in candidates:
            c_url = self.canonicalize(c["url"])
            if c_url not in seen:
                seen.add(c_url)
                c_copy = dict(c)
                c_copy["url"] = c_url
                unique_candidates.append(c_copy)

        if limit and limit > 0:
            return unique_candidates[:limit]
        return unique_candidates

    def _extract_links_from_html(self, html_text: str, base_url: str) -> List[str]:
        """Extracts valid RBI document URLs matching notification/direction patterns."""
        links = []
        pattern = re.compile(r'href=[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
        for match in pattern.finditer(html_text):
            raw_link = match.group(1).strip()
            if not raw_link or raw_link.startswith(("#", "javascript:", "mailto:")):
                continue
            abs_url = urljoin(base_url, raw_link)
            if not self.is_allowed_domain(abs_url):
                continue

            lower = abs_url.lower()
            if (
                "notificationuser.aspx" in lower
                or "bs_viewmasterdirections.aspx" in lower
                or "bs_viewmastercirculardetails.aspx" in lower
                or "bs_circularindexdisplay.aspx" in lower
                or lower.endswith(".pdf")
            ):
                links.append(abs_url)
        return links

    async def fetch_document(self, url: str) -> CrawlResult:
        """Fetches and extracts text content from an RBI document."""
        canonical_url = self.canonicalize(url)
        if not self.is_allowed_domain(canonical_url):
            return CrawlResult(
                url=canonical_url,
                status_code=400,
                success=False,
                error=f"Domain not allowed for RBI: {url}"
            )

        start_time = time.time()

        # Attempt fetch via httpx or requests
        try:
            import httpx
            headers = {
                "User-Agent": "RegIntel Regulatory Intelligence/1.0 (+https://regintel.ai; compliance-bot)",
                "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8"
            }
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(canonical_url, headers=headers)
                latency_ms = (time.time() - start_time) * 1000.0

                if resp.status_code != 200:
                    return CrawlResult(
                        url=canonical_url,
                        status_code=resp.status_code,
                        success=False,
                        error=f"HTTP {resp.status_code}",
                        response_time_ms=latency_ms
                    )

                content_type = resp.headers.get("content-type", "").lower()
                if "application/pdf" in content_type or canonical_url.lower().endswith(".pdf"):
                    # Extract PDF text
                    try:
                        import pypdf
                        import io
                        reader = pypdf.PdfReader(io.BytesIO(resp.content))
                        text_pages = [page.extract_text() or "" for page in reader.pages]
                        content = "\n\n".join(text_pages).strip()
                        doc_type = "PDF"
                    except Exception as pdf_err:
                        content = ""
                        doc_type = "PDF"
                        return CrawlResult(
                            url=canonical_url,
                            status_code=422,
                            content_type="PDF",
                            success=False,
                            error=f"PDF extraction failed: {pdf_err}",
                            response_time_ms=latency_ms
                        )
                else:
                    content = resp.text
                    doc_type = "HTML"

                is_valid, val_err = self.validate_content(content)
                if not is_valid:
                    return CrawlResult(
                        url=canonical_url,
                        status_code=422,
                        content_type=doc_type,
                        success=False,
                        error=val_err,
                        response_time_ms=latency_ms
                    )

                # Derive title
                title = None
                title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    title = re.sub(r"\s*-\s*Reserve Bank of India.*$", "", title, flags=re.IGNORECASE).strip()

                return CrawlResult(
                    url=canonical_url,
                    title=title,
                    content=content,
                    status_code=200,
                    content_type=doc_type,
                    success=True,
                    response_time_ms=latency_ms
                )
        except Exception as ex:
            return CrawlResult(
                url=canonical_url,
                status_code=500,
                success=False,
                error=str(ex),
                response_time_ms=(time.time() - start_time) * 1000.0
            )

    def extract_metadata(
        self,
        text: str,
        title: Optional[str] = None,
        url: Optional[str] = None
    ) -> DocumentMetadata:
        """
        Extracts structured metadata deterministically from RBI circular/notification text.
        Never fabricates numbers or dates; uses None / unknown if absent.
        """
        meta = DocumentMetadata(
            authority=self.authority.value,
            source=self.authority.value,
            status="current"
        )

        clean_text = text or ""
        header_sample = clean_text[:4000]

        # 1. Document Type Classification
        t_lower = (title or "").lower()
        if "master direction" in t_lower or "master directions" in header_sample[:1000].lower():
            meta.document_type = "Master Direction"
        elif "master circular" in t_lower or "master circular" in header_sample[:1000].lower():
            meta.document_type = "Master Circular"
        elif "guideline" in t_lower or "guidelines" in t_lower:
            meta.document_type = "Guideline"
        elif "press release" in t_lower or "press release" in header_sample[:500].lower():
            meta.document_type = "Press Release"
        elif "order" in t_lower:
            meta.document_type = "Order"
        elif "notification" in t_lower or "notification" in header_sample[:500].lower():
            meta.document_type = "Notification"
        elif "circular" in t_lower or "circular" in header_sample[:500].lower():
            meta.document_type = "Circular"
        else:
            meta.document_type = "Notification"

        # 2. Reference / Circular Number Extraction
        for pat in RBI_REF_PATTERNS:
            m = pat.search(header_sample)
            if m:
                meta.circular_number = m.group(0).strip().rstrip(".,;")
                break

        # 3. Department Extraction
        for dept in RBI_DEPARTMENTS:
            if dept.lower() in header_sample.lower():
                meta.section = dept
                break

        # 4. Publication Date Extraction
        pub_date = self._parse_rbi_date(header_sample)
        if pub_date:
            meta.published_date = pub_date

        # 5. Category Resolution
        if meta.section == "Department of Payment and Settlement Systems" or "digital payment" in t_lower:
            meta.category = "Payment & Settlement Systems"
        elif meta.section == "Foreign Exchange Department" or "fema" in t_lower:
            meta.category = "Foreign Exchange"
        elif meta.section == "Financial Markets Regulation Department":
            meta.category = "Financial Markets"
        else:
            meta.category = "Banking Regulation"

        # 6. Relationship Extraction
        meta.relationships = self._extract_relationships(clean_text)
        for rel in meta.relationships:
            rtype = rel.get("type")
            target = rel.get("target_ref")
            if rtype == "SUPERSEDES" and not meta.supersedes and target:
                meta.supersedes = target
            elif rtype == "AMENDS" and not meta.amends and target:
                meta.amends = target
            elif rtype == "REFERENCES" and target:
                if meta.references is None:
                    meta.references = []
                if target not in meta.references:
                    meta.references.append(target)

        return meta

    def _parse_rbi_date(self, text: str) -> Optional[str]:
        """Parses publication date from RBI text into ISO YYYY-MM-DD."""
        for pat in RBI_DATE_PATTERNS:
            m = pat.search(text)
            if m:
                raw_str = m.group(1).replace(",", "").strip()
                # Try parsing formats
                for fmt in ["%B %d %Y", "%d %B %Y", "%b %d %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"]:
                    try:
                        dt = datetime.strptime(raw_str, fmt)
                        return dt.strftime("%Y-%m-%d")
                    except ValueError:
                        pass
        return None

    def _extract_relationships(self, text: str) -> List[Dict[str, Any]]:
        """Identifies explicit relationships (supersedes, amends, modifies) mentioned in text."""
        rels = []
        sample = text[:6000]

        # Supersedes patterns
        supersede_pat = re.compile(
            r"(?:supersedes|repeals|in supersession of)\s+(?:circular|master direction|direction|notification|guidelines?)?\s*(?:no\.?)?\s*([A-Za-z0-9/\.\-]+)",
            re.IGNORECASE
        )
        for m in supersede_pat.finditer(sample):
            target = m.group(1).strip().rstrip(".,;")
            if len(target) > 5 and "/" in target:
                rels.append({
                    "type": "SUPERSEDES",
                    "target_ref": target,
                    "evidence": m.group(0),
                    "is_explicit": True
                })

        # Amends / Modifies patterns
        amend_pat = re.compile(
            r"(?:amends|in partial modification of|modifies)\s+(?:circular|master direction|notification)?\s*(?:no\.?)?\s*([A-Za-z0-9/\.\-]+)",
            re.IGNORECASE
        )
        for m in amend_pat.finditer(sample):
            target = m.group(1).strip().rstrip(".,;")
            if len(target) > 5 and "/" in target:
                rels.append({
                    "type": "AMENDS",
                    "target_ref": target,
                    "evidence": m.group(0),
                    "is_explicit": True
                })

        # References patterns
        ref_pat = re.compile(
            r"(?:please refer to|attention is invited to|reference is invited to)\s+(?:circular|master direction)?\s*(?:no\.?)?\s*([A-Za-z0-9/\.\-]+)",
            re.IGNORECASE
        )
        for m in ref_pat.finditer(sample):
            target = m.group(1).strip().rstrip(".,;")
            if len(target) > 5 and "/" in target:
                rels.append({
                    "type": "REFERENCES",
                    "target_ref": target,
                    "evidence": m.group(0),
                    "is_explicit": True
                })

        return rels


# Instantiate and register
rbi_connector = RBIConnector()
connector_registry.register(rbi_connector)
