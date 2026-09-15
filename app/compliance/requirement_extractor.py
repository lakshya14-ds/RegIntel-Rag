"""
Regulatory Requirement Extraction Engine (Phase 61).

Transforms regulatory text and candidates into structured, normalized, atomic,
and grounded RegulatoryRequirement records.
"""

import re
import json
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from app.config import settings
from app.llm import get_llm_provider
from app.compliance.models import (
    RegulatoryRequirement,
    RequirementType,
    RequirementConfidence,
    RequirementThreshold,
)
from app.compliance.candidate_detector import (
    RequirementCandidate,
    detect_candidate_requirements_in_text,
)
from app.observability.langfuse_tracer import langfuse_tracer

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

PROMPT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"


# =============================================================================
# STRUCTURED LLM VALIDATION SCHEMA (61.4)
# =============================================================================

class LLMRequirementItem(BaseModel):
    """Pydantic model for structured extraction from LLM."""
    requirement_type: RequirementType = "COMPLIANCE"
    subject: Optional[str] = Field(None, description="Who is obligated (e.g. 'registered investment adviser')")
    action: Optional[str] = Field(None, description="Action required (e.g. 'submit', 'maintain', 'disclose')")
    object: Optional[str] = Field(None, description="Target entity or deliverable (e.g. 'quarterly compliance report')")
    applicability: Optional[str] = Field(None, description="Applicability scope or entity category")
    conditions: List[str] = Field(default_factory=list, description="Conditions trigger e.g. 'if turnover exceeds ₹50 Lakhs'")
    exceptions: List[str] = Field(default_factory=list, description="Exceptions e.g. 'except where exempted under clause 4'")
    deadline: Optional[str] = Field(None, description="Exact deadline e.g. 'within 15 days of end of quarter'")
    frequency: Optional[str] = Field(None, description="Frequency e.g. 'QUARTERLY', 'ANNUALLY', 'ON_EVENT'")
    threshold_raw: Optional[str] = Field(None, description="Threshold, amount, percentage or duration mentioned")
    confidence: RequirementConfidence = "HIGH"


class LLMExtractionBatch(BaseModel):
    requirements: List[LLMRequirementItem] = Field(default_factory=list)


# =============================================================================
# DETERMINISTIC NUMERIC & TEMPORAL EXTRACTOR (61.8)
# =============================================================================

NUMERIC_PATTERNS = [
    # Deadlines / Durations: e.g. "15 days", "30 days", "8 years", "6 months"
    (r"\b(\d+)\s*(days?|months?|years?|weeks?|hours?)\b", "duration"),
    # Percentages: e.g. "10%", "2.5%", "100%"
    (r"\b(\d+(?:\.\d+)?)\s*%", "percentage"),
    # Currency / Amounts: e.g. "₹50 Lakhs", "INR 25 Lakhs", "Rs. 1 Crore"
    (r"(?:\bINR\b|\bRs\.?|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(Lakhs?|Crores?|thousand)?\b", "currency"),
    # Ratios
    (r"\b(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\b", "ratio"),
]

FREQUENCY_PATTERNS = [
    (r"\bquarterly\b|\beach\s+quarter\b|\bevery\s+quarter\b", "QUARTERLY"),
    (r"\bannually\b|\byearly\b|\beach\s+year\b", "ANNUALLY"),
    (r"\bhalf-yearly\b|\bsemi-annually\b", "SEMI_ANNUALLY"),
    (r"\bmonthly\b|\beach\s+month\b", "MONTHLY"),
    (r"\bweekly\b", "WEEKLY"),
    (r"\bdaily\b", "DAILY"),
    (r"\bimmediate(?:ly)?\b|\bforthwith\b", "IMMEDIATE"),
    (r"\bon\s+demand\b|\bupon\s+request\b", "ON_REQUEST"),
]


def extract_thresholds_and_numerics(text: str) -> List[RequirementThreshold]:
    """Extracts structured numeric constraints from text."""
    thresholds: List[RequirementThreshold] = []
    seen = set()

    for pat, ptype in NUMERIC_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            full = m.group(0).strip()
            if full.lower() not in seen:
                seen.add(full.lower())
                val_str = m.group(1).replace(",", "")
                try:
                    num_val = float(val_str)
                except ValueError:
                    num_val = None

                unit = m.group(2) if len(m.groups()) >= 2 else None
                thresholds.append(RequirementThreshold(
                    parameter_type=ptype,
                    raw_value=full,
                    normalized_value=num_val,
                    unit=unit.lower() if unit else None,
                    operator="<=" if "within" in text.lower() or "not later" in text.lower() else ">=" if "at least" in text.lower() else "=="
                ))

    return thresholds


def extract_frequency_deterministic(text: str) -> Optional[str]:
    """Extracts regulatory frequency deterministically."""
    for pat, freq in FREQUENCY_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return freq
    return None


def extract_deadline_deterministic(text: str) -> Optional[str]:
    """Extracts explicit deadline clause from text."""
    m = re.search(r"\b(?:within\s+\d+\s*(?:days?|weeks?|months?|hours?)(?:\s+of[^\.,;]+)?|not\s+later\s+than[^\.,;]+)\b", text, re.IGNORECASE)
    if m:
        return m.group(0).strip()
    return None


# =============================================================================
# ATOMIC REQUIREMENT SPLITTER (61.6)
# =============================================================================

def split_compound_requirement(text: str) -> List[str]:
    """
    Splits compound requirements connected by conjunctive clauses when each clause
    represents an independent obligation, while preserving shared context.
    Example: 'shall maintain records for 8 years and submit quarterly reports'
    -> ['shall maintain records for 8 years', 'submit quarterly reports']
    """
    # Look for patterns like 'shall X and [shall] Y'
    match = re.search(r"\bshall\s+([^\.]+?)\s+and\s+(?:shall\s+)?(submit|maintain|disclose|report|file|ensure|conduct|audit|pay)\b", text, re.IGNORECASE)
    if match and len(match.groups()) == 2:
        part1 = text[:match.start()] + "shall " + match.group(1).strip()
        part2 = "The regulated entity shall " + match.group(2) + text[match.end():]
        return [part1.strip(), part2.strip()]
    return [text.strip()]


# =============================================================================
# DETERMINISTIC EXTRACTOR (Zero-LLM fallback / baseline)
# =============================================================================

def extract_requirement_deterministic(
    candidate: RequirementCandidate,
    document_id: str,
    authority: str = "SEBI",
    document_title: Optional[str] = None,
    document_type: Optional[str] = None,
    effective_date: Optional[str] = None
) -> List[RegulatoryRequirement]:
    """
    Extracts atomic requirements deterministically without invoking the LLM.
    """
    text = candidate.cleaned_text
    atomic_texts = split_compound_requirement(text)
    results: List[RegulatoryRequirement] = []

    for sub_text in atomic_texts:
        thresholds = extract_thresholds_and_numerics(sub_text)
        deadline = extract_deadline_deterministic(sub_text)
        frequency = extract_frequency_deterministic(sub_text)

        # Deontic type inference
        req_type: RequirementType = "COMPLIANCE"
        t_lower = sub_text.lower()
        if any(k in t_lower for k in ["report", "reporting", "return"]):
            req_type = "REPORTING"
        elif any(k in t_lower for k in ["disclose", "disclosure", "website"]):
            req_type = "DISCLOSURE"
        elif any(k in t_lower for k in ["record", "records", "register", "maintain records"]):
            req_type = "RECORD_KEEPING"
        elif any(k in t_lower for k in ["prohibited", "shall not", "must not"]):
            req_type = "PROHIBITION"
        elif any(k in t_lower for k in ["audit", "auditor"]):
            req_type = "AUDIT"
        elif any(k in t_lower for k in ["notify", "notification", "intimate"]):
            req_type = "NOTIFICATION"
        elif any(k in t_lower for k in ["submit", "submission", "file"]):
            req_type = "SUBMISSION"
        elif any(k in t_lower for k in ["approval", "prior approval"]):
            req_type = "APPROVAL"
        elif any(k in t_lower for k in ["calculate", "net worth", "capital"]):
            req_type = "CALCULATION"

        # Condition & Exception regex
        conditions = []
        cond_m = re.search(r"\b(?:if|when|where|provided\s+that|subject\s+to)\s+([^,;\.]+)", sub_text, re.IGNORECASE)
        if cond_m:
            conditions.append(cond_m.group(0).strip())

        exceptions = []
        exc_m = re.search(r"\b(?:except\s+where|unless|save\s+as)\s+([^,;\.]+)", sub_text, re.IGNORECASE)
        if exc_m:
            exceptions.append(exc_m.group(0).strip())

        # Subject extraction
        subject = None
        subj_m = re.search(r"\b(?:the\s+)?(intermediary|investment\s+adviser|research\s+analyst|mutual\s+fund|asset\s+management\s+company|amc|stock\s+broker|depository\s+participant|merchant\s+banker|listed\s+entity|regulated\s+entity|entity)\b", sub_text, re.IGNORECASE)
        if subj_m:
            subject = subj_m.group(1).title()

        # Action & Object extraction
        action = None
        act_m = re.search(r"\bshall\s+([a-z]+)\b", sub_text, re.IGNORECASE)
        if act_m:
            action = act_m.group(1).lower()

        # Deterministic identity hash (61.9)
        sec_key = candidate.section_id or "sec"
        norm_key = f"{document_id}:{sec_key}:{req_type}:{action}:{sub_text[:60].lower()}"
        req_id = f"req_{hashlib.sha256(norm_key.encode('utf-8')).hexdigest()[:12]}"

        results.append(RegulatoryRequirement(
            requirement_id=req_id,
            document_id=document_id,
            document_version_id="1.0",
            section_id=candidate.section_id,
            authority=authority,
            document_type=document_type,
            document_title=document_title,
            requirement_text=sub_text,
            normalized_requirement=f"Subject: {subject or 'Regulated Entity'} | Action: {action or 'comply'} | Type: {req_type}",
            requirement_type=req_type,
            subject=subject,
            action=action,
            object=None,
            applicability=subject,
            conditions=conditions,
            exceptions=exceptions,
            effective_date=effective_date,
            deadline=deadline,
            frequency=frequency,
            thresholds=thresholds,
            source_evidence=candidate.cleaned_text,
            source_locator={
                "section_id": candidate.section_id,
                "section_number": candidate.section_number,
                "heading": candidate.heading,
                "page_number": candidate.page_number
            },
            confidence=candidate.confidence_hint,
            extraction_method="DETERMINISTIC",
            content_hash=hashlib.sha256(sub_text.encode("utf-8")).hexdigest()
        ))

    return results


# =============================================================================
# REQUIREMENT EXTRACTION PIPELINE (61.4)
# =============================================================================

def build_requirement_prompt(
    document_title: str,
    section_heading: str,
    candidate_text: str
) -> str:
    """Builds prompt instructing Gemini/LLM to extract structured requirements."""
    return f"""You are an expert regulatory compliance intelligence analyzer.
Your task is to extract structured, actionable regulatory requirements strictly supported by the text below.

STRICT REGULATORY RULES:
1. Extract ONLY requirements explicitly stated in the regulatory text.
2. DO NOT hallucinate obligations, deadlines, applicability, or consequences.
3. Preserve all numerical values, percentages, currencies, and timeframes EXACTLY.
4. Distinguish mandatory obligations (shall, must) from prohibitions (shall not) or recommendations (should).
5. If subject or deadline is not specified in the text, return null.
6. Return valid JSON only adhering strictly to the schema below.

DOCUMENT TITLE: {document_title}
SECTION HEADING: {section_heading}
SOURCE TEXT:
\"\"\"
{candidate_text}
\"\"\"

JSON SCHEMA:
{{
  "requirements": [
    {{
      "requirement_type": "REPORTING | DISCLOSURE | RECORD_KEEPING | APPROVAL | NOTIFICATION | PROHIBITION | PERMISSION | CALCULATION | COMPLIANCE | GOVERNANCE | DOCUMENTATION | MONITORING | AUDIT | SUBMISSION | MAINTENANCE | PROCEDURAL | OTHER",
      "subject": "who is obligated, e.g. 'registered investment adviser' or null",
      "action": "mandatory action verb e.g. 'submit', 'maintain', 'disclose'",
      "object": "target of action e.g. 'quarterly compliance report'",
      "applicability": "scope of entities to which this applies, or null",
      "conditions": ["list of conditions, e.g. 'turnover > 50 Lakhs'"],
      "exceptions": ["list of exceptions, e.g. 'except where exempted'"],
      "deadline": "exact deadline string e.g. 'within 15 days of end of quarter' or null",
      "frequency": "QUARTERLY | ANNUALLY | MONTHLY | DAILY | ON_EVENT | ONCE | null",
      "threshold_raw": "raw threshold or numeric parameter mentioned, or null",
      "confidence": "HIGH | MEDIUM | LOW"
    }}
  ]
}}
"""


class RequirementExtractor:
    """
    Extracts, normalizes, validates, and deduplicates regulatory requirements.
    """

    def __init__(self):
        self.llm_provider = None

    def _get_provider(self):
        if self.llm_provider is None:
            try:
                self.llm_provider = get_llm_provider()
            except Exception as e:
                logger.warning(f"Could not initialize LLM provider: {e}")
        return self.llm_provider

    def extract_requirements_from_text(
        self,
        text: str,
        document_id: str,
        authority: str = "SEBI",
        document_title: Optional[str] = None,
        document_type: Optional[str] = None,
        effective_date: Optional[str] = None,
        section_id: Optional[str] = None,
        section_number: Optional[str] = None,
        heading: Optional[str] = None,
        page_number: Optional[int] = None,
        use_llm: bool = False
    ) -> List[RegulatoryRequirement]:
        """
        Full extraction pipeline:
        Candidate Detection -> Normalization -> (Optional LLM Enrichment) -> Validation -> Deduplication
        """
        candidates = detect_candidate_requirements_in_text(
            text=text,
            section_id=section_id,
            section_number=section_number,
            heading=heading,
            page_number=page_number
        )

        if not candidates:
            return []

        all_reqs: List[RegulatoryRequirement] = []
        seen_identity_keys = set()

        for cand in candidates:
            # 1. Deterministic Extraction baseline
            det_reqs = extract_requirement_deterministic(
                candidate=cand,
                document_id=document_id,
                authority=authority,
                document_title=document_title,
                document_type=document_type,
                effective_date=effective_date
            )

            # 2. LLM Semantic Extraction if requested
            if use_llm:
                provider = self._get_provider()
                if provider and provider.is_available():
                    prompt = build_requirement_prompt(
                        document_title=document_title or "Regulatory Document",
                        section_heading=heading or "General Provisions",
                        candidate_text=cand.cleaned_text
                    )
                    try:
                        llm_resp = provider.generate(prompt=prompt, temperature=0.0)
                        raw_json = llm_resp.text.strip()
                        if raw_json.startswith("```"):
                            raw_json = raw_json.split("\n", 1)[-1]
                        if raw_json.endswith("```"):
                            raw_json = raw_json.rsplit("```", 1)[0]
                        data = json.loads(raw_json.strip())
                        batch = LLMExtractionBatch.model_validate(data)

                        for item in batch.requirements:
                            sec_key = cand.section_id or "sec"
                            norm_key = f"{document_id}:{sec_key}:{item.requirement_type}:{item.action}:{cand.cleaned_text[:60].lower()}"
                            req_id = f"req_{hashlib.sha256(norm_key.encode('utf-8')).hexdigest()[:12]}"

                            th_list = extract_thresholds_and_numerics(cand.cleaned_text)
                            if item.threshold_raw:
                                th_list.extend(extract_thresholds_and_numerics(item.threshold_raw))

                            req = RegulatoryRequirement(
                                requirement_id=req_id,
                                document_id=document_id,
                                document_version_id="1.0",
                                section_id=cand.section_id,
                                authority=authority,
                                document_type=document_type,
                                document_title=document_title,
                                requirement_text=cand.cleaned_text,
                                normalized_requirement=f"Subject: {item.subject or 'Regulated Entity'} | Action: {item.action or 'comply'} | Type: {item.requirement_type}",
                                requirement_type=item.requirement_type,
                                subject=item.subject,
                                action=item.action,
                                object=item.object,
                                applicability=item.applicability or item.subject,
                                conditions=item.conditions,
                                exceptions=item.exceptions,
                                effective_date=effective_date,
                                deadline=item.deadline or extract_deadline_deterministic(cand.cleaned_text),
                                frequency=item.frequency or extract_frequency_deterministic(cand.cleaned_text),
                                thresholds=th_list,
                                source_evidence=cand.cleaned_text,
                                source_locator={
                                    "section_id": cand.section_id,
                                    "section_number": cand.section_number,
                                    "heading": cand.heading,
                                    "page_number": cand.page_number
                                },
                                confidence=item.confidence,
                                extraction_method="LLM",
                                content_hash=hashlib.sha256(cand.cleaned_text.encode("utf-8")).hexdigest()
                            )
                            # Deduplicate (61.9)
                            dedup_key = (req.document_id, req.section_id, req.subject, req.action, req.requirement_type)
                            if dedup_key not in seen_identity_keys:
                                seen_identity_keys.add(dedup_key)
                                all_reqs.append(req)
                        continue
                    except Exception as e:
                        logger.warning(f"LLM Requirement extraction failed, using deterministic output: {e}")

            # Fallback / Default to deterministic results
            for d_req in det_reqs:
                dedup_key = (d_req.document_id, d_req.section_id, d_req.subject, d_req.action, d_req.requirement_type)
                if dedup_key not in seen_identity_keys:
                    seen_identity_keys.add(dedup_key)
                    all_reqs.append(d_req)

        return all_reqs


# Global singleton extractor
_requirement_extractor = RequirementExtractor()


def get_requirement_extractor() -> RequirementExtractor:
    return _requirement_extractor


def extract_requirements_from_text(
    text: str,
    document_id: str,
    authority: str = "SEBI",
    document_title: Optional[str] = None,
    document_type: Optional[str] = None,
    effective_date: Optional[str] = None,
    section_id: Optional[str] = None,
    section_number: Optional[str] = None,
    heading: Optional[str] = None,
    page_number: Optional[int] = None,
    use_llm: bool = False
) -> List[RegulatoryRequirement]:
    """Convenience function calling the singleton RequirementExtractor."""
    return _requirement_extractor.extract_requirements_from_text(
        text=text,
        document_id=document_id,
        authority=authority,
        document_title=document_title,
        document_type=document_type,
        effective_date=effective_date,
        section_id=section_id,
        section_number=section_number,
        heading=heading,
        page_number=page_number,
        use_llm=use_llm
    )

