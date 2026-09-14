"""
Deterministic Regulatory Candidate Detector (Phase 61.3).

Detects requirement-bearing clauses and statements in regulatory instruments.
Filters non-regulatory noise, background explanations, recitals, and purely narrative preambles.
"""

import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


DEONTIC_PATTERNS = [
    # Mandatory obligations
    (r"\bshall\s+ensure\b", "MANDATORY_ENSURE"),
    (r"\bshall\s+maintain\b", "MANDATORY_MAINTAIN"),
    (r"\bshall\s+submit\b", "MANDATORY_SUBMIT"),
    (r"\bshall\s+disclose\b", "MANDATORY_DISCLOSE"),
    (r"\bshall\s+report\b", "MANDATORY_REPORT"),
    (r"\bshall\s+comply\b", "MANDATORY_COMPLY"),
    (r"\bshall\s+not\b", "PROHIBITION"),
    (r"\bshall\b", "MANDATORY"),
    (r"\bmust\s+not\b", "PROHIBITION"),
    (r"\bmust\b", "MANDATORY"),
    (r"\bis\s+required\s+to\b", "MANDATORY_REQUIRED"),
    (r"\bare\s+required\s+to\b", "MANDATORY_REQUIRED"),
    (r"\brequired\s+to\b", "MANDATORY_REQUIRED"),
    (r"\bprohibited\b", "PROHIBITION"),
    (r"\bmay\s+only\b", "RESTRICTED_PERMISSION"),

    # Temporal constraints & Deadlines
    (r"\bwithin\s+\d+\s*(?:days?|weeks?|months?|hours?)\b", "TEMPORAL_DEADLINE"),
    (r"\bnot\s+later\s+than\b", "TEMPORAL_DEADLINE"),
    (r"\bnot\s+exceeding\b", "THRESHOLD_LIMIT"),
    (r"\bat\s+least\b", "THRESHOLD_MINIMUM"),
    (r"\bnot\s+less\s+than\b", "THRESHOLD_MINIMUM"),
    (r"\bnot\s+more\s+than\b", "THRESHOLD_MAXIMUM"),

    # Conditionals & Exceptions
    (r"\bprovided\s+that\b", "CONDITIONAL_PROVISO"),
    (r"\bsubject\s+to\b", "CONDITIONAL_SUBJECT_TO"),
]

# Patterns that suggest purely informational, background, or recitals
NOISE_PREFIXES = [
    r"^(?:whereas|in\s+exercise\s+of\s+the\s+powers|background|preamble|introduction)\b",
    r"^(?:this\s+circular\s+is\s+issued\s+with\s+the\s+approval\s+of)\b",
    r"^(?:copy\s+to|to\s+all\s+registered)\b",
    r"^(?:the\s+board\s+has\s+decided\s+to)\b"
]


class RequirementCandidate(BaseModel):
    """Candidate requirement identified deterministically by regulatory cues."""
    candidate_text: str
    cleaned_text: str
    trigger_cues: List[str] = Field(default_factory=list)
    cue_categories: List[str] = Field(default_factory=list)
    is_table: bool = False
    section_id: Optional[str] = None
    section_number: Optional[str] = None
    heading: Optional[str] = None
    page_number: Optional[int] = None
    confidence_hint: str = "HIGH"


def is_noise_statement(sentence: str) -> bool:
    """Detects whether a sentence is procedural boilerplate or recital rather than an obligation."""
    s_lower = sentence.strip().lower()
    for pat in NOISE_PREFIXES:
        if re.search(pat, s_lower):
            return True
    return False


def split_into_sentences(text: str) -> List[str]:
    """Splits regulatory paragraphs into candidate sentences while preserving abbreviations."""
    if not text:
        return []
    # Avoid splitting on common regulatory abbreviations e.g., "w.e.f.", "viz.", "i.e.", "e.g.", "reg."
    clean = re.sub(r"\b(w\.e\.f\.|viz\.|i\.e\.|e\.g\.|reg\.|sec\.|no\.)", lambda m: m.group(0).replace(".", "§§"), text)
    # Split on period followed by whitespace or line break
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])|\n{2,}", clean)
    sentences = []
    for s in raw_sentences:
        restored = s.replace("§§", ".").strip()
        if len(restored) > 15:
            sentences.append(restored)
    return sentences


def detect_candidate_requirements_in_text(
    text: str,
    section_id: Optional[str] = None,
    section_number: Optional[str] = None,
    heading: Optional[str] = None,
    page_number: Optional[int] = None
) -> List[RequirementCandidate]:
    """
    Scans regulatory text deterministically and extracts requirement-bearing candidate clauses.
    """
    if not text or not text.strip():
        return []

    candidates: List[RequirementCandidate] = []
    lines = text.split("\n")

    # 1. Detect table rows if formatted as markdown tables
    in_table = False
    table_rows = []
    for line in lines:
        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2 and not all(p.startswith("-") for p in parts):
                in_table = True
                table_rows.append(line)
        elif in_table and table_rows:
            # Process table batch
            table_text = " ".join(table_rows)
            cues = []
            categories = []
            for pat, cat in DEONTIC_PATTERNS:
                m = re.search(pat, table_text, re.IGNORECASE)
                if m:
                    cues.append(m.group(0))
                    categories.append(cat)
            if cues:
                candidates.append(RequirementCandidate(
                    candidate_text=table_text,
                    cleaned_text=" ".join(table_text.split()),
                    trigger_cues=list(set(cues)),
                    cue_categories=list(set(categories)),
                    is_table=True,
                    section_id=section_id,
                    section_number=section_number,
                    heading=heading,
                    page_number=page_number,
                    confidence_hint="MEDIUM"
                ))
            table_rows = []
            in_table = False

    # 2. Detect sentences with requirement-bearing language
    sentences = split_into_sentences(text)
    for sent in sentences:
        if is_noise_statement(sent):
            continue

        cues = []
        categories = []
        for pat, cat in DEONTIC_PATTERNS:
            for m in re.finditer(pat, sent, re.IGNORECASE):
                cues.append(m.group(0))
                categories.append(cat)

        if cues:
            candidates.append(RequirementCandidate(
                candidate_text=sent,
                cleaned_text=" ".join(sent.split()),
                trigger_cues=list(set(cues)),
                cue_categories=list(set(categories)),
                is_table=False,
                section_id=section_id,
                section_number=section_number,
                heading=heading,
                page_number=page_number,
                confidence_hint="HIGH" if len(cues) > 1 or any(c in ["MANDATORY_SUBMIT", "MANDATORY_MAINTAIN", "PROHIBITION"] for c in categories) else "MEDIUM"
            ))

    return candidates
