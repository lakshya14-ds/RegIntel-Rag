"""
Prompt templates for Regulatory Section Comparison and Structured Change Summarization.
"""

from typing import Optional

SECTION_COMPARISON_SYSTEM_PROMPT = """You are RegIntel Change Analyst, an authoritative regulatory intelligence system for financial compliance (SEBI).

Your task is to analyze the PREVIOUS regulatory section and CURRENT regulatory section supplied below and produce a precise, factually grounded comparison.

Strict Grounding Rules:
1. Compare ONLY the supplied text of the two sections.
2. Distinguish:
   a. Superficial formatting / stylistic wording changes (substantive_change = false)
   b. Actual regulatory changes (substantive_change = true, e.g. obligations, prohibitions, eligibility, fee caps, reporting timelines, audit frequencies, penalties, applicability).
3. Do NOT invent or extrapolate legal interpretations, affected entities, deadlines, penalties, or effective dates not explicitly present in the text.
4. If the supplied text does not support a conclusion, do not infer it.
5. Provide evidence quotes strictly from the supplied texts."""


def build_structured_comparison_prompt(
    section_title: str,
    previous_text: Optional[str],
    current_text: Optional[str]
) -> str:
    """Constructs prompt requesting strict JSON structured comparison."""
    prev_str = previous_text.strip() if previous_text and previous_text.strip() else "[Section did not exist in previous version]"
    curr_str = current_text.strip() if current_text and current_text.strip() else "[Section removed in current version]"

    return f"""{SECTION_COMPARISON_SYSTEM_PROMPT}

SECTION TITLE: {section_title}

PREVIOUS VERSION:
{prev_str}

CURRENT VERSION:
{curr_str}

Analyze the regulatory differences between the two versions and return a valid JSON object matching this schema:
{{
  "change_type": "MODIFIED",  // "ADDED", "REMOVED", "MODIFIED", or "UNCHANGED"
  "substantive_change": true, // boolean: true if compliance obligations/thresholds changed, false if purely stylistic
  "summary": "1-2 sentence factual statement of what specific requirement changed.",
  "old_requirement": "Exact previous requirement or 'N/A'",
  "new_requirement": "Exact current requirement or 'N/A'",
  "impact": "1 sentence describing operational/compliance impact on regulated entities.",
  "evidence": ["Exact short quote from previous or current version supporting this"]
}}

Respond ONLY with the JSON object, with no markdown code fences or conversational prose."""


def build_section_comparison_prompt(
    section_title: str,
    previous_text: str,
    current_text: str
) -> str:
    """Legacy helper for plain-text comparison prompt."""
    return f"""{SECTION_COMPARISON_SYSTEM_PROMPT}

SECTION: {section_title}

PREVIOUS VERSION:
{previous_text.strip() if previous_text and previous_text.strip() else "[Section did not exist in previous version]"}

CURRENT VERSION:
{current_text.strip() if current_text and current_text.strip() else "[Section removed in current version]"}

Analyze the exact differences and provide:
1. Summary: A 1-2 sentence factual explanation of what specifically changed.
2. Impact: A 1 sentence statement of the compliance/operational effect on regulated entities.

Format your response as:
Summary: <summary text>
Impact: <impact text>"""
