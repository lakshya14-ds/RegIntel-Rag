"""
Query Understanding and Metadata Analysis Module for Regulatory Intelligence.

Analyzes natural-language queries deterministically using controlled domain vocabularies,
extracting source, category, document type, time intent, query type, and exact terms.
"""

import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Controlled Vocabularies
SUPPORTED_SOURCES = {"SEBI", "RBI", "IRDAI", "NSE", "BSE", "Moneycontrol"}

SUPPORTED_CATEGORIES = {
    "Investment Adviser": ["investment adviser", "investment advisers", "investment advisor", "investment advisors", "ria", "rias", "ia", "basl"],
    "Mutual Funds": ["mutual fund", "mutual funds", "amc", "amcs", "etf", "etfs", "index fund", "unit trust"],
    "Market Intermediaries": ["market intermediary", "market intermediaries", "intermediary", "intermediaries", "stock broker", "stock brokers", "broker", "brokers", "research analyst", "research analysts", "portfolio manager", "portfolio managers", "pms"],
    "Securities Markets": ["securities market", "securities markets", "takeover", "takeovers", "lodr", "drhp", "public issue", "listing obligation", "bond platform", "obpp"]
}

SUPPORTED_DOCUMENT_TYPES = {
    "Master Circular": ["master circular", "master circulars"],
    "Circular": ["circular", "circulars"],
    "Order": ["order", "orders", "adjudication", "recovery certificate"],
    "Regulations": ["regulations", "regulation"],
    "DRHP": ["drhp", "draft red herring prospectus"]
}

TIME_INTENT_PATTERNS = {
    "latest": [r"\blatest\b", r"\bnewest\b", r"\bmost recent\b", r"\bnew\b"],
    "current": [r"\bcurrent\b", r"\bcurrently\b", r"\bpresent\b", r"\beffective now\b", r"\bas of now\b", r"\bapplicable now\b"],
    "recent": [r"\brecent\b", r"\brecently\b"],
    "historical": [r"\bold\b", r"\bprevious\b", r"\bprior\b", r"\bhistorical\b", r"\bpast\b", r"\bearlier\b", r"\bsuperseded\b"],
}

QUERY_TYPE_PATTERNS = {
    "change_analysis": [r"what\s+changed", r"changes\s+in", r"change\s+analysis", r"what\s+has\s+changed", r"amendment", r"amendments", r"how\s+has\s+.*changed"],
    "comparison": [r"compare", r"comparison", r"difference\s+between", r"versus", r"\bvs\b"],
    "effective_date": [r"effective\s+date", r"when\s+did\s+.*become\s+effective", r"effective\s+from", r"date\s+of\s+effect"],
    "current_requirement": [r"what\s+are\s+the\s+(?:current|latest)?\s*(?:requirements|rules|guidelines|norms|eligibility|limits)", r"requirements\s+for", r"compliance\s+for"],
    "definition": [r"what\s+is\s+a\b", r"what\s+is\s+an\b", r"define\b", r"definition\s+of"],
    "historical": [r"what\s+were\s+the\s+old", r"historical\s+rules", r"previous\s+rules"]
}

MONTH_MAP = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09", "sept": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12"
}


class QueryIntent(BaseModel):
    """Normalized structured understanding of a user's regulatory query."""
    original_query: str
    source: Optional[str] = None
    category: Optional[str] = None
    document_type: Optional[str] = None
    time_intent: str = Field(default="none")  # latest, current, recent, historical, date_specific, none
    query_type: str = Field(default="general_search")  # current_requirement, historical, definition, factual, effective_date, comparison, change_analysis, general_search
    exact_terms: List[str] = Field(default_factory=list)
    target_date: Optional[str] = None  # ISO YYYY-MM or YYYY-MM-DD or YYYY


def _extract_time_and_date(query: str) -> Tuple[str, Optional[str]]:
    q_lower = query.lower()

    # 1. Check date patterns (e.g. "August 2026", "2024-05-24", "in 2026")
    # ISO date YYYY-MM-DD
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", query)
    if iso_match:
        return "date_specific", iso_match.group(1)

    # Month Year: e.g. "August 2026", "aug 2024"
    month_year_pattern = r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{4})\b"
    my_match = re.search(month_year_pattern, q_lower)
    if my_match:
        m_str, y_str = my_match.group(1), my_match.group(2)
        m_num = MONTH_MAP.get(m_str, "01")
        return "date_specific", f"{y_str}-{m_num}"

    # Year only: e.g. "in 2024", "from 2026"
    year_match = re.search(r"\b(?:in|from|year|during)\s+(20\d{2})\b", q_lower)
    if year_match:
        return "date_specific", year_match.group(1)

    # 2. Check time intent keywords
    for intent, patterns in TIME_INTENT_PATTERNS.items():
        for p in patterns:
            if re.search(p, q_lower):
                return intent, None

    return "none", None


def _extract_query_type(query: str, time_intent: str) -> str:
    q_lower = query.lower()
    for q_type, patterns in QUERY_TYPE_PATTERNS.items():
        for p in patterns:
            if re.search(p, q_lower):
                return q_type

    if time_intent in {"latest", "current", "recent"}:
        return "current_requirement"
    elif time_intent == "historical":
        return "historical"

    return "general_search"


def _extract_exact_terms(query: str) -> List[str]:
    """Extracts exact regulatory identifiers, circular numbers, clauses, and acronyms."""
    terms = []

    # Slashed circular numbers: e.g. SEBI/HO/MIRSD/MIRSD-PoD-2/P/CIR/2024/56
    circular_matches = re.findall(r"\b(?:SEBI|RBI|CIR)/[A-Za-z0-9/\-_]+", query, flags=re.IGNORECASE)
    terms.extend(circular_matches)

    # Regulation numbers: e.g. Regulation 15A, Regulation 12(1)
    reg_matches = re.findall(r"\bRegulation\s+\d+[A-Za-z]?(?:\(\d+\))?", query, flags=re.IGNORECASE)
    terms.extend(reg_matches)

    # Clause / Section: e.g. Clause 4.2, Section 2
    clause_matches = re.findall(r"\b(?:Clause|Section)\s+\d+(?:\.\d+)*", query, flags=re.IGNORECASE)
    terms.extend(clause_matches)

    # Key uppercase acronyms (2-6 letters)
    acronym_matches = re.findall(r"\b[A-Z]{2,6}\b", query)
    for ac in acronym_matches:
        if ac not in {"WHAT", "WHEN", "WHERE", "HOW", "WHO", "WHY", "THE", "FOR", "AND"}:
            if ac not in terms:
                terms.append(ac)

    return list(dict.fromkeys(terms))


class QueryAnalyzer:
    """
    Analyzes user queries to produce structured QueryIntent records.
    """

    @classmethod
    def analyze(cls, query: str) -> QueryIntent:
        if not query or not query.strip():
            return QueryIntent(original_query="")

        clean_query = query.strip()
        source = cls.extract_source(clean_query)
        category = cls.extract_category(clean_query)
        doc_type = cls.extract_document_type(clean_query)
        time_intent, target_date = _extract_time_and_date(clean_query)
        query_type = _extract_query_type(clean_query, time_intent)
        exact_terms = _extract_exact_terms(clean_query)

        # Default source to SEBI if not specified but standard Indian market categories detected
        if source is None and category in {"Investment Adviser", "Mutual Funds", "Market Intermediaries", "Securities Markets"}:
            source = "SEBI"

        intent = QueryIntent(
            original_query=clean_query,
            source=source,
            category=category,
            document_type=doc_type,
            time_intent=time_intent,
            query_type=query_type,
            exact_terms=exact_terms,
            target_date=target_date
        )

        logger.debug(f"Analyzed QueryIntent: {intent.model_dump()}")
        return intent

    @classmethod
    def extract_source(cls, query: str) -> Optional[str]:
        q_lower = f" {query.lower()} "
        for src in ["sebi", "rbi", "irdai", "nse", "bse", "moneycontrol"]:
            if f" {src} " in q_lower or f"/{src}/" in q_lower:
                for supported in SUPPORTED_SOURCES:
                    if supported.lower() == src:
                        return supported
        return None

    @classmethod
    def extract_category(cls, query: str) -> Optional[str]:
        q_lower = f" {query.lower()} "
        for cat, keywords in SUPPORTED_CATEGORIES.items():
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", q_lower):
                    return cat
        return None

    @classmethod
    def extract_document_type(cls, query: str) -> Optional[str]:
        q_lower = query.lower()
        for doc_type, keywords in SUPPORTED_DOCUMENT_TYPES.items():
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", q_lower):
                    return doc_type
        return None


def build_metadata_filters(intent: QueryIntent) -> Dict[str, Any]:
    """
    Constructs safe MongoDB Vector Search metadata filter dictionary from QueryIntent.
    Only includes confidently extracted filters to avoid over-constraining results.
    """
    filter_dict = {}
    if intent.source:
        filter_dict["source"] = intent.source
    if intent.category:
        filter_dict["category"] = intent.category
    if intent.document_type:
        filter_dict["document_type"] = intent.document_type
    return filter_dict


def analyze_query(query: str) -> QueryIntent:
    return QueryAnalyzer.analyze(query)
