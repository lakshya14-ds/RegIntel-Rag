"""
Regulatory Text and Heading Normalization Module.

Normalizes superficial text differences (repeated whitespace, line ending variations,
quote styles, bullet points) while strictly preserving substantive regulatory tokens:
- Section and clause numbers (e.g. 4.2, Regulation 15A, (1)(a))
- Legal terminology (shall, must, prohibited, mandatory, exempt)
- Dates, percentages, monetary amounts, penalties, timelines (e.g. INR 50 Lakhs, 25%, 30 days, 8 years)
- Headings and vital punctuation
"""

import re
from typing import Tuple


def normalize_whitespace(text: str) -> str:
    """Normalizes whitespace and line breaks without altering word tokens."""
    if not text:
        return ""
    # Standardize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Normalize multiple blank lines to at most two
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Normalize spaces within lines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def normalize_punctuation_and_quotes(text: str) -> str:
    """Standardizes smart quotes and bullet dashes to canonical ASCII representations."""
    if not text:
        return ""
    replacements = {
        "\u2018": "'",  # Left single quotation mark
        "\u2019": "'",  # Right single quotation mark
        "\u201c": '"',  # Left double quotation mark
        "\u201d": '"',  # Right double quotation mark
        "\u2013": "-",  # En dash
        "\u2014": "-",  # Em dash
        "\u2022": "-",  # Bullet symbol
        "•": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'"
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text


def normalize_regulatory_text(text: str) -> str:
    """
    Performs comprehensive conservative normalization for regulatory comparison.
    Preserves all numbers, section IDs, legal verbs, and dates.
    """
    if not text:
        return ""
    cleaned = normalize_punctuation_and_quotes(text)
    cleaned = normalize_whitespace(cleaned)
    return cleaned


def normalize_heading(heading: str) -> str:
    """
    Normalizes section heading for cross-revision section alignment.
    Strips markdown prefix (#), leading numbers, and punctuation.
    """
    if not heading:
        return ""
    # Remove markdown header syntax and leading numbers e.g. "## 1.2 Eligibility" -> "Eligibility"
    clean = re.sub(r"^[#\s\d\.\-_:]+", "", heading).lower()
    clean = re.sub(r"[^\w\s]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def extract_section_number(heading: str) -> Tuple[str, str]:
    """
    Extracts section number and clean title from a raw heading.
    Examples:
        "1.2 Eligibility Requirements" -> ("1.2", "Eligibility Requirements")
        "Section 4: Audit Norms" -> ("4", "Audit Norms")
        "## General Provisions" -> ("", "General Provisions")
    """
    if not heading:
        return "", ""

    raw = re.sub(r"^#+\s*", "", heading).strip()

    # Pattern: Section 4.2 or Clause 4.2 or 4.2 or 4.
    m = re.match(r"^(?:Section|Clause|Reg\.?|Regulation)?\s*(\d+(?:\.\d+)*)\.?\s*[:\-\s]\s*(.+)$", raw, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Pattern without colon: "1.2 Eligibility"
    m2 = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$", raw)
    if m2:
        return m2.group(1).strip(), m2.group(2).strip()

    return "", raw


def are_texts_substantively_equal(text_a: str, text_b: str) -> bool:
    """
    Determines if two texts are substantively identical after superficial formatting normalization.
    """
    if not text_a and not text_b:
        return True
    if not text_a or not text_b:
        return False

    norm_a = normalize_regulatory_text(text_a)
    norm_b = normalize_regulatory_text(text_b)

    if norm_a == norm_b:
        return True

    # Check case-insensitive and collapsed whitespace identity
    collapsed_a = re.sub(r"\s+", " ", norm_a).lower()
    collapsed_b = re.sub(r"\s+", " ", norm_b).lower()

    return collapsed_a == collapsed_b
