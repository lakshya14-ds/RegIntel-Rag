"""
IRDAI Regulatory Connector (Phase 67).

Production-grade connector for the Insurance Regulatory and Development Authority of India (IRDAI).
Handles:
- Discovery across IRDAI circulars, regulations, and master circulars
- Extraction of IRDAI reference formats (e.g. IRDAI/NL/CIR/MOT/123/05/2024, IRDA/F&I/CIR/INV/045/03/2023)
- Department resolution (Life, Non-Life, Health, Actuarial, Finance)
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

logger = logging.getLogger("regintel.connectors.irdai")

# Curated seed documents from IRDAI
IRDAI_CURATED_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "url": "https://irdai.gov.in/document-detail?documentId=4928172",
        "title": "Master Circular on Protection of Policyholders' Interests, 2024",
        "expected_document_type": "Master Circular",
        "expected_category": "Insurance",
        "reference_number": "IRDAI/NL/CIR/MOT/105/06/2024",
        "department": "Consumer Affairs Department",
        "date_hint": "2024-06-19"
    },
    {
        "url": "https://irdai.gov.in/document-detail?documentId=4820150",
        "title": "Master Circular on Health Insurance Business",
        "expected_document_type": "Master Circular",
        "expected_category": "Health Insurance",
        "reference_number": "IRDAI/HLT/CIR/PRO/095/05/2024",
        "department": "Health Department",
        "date_hint": "2024-05-29"
    },
    {
        "url": "https://irdai.gov.in/document-detail?documentId=4519200",
        "title": "Master Circular on Life Insurance Products",
        "expected_document_type": "Master Circular",
        "expected_category": "Life Insurance",
        "reference_number": "IRDAI/ACTL/CIR/PRO/080/04/2024",
        "department": "Life Department",
        "date_hint": "2024-04-15"
    }
]

# Regex patterns for IRDAI reference numbers
IRDAI_REF_PATTERNS = [
    re.compile(r"IRDAI?/(?:[A-Za-z0-9&\-]+/){2,6}\d{2,4}(?:-\d{2,4})?", re.IGNORECASE),
    re.compile(r"IRDAI?/[A-Za-z0-9\.\-/]+/\d{2,4}", re.IGNORECASE),
]

# Known IRDAI departments
IRDAI_DEPARTMENTS = [
    "Consumer Affairs Department",
    "Health Department",
    "Life Department",
    "Non-Life Department",
    "Actuarial Department",
    "Finance and Accounts Department",
    "Inspection Department",
    "Intermediaries Department",
    "Re-insurance Department"
]

IRDAI_DATE_PATTERNS = [
    re.compile(r"(?:Dated\s*:?\s*)?([A-Za-z]+ \d{1,2},? \d{4})", re.IGNORECASE),
    re.compile(r"(?:Dated\s*:?\s*)?(\d{1,2} [A-Za-z]+,? \d{4})", re.IGNORECASE),
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(\d{1,2}/\d{1,2}/\d{4})")
]


class IRDAIConnector(BaseRegulatoryConnector):
    """
    Official connector for the Insurance Regulatory and Development Authority of India (IRDAI).
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
        return RegulatoryAuthority.IRDAI

    @property
    def allowed_domains(self) -> List[str]:
        return ["irdai.gov.in", "www.irdai.gov.in"]

    async def discover_sources(self) -> List[RegulatorySource]:
        """Returns official registered sources for IRDAI."""
        return source_registry.get_sources(authority=self.authority, enabled_only=True)

    async def discover_documents(
        self,
        source: Optional[RegulatorySource] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Discovers candidate document URLs from curated seeds and IRDAI listings."""
        candidates = []

        # 1. Curated seeds
        for doc in IRDAI_CURATED_DOCUMENTS:
            candidates.append({
                "url": doc["url"],
                "title": doc.get("title"),
                "authority": self.authority.value,
                "source": self.authority.value,
                "document_type": doc.get("expected_document_type", "Circular"),
                "category": doc.get("expected_category", "Insurance"),
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
                        if self.is_allowed_domain(abs_url) and ("document-detail" in abs_url or abs_url.lower().endswith(".pdf")):
                            candidates.append({
                                "url": abs_url,
                                "authority": self.authority.value,
                                "source": self.authority.value,
                                "document_type": source.document_types[0] if source.document_types else "Circular",
                                "category": source.category or "Insurance"
                            })
            except Exception as e:
                logger.warning(f"Failed dynamic link discovery on IRDAI source {source.name}: {e}")

        # Deduplicate
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
        """Fetches and extracts text content from an IRDAI document or PDF."""
        canonical_url = self.canonicalize(url)
        if not self.is_allowed_domain(canonical_url):
            return CrawlResult(
                url=canonical_url,
                status_code=400,
                success=False,
                error=f"Domain not allowed for IRDAI: {url}"
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
                    title = re.sub(r"\s*-\s*IRDAI.*$", "", title, flags=re.IGNORECASE).strip()

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
        """Extracts structured metadata deterministically from IRDAI text."""
        meta = DocumentMetadata(
            authority=self.authority.value,
            source=self.authority.value,
            status="current"
        )

        clean_text = text or ""
        header_sample = clean_text[:4000]

        # 1. Document Type
        t_lower = (title or "").lower()
        if "master circular" in t_lower or "master circular" in header_sample[:1000].lower():
            meta.document_type = "Master Circular"
        elif "regulation" in t_lower:
            meta.document_type = "Regulation"
        elif "guideline" in t_lower or "guidelines" in t_lower:
            meta.document_type = "Guideline"
        elif "exposure draft" in t_lower:
            meta.document_type = "Exposure Draft"
        elif "order" in t_lower:
            meta.document_type = "Order"
        elif "circular" in t_lower or "circular" in header_sample[:500].lower():
            meta.document_type = "Circular"
        else:
            meta.document_type = "Circular"

        # 2. Reference Number
        for pat in IRDAI_REF_PATTERNS:
            m = pat.search(header_sample)
            if m:
                meta.circular_number = m.group(0).strip().rstrip(".,;")
                break

        # 3. Department
        for dept in IRDAI_DEPARTMENTS:
            if dept.lower() in header_sample.lower():
                meta.section = dept
                meta.department = dept
                break
        if not meta.department and meta.section:
            meta.department = meta.section

        # 4. Publication Date
        pub_date = self._parse_irdai_date(header_sample)
        if pub_date:
            meta.published_date = pub_date

        # 4b. Effective Date
        eff_date = self._parse_effective_date(clean_text[:4000])
        if eff_date:
            meta.effective_date = eff_date

        # 5. Category
        if "motor" in t_lower or "mot" in (meta.circular_number or "").lower():
            meta.category = "Non-Life / Motor Insurance"
        elif "health" in t_lower or meta.section == "Health Department" or "hlt" in (meta.circular_number or "").lower():
            meta.category = "Health Insurance"
        elif "life" in t_lower or meta.section == "Life Department":
            meta.category = "Life Insurance"
        elif "non-life" in t_lower or meta.section == "Non-Life Department":
            meta.category = "Non-Life Insurance"
        else:
            meta.category = "Insurance"

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
            re.compile(r"(?:with effect from|come into force with effect from|effective from|w\.e\.f\.?)\s+([A-Za-z0-9, ]{6,30})", re.IGNORECASE),
            re.compile(r"(?:shall come into force on|take effect from)\s+([A-Za-z0-9, ]{6,30})", re.IGNORECASE),
        ]
        for pat in patterns:
            m = pat.search(text)
            if m:
                raw_snippet = m.group(1).split("\n")[0].rstrip(".,;")
                parsed = parse_calendar_date(raw_snippet)
                if parsed:
                    return parsed
        return None

    def _parse_irdai_date(self, text: str) -> Optional[str]:
        """Parses publication date from IRDAI text into ISO YYYY-MM-DD."""
        for pat in IRDAI_DATE_PATTERNS:
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
        """Identifies explicit relationships in IRDAI circular text."""
        rels = []
        sample = text[:6000]

        supersede_pat = re.compile(
            r"(?:supersedes|in supersession of)\s+(?:circular|master circular|guidelines?)?\s*(?:ref\.?\s*(?:no\.?)?)?\s*([A-Za-z0-9/\.\-]+)",
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
            r"(?:amends|in partial modification of|modifies)\s+(?:circular|guidelines?)?\s*(?:ref\.?\s*(?:no\.?)?)?\s*([A-Za-z0-9/\.\-]+)",
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

        ref_pat = re.compile(
            r"(?:please refer to|attention is drawn to|reference is invited to)\s+(?:circular)?\s*(?:ref\.?\s*(?:no\.?)?)?\s*([A-Za-z0-9/\.\-]+)",
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
irdai_connector = IRDAIConnector()
connector_registry.register(irdai_connector)
