"""
Section Extraction, Alignment, and Difference Classification Module.

Parses regulatory documents into structured sections, aligns corresponding clauses across versions,
and classifies changes into ADDED, REMOVED, MODIFIED, and UNCHANGED with domain subcategories.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Literal
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

MODIFICATION_CATEGORIES = [
    "eligibility",
    "reporting",
    "disclosure",
    "compliance",
    "documentation",
    "timelines",
    "fees",
    "penalties",
    "applicability",
    "procedural requirement",
    "other"
]

CATEGORY_KEYWORDS = {
    "eligibility": ["eligibility", "qualification", "certification", "nism", "net worth", "capital requirement", "criteria"],
    "fees": ["fee", "fees", "cap", "charges", "remuneration", "expense ratio", "ter", "billing"],
    "timelines": ["timeline", "deadline", "days", "months", "within", "period", "annual", "quarterly", "submission"],
    "documentation": ["agreement", "records", "books of account", "documentation", "retention", "8 years", "archive"],
    "compliance": ["audit", "compliance officer", "internal control", "supervision", "basl", "inspection"],
    "reporting": ["report", "reporting", "disclosure", "filing", "submission", "portal"],
    "disclosure": ["disclosure", "advertisement", "code of conduct", "transparency", "website"],
    "penalties": ["penalty", "penalties", "adjudication", "disincentive", "enforcement", "fine"],
    "applicability": ["applicability", "scope", "applicable to", "effective date", "entities"]
}


class RegulatorySection(BaseModel):
    """Represents an extracted logical section from a regulatory document."""
    section_id: str
    section_number: Optional[str] = None
    heading: str
    content: str


class AlignedSectionPair(BaseModel):
    """Represents a matched pair of sections across previous and current documents."""
    section_key: str
    section_title: str
    previous_section: Optional[RegulatorySection] = None
    current_section: Optional[RegulatorySection] = None
    alignment_type: Literal["exact", "normalized", "semantic", "added", "removed"]


class SectionChange(BaseModel):
    """Structured delta for a single regulatory section."""
    section: str
    title: str
    change_type: Literal["ADDED", "REMOVED", "MODIFIED", "UNCHANGED"]
    modification_category: Optional[str] = None
    previous_text: Optional[str] = None
    current_text: Optional[str] = None
    summary: Optional[str] = None
    impact: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)


def normalize_heading(heading: str) -> str:
    """Normalizes heading for robust matching across revisions."""
    if not heading:
        return ""
    clean = re.sub(r"^[#\s\d\.\-_]+", "", heading).lower()
    clean = re.sub(r"[^\w\s]", "", clean)
    return re.sub(r"\s+", " ", clean).strip()


class SectionComparer:
    """
    Extracts, aligns, and compares regulatory sections across document revisions.
    """

    @classmethod
    def extract_sections(cls, text: str, document_id: str = "doc") -> List[RegulatorySection]:
        """
        Parses markdown/structured regulatory text into distinct logical sections based on headings.
        """
        if not text or not text.strip():
            return []

        # Split by markdown headers #, ##, ###, #### or numbered clause headers
        lines = text.strip().split("\n")
        sections: List[RegulatorySection] = []
        
        current_num: Optional[str] = None
        current_heading = "General"
        current_content_lines: List[str] = []
        sec_idx = 0

        header_regex = re.compile(r"^(?:#{1,4}\s+|(?:\d+\.|\d+\.\d+)\s+)(.+)$")
        num_prefix_regex = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")

        for line in lines:
            line_str = line.strip()
            # Check if header line
            if line.startswith("#") or re.match(r"^\d+\.\s+[A-Z]", line_str):
                # Save previous section if it had content
                if current_content_lines:
                    sec_idx += 1
                    content_str = "\n".join(current_content_lines).strip()
                    sections.append(RegulatorySection(
                        section_id=f"{document_id}_sec_{sec_idx:03d}",
                        section_number=current_num,
                        heading=current_heading,
                        content=content_str
                    ))
                    current_content_lines = []

                clean_heading = re.sub(r"^#+\s*", "", line_str)
                num_match = num_prefix_regex.match(clean_heading)
                if num_match:
                    current_num = num_match.group(1)
                    current_heading = num_match.group(2).strip()
                else:
                    current_num = None
                    current_heading = clean_heading.strip()
            else:
                if line_str:
                    current_content_lines.append(line)

        # Flush final section
        if current_content_lines:
            sec_idx += 1
            sections.append(RegulatorySection(
                section_id=f"{document_id}_sec_{sec_idx:03d}",
                section_number=current_num,
                heading=current_heading,
                content="\n".join(current_content_lines).strip()
            ))

        # Fallback if no headings found
        if not sections and text.strip():
            sections.append(RegulatorySection(
                section_id=f"{document_id}_sec_001",
                section_number=None,
                heading="General Provisions",
                content=text.strip()
            ))

        return sections

    @classmethod
    def align_sections(
        cls,
        prev_sections: List[RegulatorySection],
        curr_sections: List[RegulatorySection]
    ) -> List[AlignedSectionPair]:
        """
        Aligns sections between Previous and Current document versions.
        """
        aligned_pairs: List[AlignedSectionPair] = []
        matched_prev_ids = set()
        matched_curr_ids = set()

        # Step 1: Match by exact Section Number
        prev_by_num = {s.section_number: s for s in prev_sections if s.section_number}
        curr_by_num = {s.section_number: s for s in curr_sections if s.section_number}

        for num, curr_s in curr_by_num.items():
            if num in prev_by_num:
                prev_s = prev_by_num[num]
                aligned_pairs.append(AlignedSectionPair(
                    section_key=f"sec_{num}",
                    section_title=f"{num}. {curr_s.heading}",
                    previous_section=prev_s,
                    current_section=curr_s,
                    alignment_type="exact"
                ))
                matched_prev_ids.add(prev_s.section_id)
                matched_curr_ids.add(curr_s.section_id)

        # Step 2: Match remaining by Normalized Heading
        unmatched_curr = [s for s in curr_sections if s.section_id not in matched_curr_ids]
        unmatched_prev = [s for s in prev_sections if s.section_id not in matched_prev_ids]

        prev_by_norm = {normalize_heading(s.heading): s for s in unmatched_prev}

        for curr_s in list(unmatched_curr):
            norm_h = normalize_heading(curr_s.heading)
            if norm_h and norm_h in prev_by_norm:
                prev_s = prev_by_norm[norm_h]
                aligned_pairs.append(AlignedSectionPair(
                    section_key=norm_h,
                    section_title=curr_s.heading,
                    previous_section=prev_s,
                    current_section=curr_s,
                    alignment_type="normalized"
                ))
                matched_prev_ids.add(prev_s.section_id)
                matched_curr_ids.add(curr_s.section_id)
                unmatched_curr.remove(curr_s)

        # Step 3: Identify Added Sections (in current but not previous)
        for curr_s in curr_sections:
            if curr_s.section_id not in matched_curr_ids:
                aligned_pairs.append(AlignedSectionPair(
                    section_key=curr_s.section_id,
                    section_title=curr_s.heading,
                    previous_section=None,
                    current_section=curr_s,
                    alignment_type="added"
                ))

        # Step 4: Identify Removed Sections (in previous but not current)
        for prev_s in prev_sections:
            if prev_s.section_id not in matched_prev_ids:
                aligned_pairs.append(AlignedSectionPair(
                    section_key=prev_s.section_id,
                    section_title=prev_s.heading,
                    previous_section=prev_s,
                    current_section=None,
                    alignment_type="removed"
                ))

        return aligned_pairs

    @classmethod
    def classify_change(cls, pair: AlignedSectionPair) -> Tuple[str, Optional[str]]:
        """
        Classifies an aligned pair into ADDED, REMOVED, MODIFIED, or UNCHANGED,
        and determines the modification category.
        """
        if pair.previous_section is None and pair.current_section is not None:
            return "ADDED", cls.infer_modification_category(pair.current_section.content)

        if pair.previous_section is not None and pair.current_section is None:
            return "REMOVED", cls.infer_modification_category(pair.previous_section.content)

        prev_text = pair.previous_section.content.strip()
        curr_text = pair.current_section.content.strip()

        # Check exact text identity
        if prev_text == curr_text:
            return "UNCHANGED", None

        # Check if difference is purely whitespace/punctuation
        norm_prev = re.sub(r"\s+", " ", prev_text).lower()
        norm_curr = re.sub(r"\s+", " ", curr_text).lower()
        if norm_prev == norm_curr:
            return "UNCHANGED", None

        # Substantive modification
        mod_cat = cls.infer_modification_category(f"{curr_text} {pair.section_title}")
        return "MODIFIED", mod_cat

    @staticmethod
    def infer_modification_category(text: str) -> str:
        """Determines regulatory subcategory from text keywords."""
        if not text:
            return "other"
        text_lower = text.lower()
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                    return cat
        return "other"
