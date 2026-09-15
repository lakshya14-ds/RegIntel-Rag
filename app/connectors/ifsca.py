"""
IFSCA Regulatory Connector (Phase 69).

Production-grade connector for the International Financial Services Centres Authority (IFSCA).
Handles:
- Discovery across IFSCA regulations, circulars, frameworks, and directions
- Extraction of IFSCA reference standards (e.g. IFSCA/2024-25/GN/REG045, F.No. 123/IFSCA/Banking/2024-25)
- Division classification (Banking, Capital Markets, Insurance, FinTech, Fund Management)
- Normalization into common RegulatoryDocument model
- Relationship detection (amends, supersedes, clarifies, references)
- Polite Crawl4AI / HTTP fetching with backoff
"""

import re
import time
import logging
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

from app.connectors.authority import RegulatoryAuthority
from app.connectors.base import BaseRegulatoryConnector, CrawlResult
from app.connectors.registry import RegulatorySource, source_registry, connector_registry
from app.ingestion.models import RawDocument, RegulatoryDocument, DocumentMetadata

logger = logging.getLogger("regintel.connectors.ifsca")

# Curated seed documents from IFSCA
IFSCA_CURATED_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "url": "https://ifsca.gov.in/Document/Legal/banking-regulations-2020.pdf",
        "title": "International Financial Services Centres Authority (Banking) Regulations, 2020",
        "expected_document_type": "Regulation",
        "expected_category": "Banking in IFSC",
        "reference_number": "IFSCA/2020-21/GN/REG004",
        "department": "Banking Division",
        "date_hint": "2020-11-20"
    },
    {
        "url": "https://ifsca.gov.in/Document/Legal/fund-management-regulations-2022.pdf",
        "title": "International Financial Services Centres Authority (Fund Management) Regulations, 2022",
        "expected_document_type": "Regulation",
        "expected_category": "Fund Management",
        "reference_number": "IFSCA/2022-23/GN/REG024",
        "department": "Fund Management Division",
        "date_hint": "2022-04-19"
    },
    {
        "url": "https://ifsca.gov.in/Document/Legal/fintech-framework-2022.pdf",
        "title": "Framework for FinTech Entity in the International Financial Services Centres (IFSCs)",
        "expected_document_type": "Framework",
        "expected_category": "FinTech",
        "reference_number": "IFSCA/2022-23/GN/GL001",
        "department": "FinTech Division",
        "date_hint": "2022-04-27"
    }
]

# Regex patterns for IFSCA reference numbers
IFSCA_REF_PATTERNS = [
    re.compile(r"F\.?\s*No\.?\s*[A-Za-z0-9\.\-/]+IFSCA[A-Za-z0-9\.\-/]+", re.IGNORECASE),
    re.compile(r"IFSCA/[A-Za-z0-9\.\-/]+", re.IGNORECASE),
    re.compile(r"F\.?\s*No\.?\s*[A-Za-z0-9\.\-/]+", re.IGNORECASE)
]

IFSCA_DIVISIONS = [
    "Banking Division",
    "Capital Markets Division",
    "Fund Management Division",
    "Fintech Division",
    "Insurance Division",
    "Legal Division",
    "Supervision Division"
]

IFSCA_DATE_PATTERNS = [
    re.compile(r"(?:Dated\s*:?\s*)?([A-Za-z]+ \d{1,2},? \d{4})", re.IGNORECASE),
    re.compile(r"(?:Dated\s*:?\s*)?(\d{1,2} [A-Za-z]+,? \d{4})", re.IGNORECASE),
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(\d{1,2}/\d{1,2}/\d{4})")
]


class IFSCAConnector(BaseRegulatoryConnector):
    """
    Official connector for the International Financial Services Centres Authority (IFSCA).
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
        return RegulatoryAuthority.IFSCA

    @property
    def allowed_domains(self) -> List[str]:
        return ["ifsca.gov.in", "www.ifsca.gov.in"]

    async def discover_sources(self) -> List[RegulatorySource]:
        """Returns official registered sources for IFSCA."""
        return source_registry.get_sources(authority=self.authority, enabled_only=True)

    async def discover_documents(
        self,
        source: Optional[RegulatorySource] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Discovers candidate document URLs from curated seeds and IFSCA listings."""
        candidates = []

        # 1. Curated seeds
        for doc in IFSCA_CURATED_DOCUMENTS:
            candidates.append({
                "url": doc["url"],
                "title": doc.get("title"),
                "authority": self.authority.value,
                "source": self.authority.value,
                "document_type": doc.get("expected_document_type", "Circular"),
                "category": doc.get("expected_category", "International Finance"),
                "reference_number": doc.get("reference_number"),
                "department": doc.get("department"),
                "date_hint": doc.get("date_hint")
            })

        # 2. Dynamic discovery if source provided
        if source and source.listing_url:
            try:
                crawl_res = await self.fetch_document(source.listing_url)
                if crawl_res.success and crawl_res.content:
                    pattern = re.compile(r'href=[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
                    for match in pattern.finditer(crawl_res.content):
                        raw_link = match.group(1).strip()
                        abs_url = urljoin(source.listing_url, raw_link)
                        if self.is_allowed_domain(abs_url) and ("/Document/" in abs_url or abs_url.lower().endswith(".pdf")):
                            candidates.append({
                                "url": abs_url,
                                "authority": self.authority.value,
                                "source": self.authority.value,
                                "document_type": source.document_types[0] if source.document_types else "Circular",
                                "category": source.category or "International Finance"
                            })
            except Exception as e:
                logger.warning(f"Failed dynamic link discovery on IFSCA source {source.name}: {e}")

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

    async def fetch_document(self, url: str) -> CrawlResult:
        """Fetches and extracts text content from an IFSCA document or PDF."""
        canonical_url = self.canonicalize(url)
        if not self.is_allowed_domain(canonical_url):
            return CrawlResult(
                url=canonical_url,
                status_code=400,
                success=False,
                error=f"Domain not allowed for IFSCA: {url}"
            )

        start_time = time.time()
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
                    try:
                        import pypdf
                        import io
                        reader = pypdf.PdfReader(io.BytesIO(resp.content))
                        content = "\n\n".join([page.extract_text() or "" for page in reader.pages]).strip()
                        doc_type = "PDF"
                    except Exception as pdf_err:
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

                title = None
                title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    title = re.sub(r"\s*-\s*IFSCA.*$", "", title, flags=re.IGNORECASE).strip()

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
        """Extracts structured metadata deterministically from IFSCA text."""
        meta = DocumentMetadata(
            authority=self.authority.value,
            source=self.authority.value,
            status="current"
        )

        clean_text = text or ""
        header_sample = clean_text[:4000]

        # 1. Document Type
        t_lower = (title or "").lower()
        if "regulation" in t_lower or "regulations" in t_lower:
            meta.document_type = "Regulation"
        elif "framework" in t_lower or "framework" in header_sample[:1000].lower():
            meta.document_type = "Framework"
        elif "guideline" in t_lower or "guidelines" in t_lower:
            meta.document_type = "Guideline"
        elif "direction" in t_lower:
            meta.document_type = "Direction"
        elif "order" in t_lower:
            meta.document_type = "Order"
        elif "circular" in t_lower or "circular" in header_sample[:500].lower():
            meta.document_type = "Circular"
        elif "notification" in t_lower:
            meta.document_type = "Notification"
        else:
            meta.document_type = "Circular"

        # 2. Reference Number
        # Collect candidate reference numbers in header sample and take the earliest occurrence
        ref_candidates = []
        for pat in IFSCA_REF_PATTERNS:
            for m in pat.finditer(header_sample):
                ref_candidates.append((m.start(), m.group(0).strip().rstrip(".,;")))
        if ref_candidates:
            ref_candidates.sort(key=lambda x: x[0])
            meta.circular_number = ref_candidates[0][1]

        # 3. Division
        for div in IFSCA_DIVISIONS:
            if div.lower() in header_sample.lower():
                meta.section = div
                meta.department = div
                break
        if not meta.department and meta.section:
            meta.department = meta.section

        # 4. Publication Date
        pub_date = self._parse_ifsca_date(header_sample)
        if pub_date:
            meta.published_date = pub_date

        # 4b. Effective Date
        eff_date = self._parse_effective_date(clean_text[:4000])
        if eff_date:
            meta.effective_date = eff_date

        # 5. Category
        if "sandbox" in t_lower or "fintech" in t_lower:
            meta.category = "FinTech / Regulatory Sandbox"
        elif "banking" in t_lower or meta.section == "Banking Division" or "reg004" in (meta.circular_number or "").lower():
            meta.category = "Banking / IBUs"
        elif "fund management" in t_lower or meta.section == "Fund Management Division":
            meta.category = "Fund Management"
        elif "capital market" in t_lower:
            meta.category = "Capital Markets in IFSC"
        else:
            meta.category = "International Finance"

        # 6. Relationships
        meta.relationships = self._extract_relationships(clean_text)
        for rel in meta.relationships:
            if rel.get("type") == "SUPERSEDES" and not meta.supersedes:
                meta.supersedes = rel.get("target_ref")
            elif rel.get("type") == "AMENDS" and not meta.amends:
                meta.amends = rel.get("target_ref")
            elif rel.get("type") == "REFERENCES":
                target = rel.get("target_ref")
                if meta.references is None:
                    meta.references = []
                if target and target not in meta.references:
                    meta.references.append(target)

        return meta

    def _parse_effective_date(self, text: str) -> Optional[str]:
        """Parses effective date from standard regulatory formulations."""
        from app.compliance.date_extractor import parse_calendar_date
        patterns = [
            re.compile(r"(?:with effect from|effective from|w\.e\.f\.?)\s+([A-Za-z0-9, ]{6,30})", re.IGNORECASE),
            re.compile(r"(?:shall come into force on|take effect from|shall be effective from)\s+([A-Za-z0-9, ]{6,30})", re.IGNORECASE),
        ]
        for pat in patterns:
            m = pat.search(text)
            if m:
                raw_snippet = m.group(1).split("\n")[0].rstrip(".,;")
                parsed = parse_calendar_date(raw_snippet)
                if parsed:
                    return parsed
        return None

    def _parse_ifsca_date(self, text: str) -> Optional[str]:
        """Parses publication date from IFSCA text into ISO YYYY-MM-DD."""
        for pat in IFSCA_DATE_PATTERNS:
            m = pat.search(text)
            if m:
                raw_str = m.group(1).replace(",", "").strip()
                for fmt in ["%B %d %Y", "%d %B %Y", "%b %d %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"]:
                    try:
                        dt = datetime.strptime(raw_str, fmt)
                        return dt.strftime("%Y-%m-%d")
                    except ValueError:
                        pass
        return None

    def _extract_relationships(self, text: str) -> List[Dict[str, Any]]:
        """Identifies explicit relationships in IFSCA text."""
        rels = []
        sample = text[:6000]

        supersede_pat = re.compile(
            r"(?:supersedes|in supersession of)\s+(?:(?:the\s+)?(?:earlier\s+)?(?:circular|regulations?|framework)?\s*(?:circular|regulations?|framework)?\s*(?:no\.?)?\s*)?((?:F\.?\s*No\.?\s*)?[A-Za-z0-9\.\-/]+/[A-Za-z0-9\.\-/]+)",
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

        amend_pat = re.compile(
            r"(?:amends|in partial modification of|modifies)\s+(?:(?:the\s+)?(?:earlier\s+)?(?:circular|regulations?|framework)?\s*(?:circular|regulations?|framework)?\s*(?:no\.?)?\s*)?((?:F\.?\s*No\.?\s*)?[A-Za-z0-9\.\-/]+/[A-Za-z0-9\.\-/]+)",
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

        return rels


# Instantiate and register
ifsca_connector = IFSCAConnector()
connector_registry.register(ifsca_connector)
