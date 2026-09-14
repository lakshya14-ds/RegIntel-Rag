"""
Section-Level Regulatory Diff Engine (Phase 60).

Builds a structure-aware document-diff engine tailored to regulatory instruments:
- Preserves section hierarchy: Chapter > Section > Subsection > Paragraph
- 5-Tier section matching with detection of MOVED / reordered clauses
- Paragraph-level and sentence-level diffing
- Deterministic detection of numerical, date, currency, and threshold changes (e.g. 30 days → 15 days, 5% → 10%)
- Detection of regulatory deontic keyword shifts (shall, must, prohibited, required, etc.)
- Table-aware comparison with fallback to TABLE_COMPARISON_UNAVAILABLE
- Page reference tracking (old_page, new_page)
- Thread-safe diff result caching
"""

import re
import difflib
import hashlib
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple, Literal, Set
from pydantic import BaseModel, Field

from app.change_detection.normalizer import (
    normalize_regulatory_text,
    normalize_heading,
    extract_section_number,
    are_texts_substantively_equal
)

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

DIFF_ENGINE_VERSION = "1.0.0"

REGULATORY_KEYWORDS = [
    "shall", "shall not", "must", "must not", "may", "may not",
    "prohibited", "required", "eligible", "ineligible",
    "within", "before", "after", "minimum", "maximum",
    "only", "except", "mandatory", "exempt"
]


# =========================================================================
# DATA MODELS (60.1, 60.15)
# =========================================================================

class RegulatorySection(BaseModel):
    """Represents an extracted regulatory section with hierarchy and pagination."""
    section_id: str
    section_number: Optional[str] = None
    heading: str
    content: str
    normalized_content: str = ""
    order: int = 0
    parent_section: Optional[str] = None
    level: int = 1  # 1 = Chapter, 2 = Section, 3 = Subsection
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    document_id: str = ""


class NumericalChangeItem(BaseModel):
    """Detected numeric, threshold, date, duration, or currency change."""
    parameter: str
    previous_value: str
    new_value: str
    context: Optional[str] = None
    change_type: str = "NUMERICAL_CHANGE"


class KeywordChangeItem(BaseModel):
    """Shift in deontic regulatory keywords."""
    keyword: str
    change_type: Literal["ADDED", "REMOVED", "MODIFIED"]
    context: Optional[str] = None


class ParagraphDiff(BaseModel):
    """Paragraph-level granular delta inside a modified section."""
    paragraph_index: int
    change_type: Literal["ADDED", "REMOVED", "MODIFIED", "UNCHANGED"]
    previous_text: Optional[str] = None
    current_text: Optional[str] = None
    numerical_changes: List[NumericalChangeItem] = Field(default_factory=list)


class TableDiffResult(BaseModel):
    """Result of comparing structured tabular data."""
    status: Literal["TABLES_COMPARED", "TABLE_COMPARISON_UNAVAILABLE"]
    rows_added: int = 0
    rows_removed: int = 0
    cells_modified: int = 0
    details: List[str] = Field(default_factory=list)


class SectionDiff(BaseModel):
    """Complete structured diff result for a single regulatory section."""
    section_number: Optional[str] = None
    heading: str
    change_type: Literal["ADDED", "REMOVED", "MODIFIED", "UNCHANGED", "MOVED"]
    is_moved: bool = False
    old_section_number: Optional[str] = None
    old_section_id: Optional[str] = None
    new_section_id: Optional[str] = None
    old_page: Optional[int] = None
    new_page: Optional[int] = None
    substantive_change: bool = False
    previous_text: Optional[str] = None
    current_text: Optional[str] = None
    paragraph_changes: List[ParagraphDiff] = Field(default_factory=list)
    numerical_changes: List[NumericalChangeItem] = Field(default_factory=list)
    keyword_changes: List[KeywordChangeItem] = Field(default_factory=list)
    table_diff: Optional[TableDiffResult] = None
    evidence: List[str] = Field(default_factory=list)


class DiffReport(BaseModel):
    """Full section-level regulatory diff report."""
    diff_engine_version: str = DIFF_ENGINE_VERSION
    status: str = "SUCCESS"
    message: Optional[str] = None
    older_document_id: str
    newer_document_id: str
    statistics: Dict[str, int] = Field(default_factory=dict)
    sections: List[SectionDiff] = Field(default_factory=list)
    cached: bool = False


# =========================================================================
# THREAD-SAFE DIFF CACHE (60.20)
# =========================================================================

class SectionDiffCache:
    """Thread-safe memory cache for section diff reports."""

    def __init__(self, max_size: int = 150):
        self._cache: Dict[str, DiffReport] = {}
        self._lock = threading.Lock()
        self._max_size = max_size

    def make_key(self, hash_old: str, hash_new: str) -> str:
        raw = f"{hash_old}:{hash_new}:{DIFF_ENGINE_VERSION}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[DiffReport]:
        with self._lock:
            val = self._cache.get(key)
            if val is not None:
                copied = val.model_copy(deep=True)
                copied.cached = True
                return copied
            return None

    def set(self, key: str, report: DiffReport) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            self._cache[key] = report.model_copy(deep=True)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


_global_diff_cache = SectionDiffCache()


def clear_section_diff_cache() -> None:
    _global_diff_cache.clear()


# =========================================================================
# SECTION EXTRACTION WITH HIERARCHY (60.2, 60.14)
# =========================================================================

def extract_page_number(text: str) -> Optional[int]:
    """Attempts to extract page number references e.g. [Page 7] or Page 7 of 24."""
    m = re.search(r"\b(?:page|pg\.?)\s*(\d+)\b", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def extract_hierarchical_sections(text: str, document_id: str = "doc") -> List[RegulatorySection]:
    """
    Parses document into structured sections preserving hierarchy (Chapter > Section > Subsection).
    """
    if not text or not text.strip():
        return []

    lines = text.strip().split("\n")
    sections: List[RegulatorySection] = []

    current_chapter: Optional[str] = None
    current_num: Optional[str] = None
    current_heading = "General Provisions"
    current_content: List[str] = []
    current_level = 2
    sec_idx = 0
    current_page_start: Optional[int] = None

    for line in lines:
        line_str = line.strip()

        # Check for page markers
        p_num = extract_page_number(line_str)
        if p_num and current_page_start is None:
            current_page_start = p_num

        # Check for Chapter heading
        chap_match = re.match(r"^(?:#+\s*)?(?:Chapter|CHAPTER)\s+([IVXLCDM\d]+)[:\-\s]*(.*)$", line_str, re.IGNORECASE)
        if chap_match:
            current_chapter = f"Chapter {chap_match.group(1)}: {chap_match.group(2).strip()}" if chap_match.group(2) else f"Chapter {chap_match.group(1)}"
            continue


        # Check for Section heading
        is_header = False
        num_found: Optional[str] = None
        title_found = ""
        level = 2

        if line_str.startswith("#"):
            is_header = True
            h_level = len(line_str) - len(line_str.lstrip("#"))
            level = min(h_level, 3)
            num_found, title_found = extract_section_number(line_str)
        elif line_str.startswith("Section ") or line_str.startswith("Clause ") or line_str.startswith("Regulation "):
            is_header = True
            level = 2
            num_found, title_found = extract_section_number(line_str)
        elif line_str and line_str[0].isdigit() and ("." in line_str[:6]) and len(line_str) < 140:
            parts = line_str.split(" ", 1)
            if len(parts) > 1 and parts[0].rstrip(".").replace(".", "").isdigit():
                is_header = True
                level = 2 if parts[0].count(".") <= 1 else 3
                num_found, title_found = extract_section_number(line_str)

        if is_header:
            if current_content:
                sec_idx += 1
                raw_c = "\n".join(current_content).strip()
                sections.append(RegulatorySection(
                    section_id=f"{document_id}_sec_{sec_idx:03d}",
                    section_number=current_num,
                    heading=current_heading,
                    content=raw_c,
                    normalized_content=normalize_regulatory_text(raw_c),
                    order=sec_idx,
                    parent_section=current_chapter,
                    level=current_level,
                    page_start=current_page_start,
                    page_end=extract_page_number(raw_c[-300:]) or current_page_start,
                    document_id=document_id
                ))
                current_content = []
                current_page_start = None

            current_num = num_found if num_found else None
            current_heading = title_found if title_found else (line_str.lstrip("#").strip() or "General Provisions")
            current_level = level
        else:
            if line_str:
                current_content.append(line)

    # Flush final section
    if current_content:
        sec_idx += 1
        raw_c = "\n".join(current_content).strip()
        sections.append(RegulatorySection(
            section_id=f"{document_id}_sec_{sec_idx:03d}",
            section_number=current_num,
            heading=current_heading,
            content=raw_c,
            normalized_content=normalize_regulatory_text(raw_c),
            order=sec_idx,
            parent_section=current_chapter,
            level=current_level,
            page_start=current_page_start,
            page_end=extract_page_number(raw_c[-300:]) or current_page_start,
            document_id=document_id
        ))

    # Fallback if no explicit headers found
    if not sections and text.strip():
        raw_c = text.strip()
        sections.append(RegulatorySection(
            section_id=f"{document_id}_sec_001",
            section_number=None,
            heading="General Provisions",
            content=raw_c,
            normalized_content=normalize_regulatory_text(raw_c),
            order=1,
            level=2,
            document_id=document_id
        ))

    return sections


# =========================================================================
# 5-TIER SECTION MATCHING WITH REORDERED / MOVED CLAUSES (60.3, 60.4)
# =========================================================================

def match_sections_hierarchical(
    older_sections: List[RegulatorySection],
    newer_sections: List[RegulatorySection]
) -> List[Tuple[Optional[RegulatorySection], Optional[RegulatorySection], str, bool]]:
    """
    Matches sections across revisions using 5-tier matching and detects MOVED sections.
    Returns list of tuples: (older_section, newer_section, matching_tier, is_moved)
    """
    pairs: List[Tuple[Optional[RegulatorySection], Optional[RegulatorySection], str, bool]] = []
    matched_old_ids: Set[str] = set()
    matched_new_ids: Set[str] = set()

    # Tier 1: Match by exact Section Number (e.g. "4.2" == "4.2")
    old_by_num = {s.section_number: s for s in older_sections if s.section_number}
    new_by_num = {s.section_number: s for s in newer_sections if s.section_number}

    for num, new_s in new_by_num.items():
        if num in old_by_num:
            old_s = old_by_num[num]
            pairs.append((old_s, new_s, "section_number", False))
            matched_old_ids.add(old_s.section_id)
            matched_new_ids.add(new_s.section_id)

    # Tier 2: Match remaining by Exact Normalized Heading
    unmatched_new = [s for s in newer_sections if s.section_id not in matched_new_ids]
    unmatched_old = [s for s in older_sections if s.section_id not in matched_old_ids]

    old_by_norm = {normalize_heading(s.heading): s for s in unmatched_old if normalize_heading(s.heading)}

    for new_s in list(unmatched_new):
        nh = normalize_heading(new_s.heading)
        if nh and nh in old_by_norm:
            old_s = old_by_norm[nh]
            # Check if section number changed -> MOVED (60.4)
            is_moved = bool(old_s.section_number and new_s.section_number and old_s.section_number != new_s.section_number)
            pairs.append((old_s, new_s, "exact_heading", is_moved))
            matched_old_ids.add(old_s.section_id)
            matched_new_ids.add(new_s.section_id)
            unmatched_new.remove(new_s)
            del old_by_norm[nh]

    # Tier 3: Match remaining by Normalized Heading Similarity (Fuzzy > 0.70)
    unmatched_old = [s for s in older_sections if s.section_id not in matched_old_ids]
    for new_s in list(unmatched_new):
        norm_new = normalize_heading(new_s.heading)
        if not norm_new:
            continue

        best_match = None
        best_score = 0.0

        for old_s in unmatched_old:
            norm_old = normalize_heading(old_s.heading)
            if not norm_old:
                continue
            ratio = difflib.SequenceMatcher(None, norm_new, norm_old).ratio()
            if ratio > best_score and ratio >= 0.70:
                best_score = ratio
                best_match = old_s

        if best_match:
            is_moved = bool(best_match.section_number and new_s.section_number and best_match.section_number != new_s.section_number)
            pairs.append((best_match, new_s, "heading_similarity", is_moved))
            matched_old_ids.add(best_match.section_id)
            matched_new_ids.add(new_s.section_id)
            unmatched_new.remove(new_s)
            unmatched_old.remove(best_match)

    # Tier 4: Detect MOVED sections by high content similarity (> 0.65)
    unmatched_old = [s for s in older_sections if s.section_id not in matched_old_ids]
    for new_s in list(unmatched_new):
        toks_new = set(new_s.normalized_content.split())
        if not toks_new:
            continue

        best_match = None
        best_jaccard = 0.0

        for old_s in unmatched_old:
            toks_old = set(old_s.normalized_content.split())
            if not toks_old:
                continue
            inter = len(toks_new.intersection(toks_old))
            union = len(toks_new.union(toks_old))
            jacc = inter / union if union else 0.0
            if jacc > best_jaccard and jacc >= 0.65:
                best_jaccard = jacc
                best_match = old_s

        if best_match:
            pairs.append((best_match, new_s, "content_similarity", True))
            matched_old_ids.add(best_match.section_id)
            matched_new_ids.add(new_s.section_id)
            unmatched_new.remove(new_s)
            unmatched_old.remove(best_match)

    # Unmatched in Newer Document -> ADDED (60.5)
    for new_s in newer_sections:
        if new_s.section_id not in matched_new_ids:
            pairs.append((None, new_s, "unmatched_new", False))

    # Unmatched in Older Document -> REMOVED (60.6)
    for old_s in older_sections:
        if old_s.section_id not in matched_old_ids:
            pairs.append((old_s, None, "unmatched_old", False))

    return pairs


# =========================================================================
# NUMERICAL AND DATE CHANGE DETECTION (60.11)
# =========================================================================

NUMERIC_PATTERNS = [
    # Deadlines / Durations: e.g. "30 days", "15 days", "8 years", "6 months"
    (r"\b(\d+)\s*(days?|months?|years?|weeks?|hours?)\b", "duration"),
    # Percentages: e.g. "5%", "10%", "2.5%"
    (r"\b(\d+(?:\.\d+)?)\s*%", "percentage"),
    # Currency / Thresholds: e.g. "INR 50 Lakhs", "Rs. 25 Lakhs", "₹ 1 Crore", "INR 10,000"
    (r"\b(?:INR|Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(Lakhs?|Crores?|thousand)?\b", "currency"),
    # ISO Dates: YYYY-MM-DD
    (r"\b(\d{4}-\d{2}-\d{2})\b", "date"),
    # Textual Dates: e.g. "01 April 2024", "15 May, 2024"
    (r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4})\b", "date"),
]


def extract_numerical_tokens(text: str) -> List[Tuple[str, str, str]]:
    """Extracts (full_match, value, param_type) from text."""
    if not text:
        return []
    tokens = []
    for pat, ptype in NUMERIC_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            tokens.append((m.group(0).strip(), m.group(1).strip() if m.groups() else m.group(0), ptype))
    return tokens


def detect_numerical_changes(old_text: str, new_text: str) -> List[NumericalChangeItem]:
    """
    Detects numerical, threshold, date, and duration shifts between old and new texts (60.11).
    Example: 30 days → 15 days, 5% → 10%, INR 25 Lakhs → INR 50 Lakhs.
    """
    old_tokens = extract_numerical_tokens(old_text)
    new_tokens = extract_numerical_tokens(new_text)

    changes: List[NumericalChangeItem] = []
    seen_changes = set()

    for old_full, old_val, ptype in old_tokens:
        for new_full, new_val, ntype in new_tokens:
            if ptype == ntype and old_full.lower() != new_full.lower():
                # Pair matches if same unit or both percentage/currency/duration
                key = (old_full.lower(), new_full.lower())
                if key not in seen_changes:
                    seen_changes.add(key)
                    changes.append(NumericalChangeItem(
                        parameter=ptype.title(),
                        previous_value=old_full,
                        new_value=new_full,
                        context=f"{old_full} → {new_full}",
                        change_type="NUMERICAL_CHANGE"
                    ))
    return changes


# =========================================================================
# REGULATORY KEYWORD CHANGE DETECTION (60.12)
# =========================================================================

def detect_keyword_changes(old_text: str, new_text: str) -> List[KeywordChangeItem]:
    """
    Flags additions or omissions of deontic regulatory keywords (shall, must, prohibited, etc.).
    """
    old_words = set(re.findall(r"\b[a-z\s]+\b", old_text.lower()))
    new_words = set(re.findall(r"\b[a-z\s]+\b", new_text.lower()))

    changes: List[KeywordChangeItem] = []

    for kw in REGULATORY_KEYWORDS:
        in_old = bool(re.search(rf"\b{re.escape(kw)}\b", old_text, re.IGNORECASE))
        in_new = bool(re.search(rf"\b{re.escape(kw)}\b", new_text, re.IGNORECASE))

        if in_new and not in_old:
            changes.append(KeywordChangeItem(
                keyword=kw,
                change_type="ADDED",
                context=f"Mandatory/regulatory term '{kw}' introduced."
            ))
        elif in_old and not in_new:
            changes.append(KeywordChangeItem(
                keyword=kw,
                change_type="REMOVED",
                context=f"Mandatory/regulatory term '{kw}' removed."
            ))
    return changes


# =========================================================================
# PARAGRAPH-LEVEL DIFF (60.9)
# =========================================================================

def diff_paragraphs(old_content: str, new_content: str) -> List[ParagraphDiff]:
    """Splits modified section into paragraphs and computes paragraph deltas."""
    old_paras = [p.strip() for p in old_content.split("\n\n") if p.strip()]
    new_paras = [p.strip() for p in new_content.split("\n\n") if p.strip()]

    if not old_paras and not new_paras:
        return []

    matcher = difflib.SequenceMatcher(None, old_paras, new_paras)
    para_diffs: List[ParagraphDiff] = []
    idx = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(j1, j2):
                idx += 1
                para_diffs.append(ParagraphDiff(
                    paragraph_index=idx,
                    change_type="UNCHANGED",
                    previous_text=new_paras[k],
                    current_text=new_paras[k]
                ))
        elif tag == "insert":
            for k in range(j1, j2):
                idx += 1
                para_diffs.append(ParagraphDiff(
                    paragraph_index=idx,
                    change_type="ADDED",
                    previous_text=None,
                    current_text=new_paras[k]
                ))
        elif tag == "delete":
            for k in range(i1, i2):
                idx += 1
                para_diffs.append(ParagraphDiff(
                    paragraph_index=idx,
                    change_type="REMOVED",
                    previous_text=old_paras[k],
                    current_text=None
                ))
        elif tag == "replace":
            # Compare paired paragraphs
            len_old = i2 - i1
            len_new = j2 - j1
            for offset in range(max(len_old, len_new)):
                idx += 1
                old_p = old_paras[i1 + offset] if offset < len_old else None
                new_p = new_paras[j1 + offset] if offset < len_new else None

                if old_p and new_p:
                    num_changes = detect_numerical_changes(old_p, new_p)
                    para_diffs.append(ParagraphDiff(
                        paragraph_index=idx,
                        change_type="MODIFIED",
                        previous_text=old_p,
                        current_text=new_p,
                        numerical_changes=num_changes
                    ))
                elif new_p:
                    para_diffs.append(ParagraphDiff(
                        paragraph_index=idx,
                        change_type="ADDED",
                        previous_text=None,
                        current_text=new_p
                    ))
                elif old_p:
                    para_diffs.append(ParagraphDiff(
                        paragraph_index=idx,
                        change_type="REMOVED",
                        previous_text=old_p,
                        current_text=None
                    ))
    return para_diffs


# =========================================================================
# TABLE-AWARE COMPARISON (60.13)
# =========================================================================

def compare_tables(old_text: str, new_text: str) -> TableDiffResult:
    """
    Compares markdown tables if present.
    If table structure is absent, returns TABLE_COMPARISON_UNAVAILABLE.
    """
    old_has_table = "|" in old_text and "-|-" in old_text
    new_has_table = "|" in new_text and "-|-" in new_text

    if not old_has_table and not new_has_table:
        return TableDiffResult(status="TABLE_COMPARISON_UNAVAILABLE")

    old_rows = [line.strip() for line in old_text.split("\n") if line.strip().startswith("|") and not line.strip().startswith("|-")]
    new_rows = [line.strip() for line in new_text.split("\n") if line.strip().startswith("|") and not line.strip().startswith("|-")]

    added_r = max(0, len(new_rows) - len(old_rows))
    removed_r = max(0, len(old_rows) - len(new_rows))
    cells_mod = 0
    details = []

    for idx, (orow, nrow) in enumerate(zip(old_rows, new_rows), start=1):
        if orow != nrow:
            cells_mod += 1
            details.append(f"Row {idx} amended: '{orow}' → '{nrow}'")

    return TableDiffResult(
        status="TABLES_COMPARED",
        rows_added=added_r,
        rows_removed=removed_r,
        cells_modified=cells_mod,
        details=details[:5]
    )


# =========================================================================
# SECTION-LEVEL DIFF SERVICE (60.16, 60.18)
# =========================================================================

class RegulatoryDiffEngine:
    """
    Document-diff engine understanding regulatory document structure (Phase 60).
    """

    def __init__(self, cache: Optional[SectionDiffCache] = None):
        self.cache = cache or _global_diff_cache

    def diff_documents(
        self,
        older_doc_id: str,
        older_content: str,
        newer_doc_id: str,
        newer_content: str,
        hash_old: Optional[str] = None,
        hash_new: Optional[str] = None
    ) -> DiffReport:
        """
        Executes section-level regulatory diff between two documents.
        """
        # Cache check (60.20)
        h_old = hash_old or hashlib.sha256((older_content or "").encode("utf-8")).hexdigest()
        h_new = hash_new or hashlib.sha256((newer_content or "").encode("utf-8")).hexdigest()
        cache_key = self.cache.make_key(h_old, h_new)

        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Section Extraction (60.2)
        older_sections = extract_hierarchical_sections(older_content, document_id=older_doc_id)
        newer_sections = extract_hierarchical_sections(newer_content, document_id=newer_doc_id)

        # Comparison Safety check (60.19)
        safety_message = None
        if not older_sections or not newer_sections:
            safety_message = "Section-level comparison confidence is limited because structural information was incomplete."

        # Section Alignment (60.3, 60.4)
        aligned_pairs = match_sections_hierarchical(older_sections, newer_sections)

        diffs: List[SectionDiff] = []
        counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0, "moved": 0}

        for old_s, new_s, method, is_moved in aligned_pairs:
            # Case 1: ADDED
            if old_s is None and new_s is not None:
                counts["added"] += 1
                diffs.append(SectionDiff(
                    section_number=new_s.section_number or str(new_s.order),
                    heading=new_s.heading,
                    change_type="ADDED",
                    is_moved=False,
                    new_section_id=new_s.section_id,
                    new_page=new_s.page_start,
                    substantive_change=True,
                    current_text=new_s.content,
                    evidence=[new_s.content[:200]]
                ))

            # Case 2: REMOVED
            elif old_s is not None and new_s is None:
                counts["removed"] += 1
                diffs.append(SectionDiff(
                    section_number=old_s.section_number or str(old_s.order),
                    heading=old_s.heading,
                    change_type="REMOVED",
                    is_moved=False,
                    old_section_id=old_s.section_id,
                    old_page=old_s.page_start,
                    substantive_change=True,
                    previous_text=old_s.content,
                    evidence=[old_s.content[:200]]
                ))

            # Case 3: Matched Pair
            elif old_s is not None and new_s is not None:
                is_equal = are_texts_substantively_equal(old_s.content, new_s.content)

                if is_moved and is_equal:
                    # Section moved but content identical (60.4)
                    counts["moved"] += 1
                    diffs.append(SectionDiff(
                        section_number=new_s.section_number or str(new_s.order),
                        heading=new_s.heading,
                        change_type="MOVED",
                        is_moved=True,
                        old_section_number=old_s.section_number,
                        old_section_id=old_s.section_id,
                        new_section_id=new_s.section_id,
                        old_page=old_s.page_start,
                        new_page=new_s.page_start,
                        substantive_change=False,
                        previous_text=old_s.content,
                        current_text=new_s.content,
                        evidence=[f"Clause reordered from {old_s.section_number} to {new_s.section_number}"]
                    ))

                elif is_equal:
                    # Unchanged (60.8)
                    counts["unchanged"] += 1
                    diffs.append(SectionDiff(
                        section_number=new_s.section_number or old_s.section_number or str(new_s.order),
                        heading=new_s.heading,
                        change_type="UNCHANGED",
                        is_moved=False,
                        old_section_id=old_s.section_id,
                        new_section_id=new_s.section_id,
                        old_page=old_s.page_start,
                        new_page=new_s.page_start,
                        substantive_change=False,
                        previous_text=old_s.content,
                        current_text=new_s.content
                    ))

                else:
                    # Modified (60.7, 60.9, 60.11, 60.12, 60.13)
                    counts["modified"] += 1
                    p_diffs = diff_paragraphs(old_s.content, new_s.content)
                    num_diffs = detect_numerical_changes(old_s.content, new_s.content)
                    kw_diffs = detect_keyword_changes(old_s.content, new_s.content)
                    tbl_diff = compare_tables(old_s.content, new_s.content)

                    diffs.append(SectionDiff(
                        section_number=new_s.section_number or old_s.section_number or str(new_s.order),
                        heading=new_s.heading,
                        change_type="MODIFIED",
                        is_moved=is_moved,
                        old_section_number=old_s.section_number if is_moved else None,
                        old_section_id=old_s.section_id,
                        new_section_id=new_s.section_id,
                        old_page=old_s.page_start,
                        new_page=new_s.page_start,
                        substantive_change=True,
                        previous_text=old_s.content,
                        current_text=new_s.content,
                        paragraph_changes=p_diffs,
                        numerical_changes=num_diffs,
                        keyword_changes=kw_diffs,
                        table_diff=tbl_diff,
                        evidence=[new_s.content[:200]]
                    ))

        report = DiffReport(
            diff_engine_version=DIFF_ENGINE_VERSION,
            status="SUCCESS",
            message=safety_message,
            older_document_id=older_doc_id,
            newer_document_id=newer_doc_id,
            statistics=counts,
            sections=diffs,
            cached=False
        )

        self.cache.set(cache_key, report)
        return report


# Global instance
_diff_engine = RegulatoryDiffEngine()


def get_diff_engine() -> RegulatoryDiffEngine:
    return _diff_engine
