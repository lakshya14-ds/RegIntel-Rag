import re
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlparse
from app.ingestion.models import DocumentMetadata

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12
}


def parse_to_iso_date(date_str: str) -> Optional[str]:
    """Parses various Indian and standard date formats into ISO YYYY-MM-DD format."""
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip().strip(",.").replace("th,", "").replace("st,", "").replace("nd,", "").replace("rd,", "")
    date_str = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", date_str, flags=re.IGNORECASE)

    # 1. Pattern: YYYY-MM-DD
    iso_match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", date_str)
    if iso_match:
        try:
            y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
            return datetime(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # 2. Pattern: DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY
    dmy_match = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", date_str)
    if dmy_match:
        try:
            d, m, y = int(dmy_match.group(1)), int(dmy_match.group(2)), int(dmy_match.group(3))
            return datetime(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # 3. Pattern: Month DD, YYYY or DD Month YYYY
    word_match1 = re.match(r"^([a-zA-Z]+)\s+(\d{1,2}),?\s+(\d{4})$", date_str)
    if word_match1:
        month_name, day, year = word_match1.group(1).lower(), int(word_match1.group(2)), int(word_match1.group(3))
        if month_name in MONTH_MAP:
            try:
                return datetime(year, MONTH_MAP[month_name], day).strftime("%Y-%m-%d")
            except ValueError:
                return None

    word_match2 = re.match(r"^(\d{1,2})\s+([a-zA-Z]+),?\s+(\d{4})$", date_str)
    if word_match2:
        day, month_name, year = int(word_match2.group(1)), word_match2.group(2).lower(), int(word_match2.group(3))
        if month_name in MONTH_MAP:
            try:
                return datetime(year, MONTH_MAP[month_name], day).strftime("%Y-%m-%d")
            except ValueError:
                return None

    return None


def derive_title_from_url_or_content(url: str, text: str, generic_title: Optional[str] = None) -> Optional[str]:
    """Derives a meaningful document title from URL slug or document headings if page title is generic."""
    GENERIC_TITLES = {"securities and exchange board of india", "sebi", "home", "circulars", "welcome to sebi"}
    
    if generic_title and generic_title.strip().lower() not in GENERIC_TITLES:
        return generic_title.strip()

    # Extract from URL slug (e.g., /master-circular-for-investment-advisers-ias-_83556.html)
    if url:
        parsed = urlparse(url)
        path = parsed.path
        filename = path.split("/")[-1]
        if filename.endswith(".html") or filename.endswith(".htm"):
            filename = filename.rsplit(".", 1)[0]
        # Remove trailing ID like _83556
        slug = re.sub(r"_\d+$", "", filename)
        if slug:
            clean_slug = slug.replace("-", " ").replace("_", " ").title()
            clean_slug = re.sub(r"\bIas\b", "(IAs)", clean_slug)
            clean_slug = re.sub(r"\bMf\b", "MF", clean_slug)
            clean_slug = re.sub(r"\bSebi\b", "SEBI", clean_slug)
            return clean_slug.strip()

    return generic_title


class MetadataExtractor:
    """Deterministic, rule-based metadata extractor for SEBI and regulatory documents."""

    @staticmethod
    def extract_circular_number(text: str, title: str = "") -> Optional[str]:
        """Extracts standard SEBI or RBI circular numbers."""
        combined = f"{title}\n{text[:4000]}"
        patterns = [
            r"\b(SEBI/[A-Z0-9_\-]+(?:/[A-Z0-9_\-]+)+/\d{4}/\d+)\b",
            r"\b(SEBI/[A-Z0-9_\-]+(?:/[A-Z0-9_\-]+)+)\b",
            r"\b(CIR/[A-Z0-9_\-]+/\d{4}/\d+)\b",
            r"\b(CIR/[A-Z0-9_\-]+/[A-Z0-9_\-]+/\d+/\d{4})\b",
            r"\b(SEBI/LAD-NRO/[A-Z0-9_\-]+/\d{4}/\d+)\b",
            r"\b(RBI/\d{4}-\d{2}/\d+)\b"
        ]
        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def extract_dates(text: str, title: str = "", date_hint: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts published_date and effective_date from document text and title.
        Returns (published_date_iso, effective_date_iso).
        """
        published_date = None
        effective_date = None

        if date_hint:
            published_date = parse_to_iso_date(date_hint)

        header_chunk = f"{title}\n{text[:4000]}"

        # Extract published date if not already found
        if not published_date:
            date_patterns = [
                r"\b(?:dated|date:?)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})\b",
                r"\b([A-Za-z]+\s+\d{1,2},?\s+\d{4})\b",
                r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4})\b",
                r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})\b"
            ]
            for pattern in date_patterns:
                match = re.search(pattern, header_chunk, re.IGNORECASE)
                if match:
                    parsed = parse_to_iso_date(match.group(1))
                    if parsed:
                        published_date = parsed
                        break

        # Extract effective date
        effective_patterns = [
            r"(?i)(?:with\s+effect\s+from|effective\s+from|applicable\s+with\s+effect\s+from|w\.e\.f\.?|(?:shall\s+)?come\s+into\s+force\s+on)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})",
            r"(?i)(?:effective\s+date\s*:\s*)([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})"
        ]
        for pattern in effective_patterns:
            match = re.search(pattern, text[:6000], re.IGNORECASE)
            if match:
                parsed = parse_to_iso_date(match.group(1))
                if parsed:
                    effective_date = parsed
                    break

        return published_date, effective_date

    @staticmethod
    def extract_document_type(title: str, text: str = "") -> Optional[str]:
        """Classifies the regulatory document type deterministically."""
        combined = f"{title}\n{text[:2000]}".lower()

        if "master circular" in combined:
            return "Master Circular"
        if "consultation paper" in combined:
            return "Consultation Paper"
        if "advisory" in combined:
            return "Advisory"
        if "gazette notification" in combined:
            return "Gazette Notification"
        if "notification" in combined:
            return "Notification"
        if "order in the matter of" in combined or "adjudication order" in combined or "final order" in combined:
            return "Order"
        if "circular" in combined:
            return "Circular"
        if "press release" in combined:
            return "Press Release"

        return None

    @staticmethod
    def extract_category(title: str, text: str = "", url: str = "") -> Optional[str]:
        """
        Classifies the regulatory document into one of the key domains:
        - Investment Adviser
        - Mutual Funds
        - Market Intermediaries
        - Securities Markets
        Or None if no high-confidence match.
        """
        combined = f"{url} {title} {text[:4000]}".lower()

        # 1. Investment Adviser & Research Analyst
        if re.search(r"\b(investment advisers?|investment advisors?|investment advisory|research analysts?|ria|ias|ia regulations)\b", combined):
            return "Investment Adviser"

        # 2. Mutual Funds
        if re.search(r"\b(mutual funds?|amcs?|asset management compan(?:y|ies)|amfi|net asset values?|nav|etfs?|exchange traded funds?)\b", combined):
            return "Mutual Funds"

        # 3. Market Intermediaries
        if re.search(r"\b(market intermediar(?:y|ies)|stock brokers?|depositor(?:y|ies)|depository participants?|clearing members?|merchant bankers?|custodians?|kyc registration agenc(?:y|ies)|kras?|registries)\b", combined):
            return "Market Intermediaries"

        # 4. Securities Markets / Listing Regulations
        if re.search(r"\b(listing obligations?|lodr|disclosure requirements?|insider trading|pit regulations?|takeovers?|secondary markets?|equity shares?|debt securities|listing)\b", combined):
            return "Securities Markets"

        return None

    @classmethod
    def extract(
        cls,
        text: str,
        title: Optional[str] = None,
        url: Optional[str] = None,
        date_hint: Optional[str] = None
    ) -> DocumentMetadata:
        """Runs the complete rule-based metadata extraction pipeline."""
        resolved_title = derive_title_from_url_or_content(url=url or "", text=text or "", generic_title=title)
        title_str = resolved_title or title or ""
        text_str = text or ""
        url_str = url or ""

        circular_number = cls.extract_circular_number(text_str, title_str)
        published_date, effective_date = cls.extract_dates(text_str, title_str, date_hint)
        doc_type = cls.extract_document_type(title_str, text_str)
        category = cls.extract_category(title_str, text_str, url_str)

        return DocumentMetadata(
            document_type=doc_type,
            category=category,
            circular_number=circular_number,
            published_date=published_date,
            effective_date=effective_date,
            section=None
        )


def extract_document_metadata(
    text: str,
    title: Optional[str] = None,
    url: Optional[str] = None,
    source: Optional[str] = "SEBI"
) -> dict:
    """Convenience function returning dictionary representation of extracted metadata."""
    meta = RegulatoryMetadataExtractor.extract(text=text, title=title, url=url)
    d = meta.model_dump()
    d["title"] = derive_title_from_url_or_content(url=url or "", text=text or "", generic_title=title)
    return d
