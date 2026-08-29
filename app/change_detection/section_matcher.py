"""
4-Tier Structural Section Matching Module.

Aligns corresponding regulatory sections across document versions using a deterministic
hierarchy of evidence:
1. Exact Section Number (e.g. "4.2" == "4.2") -> High Confidence
2. Exact Normalized Heading (e.g. "client agreements") -> High Confidence
3. Normalized Heading Similarity (Fuzzy / Sequence Matcher > 0.70) -> Medium Confidence
4. Content / Keyword Overlap Fallback -> Low Confidence

Unmatched sections in newer document are classified as ADDED.
Unmatched sections in older document are classified as REMOVED.
"""

import difflib
import logging
from typing import List, Dict, Any, Optional, Set, Tuple, Literal
from pydantic import BaseModel, Field

from app.change_detection.normalizer import normalize_heading, extract_section_number, normalize_regulatory_text

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class ExtractedSection(BaseModel):
    """Represents a logical section extracted from a regulatory document."""
    section_id: str
    section_number: Optional[str] = None
    heading: str
    content: str
    normalized_content: str = ""
    order: int = 0
    document_id: str = ""


class MatchedSectionPair(BaseModel):
    """Represents an aligned pair of sections across older and newer document versions."""
    section_key: str
    section_title: str
    older_section: Optional[ExtractedSection] = None
    newer_section: Optional[ExtractedSection] = None
    matching_method: Literal["section_number", "exact_heading", "heading_similarity", "content_similarity", "unmatched_new", "unmatched_old"]
    matching_confidence: Literal["high", "medium", "low", "none"]


class SectionMatcher:
    """
    Parses documents into logical sections and matches them using 4-tier structural alignment.
    """

    @classmethod
    def extract_sections(cls, text: str, document_id: str = "doc") -> List[ExtractedSection]:
        """
        Splits markdown or structured circular text into logical sections based on headings.
        """
        if not text or not text.strip():
            return []

        lines = text.strip().split("\n")
        sections: List[ExtractedSection] = []

        current_num: Optional[str] = None
        current_heading = "General Provisions"
        current_content_lines: List[str] = []
        sec_idx = 0

        for line in lines:
            line_str = line.strip()
            # Detect header line: starts with # or numbered clause like "1. Title" or "1.2 Title"
            is_header = False
            if line_str.startswith("#"):
                is_header = True
            elif line_str.startswith("Section ") or line_str.startswith("Clause ") or line_str.startswith("Regulation "):
                is_header = True
            elif line_str and line_str[0].isdigit() and ("." in line_str[:5]) and len(line_str) < 120:
                # e.g. "1. Net Worth Requirements" or "4.2 Client Agreements"
                parts = line_str.split(" ", 1)
                if len(parts) > 1 and parts[0].rstrip(".").replace(".", "").isdigit():
                    is_header = True

            if is_header:
                # Flush existing section
                if current_content_lines:
                    sec_idx += 1
                    raw_content = "\n".join(current_content_lines).strip()
                    norm_content = normalize_regulatory_text(raw_content)
                    sections.append(ExtractedSection(
                        section_id=f"{document_id}_sec_{sec_idx:03d}",
                        section_number=current_num,
                        heading=current_heading,
                        content=raw_content,
                        normalized_content=norm_content,
                        order=sec_idx,
                        document_id=document_id
                    ))
                    current_content_lines = []

                num_extracted, title_extracted = extract_section_number(line_str)
                current_num = num_extracted if num_extracted else None
                current_heading = title_extracted if title_extracted else "General Provisions"
            else:
                if line_str:
                    current_content_lines.append(line)

        # Flush final section
        if current_content_lines:
            sec_idx += 1
            raw_content = "\n".join(current_content_lines).strip()
            norm_content = normalize_regulatory_text(raw_content)
            sections.append(ExtractedSection(
                section_id=f"{document_id}_sec_{sec_idx:03d}",
                section_number=current_num,
                heading=current_heading,
                content=raw_content,
                normalized_content=norm_content,
                order=sec_idx,
                document_id=document_id
            ))

        # Fallback if text contained no explicit headers
        if not sections and text.strip():
            raw_content = text.strip()
            sections.append(ExtractedSection(
                section_id=f"{document_id}_sec_001",
                section_number=None,
                heading="General Provisions",
                content=raw_content,
                normalized_content=normalize_regulatory_text(raw_content),
                order=1,
                document_id=document_id
            ))

        return sections

    @classmethod
    def match_sections(
        cls,
        older_sections: List[ExtractedSection],
        newer_sections: List[ExtractedSection]
    ) -> List[MatchedSectionPair]:
        """
        Executes 4-tier structural matching between older and newer document sections.
        """
        matched_pairs: List[MatchedSectionPair] = []
        matched_old_ids: Set[str] = set()
        matched_new_ids: Set[str] = set()

        # Tier 1: Match by exact Section Number (e.g. "4.2" == "4.2")
        old_by_num: Dict[str, ExtractedSection] = {s.section_number: s for s in older_sections if s.section_number}
        new_by_num: Dict[str, ExtractedSection] = {s.section_number: s for s in newer_sections if s.section_number}

        for num, new_s in new_by_num.items():
            if num in old_by_num:
                old_s = old_by_num[num]
                matched_pairs.append(MatchedSectionPair(
                    section_key=f"sec_{num}",
                    section_title=f"{num}. {new_s.heading}",
                    older_section=old_s,
                    newer_section=new_s,
                    matching_method="section_number",
                    matching_confidence="high"
                ))
                matched_old_ids.add(old_s.section_id)
                matched_new_ids.add(new_s.section_id)

        # Tier 2: Match remaining by Exact Normalized Heading
        unmatched_new = [s for s in newer_sections if s.section_id not in matched_new_ids]
        unmatched_old = [s for s in older_sections if s.section_id not in matched_old_ids]

        old_by_norm: Dict[str, ExtractedSection] = {normalize_heading(s.heading): s for s in unmatched_old if normalize_heading(s.heading)}

        for new_s in list(unmatched_new):
            norm_h = normalize_heading(new_s.heading)
            if norm_h and norm_h in old_by_norm:
                old_s = old_by_norm[norm_h]
                matched_pairs.append(MatchedSectionPair(
                    section_key=norm_h,
                    section_title=new_s.heading,
                    older_section=old_s,
                    newer_section=new_s,
                    matching_method="exact_heading",
                    matching_confidence="high"
                ))
                matched_old_ids.add(old_s.section_id)
                matched_new_ids.add(new_s.section_id)
                unmatched_new.remove(new_s)
                del old_by_norm[norm_h]

        # Tier 3: Match remaining by Normalized Heading Similarity (Fuzzy > 0.70)
        unmatched_old = [s for s in older_sections if s.section_id not in matched_old_ids]
        for new_s in list(unmatched_new):
            norm_new = normalize_heading(new_s.heading)
            if not norm_new:
                continue

            best_match: Optional[ExtractedSection] = None
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
                matched_pairs.append(MatchedSectionPair(
                    section_key=f"fuzzy_{normalize_heading(new_s.heading)}",
                    section_title=new_s.heading,
                    older_section=best_match,
                    newer_section=new_s,
                    matching_method="heading_similarity",
                    matching_confidence="medium"
                ))
                matched_old_ids.add(best_match.section_id)
                matched_new_ids.add(new_s.section_id)
                unmatched_new.remove(new_s)
                unmatched_old.remove(best_match)

        # Tier 4: Content Keyword Jaccard Overlap Fallback (> 0.45)
        for new_s in list(unmatched_new):
            tokens_new = set(normalize_heading(new_s.content).split())
            if not tokens_new:
                continue

            best_match = None
            best_jaccard = 0.0

            for old_s in unmatched_old:
                tokens_old = set(normalize_heading(old_s.content).split())
                if not tokens_old:
                    continue
                intersection = tokens_new.intersection(tokens_old)
                union = tokens_new.union(tokens_old)
                jaccard = len(intersection) / len(union) if union else 0.0
                if jaccard > best_jaccard and jaccard >= 0.45:
                    best_jaccard = jaccard
                    best_match = old_s

            if best_match:
                matched_pairs.append(MatchedSectionPair(
                    section_key=f"content_{new_s.section_id}",
                    section_title=new_s.heading,
                    older_section=best_match,
                    newer_section=new_s,
                    matching_method="content_similarity",
                    matching_confidence="low"
                ))
                matched_old_ids.add(best_match.section_id)
                matched_new_ids.add(new_s.section_id)
                unmatched_new.remove(new_s)
                unmatched_old.remove(best_match)

        # Unmatched in Newer Document -> ADDED
        for new_s in newer_sections:
            if new_s.section_id not in matched_new_ids:
                matched_pairs.append(MatchedSectionPair(
                    section_key=new_s.section_id,
                    section_title=new_s.heading,
                    older_section=None,
                    newer_section=new_s,
                    matching_method="unmatched_new",
                    matching_confidence="none"
                ))

        # Unmatched in Older Document -> REMOVED
        for old_s in older_sections:
            if old_s.section_id not in matched_old_ids:
                matched_pairs.append(MatchedSectionPair(
                    section_key=old_s.section_id,
                    section_title=old_s.heading,
                    older_section=old_s,
                    newer_section=None,
                    matching_method="unmatched_old",
                    matching_confidence="none"
                ))

        # Sort pairs logically: matched sections by order, then added, then removed
        return matched_pairs
