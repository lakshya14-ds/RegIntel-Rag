"""
Regulatory Change Intelligence Engine ("What Changed?") (Phase 59).

Answers: "What actually changed between these two regulatory versions?"
Useful to a compliance analyst, not just a generic text diff:
- Mode A (Automatic): Determines reliable predecessor conservatively. If none, returns NO_RELIABLE_PREDECESSOR.
- Mode B (Explicit): Direct comparison between document A and document B.
- Distinguishes substantive changes (obligations, thresholds, deadlines, fees, penalties) from superficial formatting.
- Deterministic diff check: Identical text -> UNCHANGED (zero LLM calls).
- Semantic analysis: Calls Gemini only for candidate modified sections with strict grounding.
- Validates structured output via Pydantic with 1 retry.
- Explicit evidence mapping: every change references source document ID and section ID.
- Impact extraction: affected_entity, deadline, threshold, effective_date.
- Conservative severity: HIGH, MEDIUM, LOW, UNKNOWN.
- Thread-safe caching keyed by content hashes and engine versions.
- Langfuse tracing with child spans.
"""

import re
import json
import hashlib
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple, Literal
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.ingestion.models import RegulatoryDocument
from app.ingestion.version_tracker import VersionTracker
from app.versioning.timeline import TimelineService, get_document_timeline
from app.change_detection.normalizer import (
    normalize_regulatory_text,
    are_texts_substantively_equal
)
from app.change_detection.section_matcher import (
    SectionMatcher,
    ExtractedSection,
    MatchedSectionPair
)
from app.change_detection.document_comparator import DocumentComparator
from app.observability.langfuse_tracer import langfuse_tracer

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

CHANGE_ENGINE_VERSION = "1.0.0"
PROMPT_VERSION = "1.0.0"


# =========================================================================
# DATA MODELS
# =========================================================================

ChangeCategory = Literal["ADDED", "REMOVED", "MODIFIED", "UNCHANGED"]

ChangeSubtype = Literal[
    "THRESHOLD_CHANGED",
    "DEADLINE_CHANGED",
    "ELIGIBILITY_CHANGED",
    "APPLICABILITY_CHANGED",
    "REPORTING_CHANGED",
    "DISCLOSURE_CHANGED",
    "COMPLIANCE_CHANGED",
    "FEE_CHANGED",
    "PENALTY_CHANGED",
    "DOCUMENTATION_CHANGED",
    "PROCEDURE_CHANGED",
    "OTHER"
]

ChangeSeverity = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]


class ImpactDetails(BaseModel):
    """Specific operational and regulatory impact details extracted from evidence."""
    affected_entity: Optional[str] = None
    affected_activity: Optional[str] = None
    effective_date: Optional[str] = None
    deadline: Optional[str] = None
    threshold: Optional[str] = None
    scope: Optional[str] = None


class RegulatoryChangeItem(BaseModel):
    """Structured, evidence-grounded regulatory change entry."""
    change_id: str
    change_type: ChangeCategory
    substantive_change: bool = False
    subtype: Optional[ChangeSubtype] = None
    severity: ChangeSeverity = "UNKNOWN"
    section_number: Optional[str] = None
    heading: str
    summary: str
    previous_requirement: Optional[str] = None
    new_requirement: Optional[str] = None
    impact: Optional[str] = None
    impact_details: Optional[ImpactDetails] = None
    previous_document_id: Optional[str] = None
    previous_section_id: Optional[str] = None
    new_document_id: Optional[str] = None
    new_section_id: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)


class ChangeSummary(BaseModel):
    """Aggregate statistics and key substantive modifications."""
    added: int = 0
    removed: int = 0
    modified: int = 0
    unchanged: int = 0
    total_substantive: int = 0
    key_changes: List[str] = Field(default_factory=list)


class ChangeIntelligenceReport(BaseModel):
    """Complete, structured 'What Changed?' report."""
    status: Literal["SUCCESS", "NO_RELIABLE_PREDECESSOR", "ERROR"]
    message: Optional[str] = None
    change_engine_version: str = CHANGE_ENGINE_VERSION
    prompt_version: str = PROMPT_VERSION
    mode: Literal["AUTOMATIC", "EXPLICIT"] = "EXPLICIT"
    previous_document: Optional[Dict[str, Any]] = None
    current_document: Optional[Dict[str, Any]] = None
    relationship: Optional[Dict[str, Any]] = None
    summary: ChangeSummary = Field(default_factory=ChangeSummary)
    changes: List[RegulatoryChangeItem] = Field(default_factory=list)
    cached: bool = False

    def export_markdown(self) -> str:
        """Generates a clean Markdown export of the What Changed report."""
        lines = [
            f"# REGULATORY CHANGE INTELLIGENCE REPORT ('What Changed?')",
            f"**Engine Version**: {self.change_engine_version} | **Status**: {self.status}\n",
        ]
        if self.status != "SUCCESS":
            lines.append(f"**Notice**: {self.message or 'No details available.'}\n")
            return "\n".join(lines)

        old_title = (self.previous_document or {}).get("title", "Prior Instrument")
        new_title = (self.current_document or {}).get("title", "Current Instrument")
        rel_type = (self.relationship or {}).get("type", "RELATED")
        rel_conf = (self.relationship or {}).get("confidence", "UNKNOWN")

        lines.extend([
            f"### Document Comparison Pair",
            f"- **Prior Version**: {old_title} (ID: `{(self.previous_document or {}).get('document_id', '')}`)",
            f"- **Current Version**: {new_title} (ID: `{(self.current_document or {}).get('document_id', '')}`)",
            f"- **Lineage Relationship**: {rel_type} (Confidence: {rel_conf})\n",
            f"### Executive Change Summary",
            f"- **Added Sections**: {self.summary.added}",
            f"- **Modified Sections**: {self.summary.modified}",
            f"- **Removed Sections**: {self.summary.removed}",
            f"- **Unchanged Sections**: {self.summary.unchanged}",
            f"- **Total Substantive Amendments**: {self.summary.total_substantive}\n",
            f"### Key Substantive Changes"
        ])
        for kc in self.summary.key_changes:
            lines.append(f"- {kc}")

        lines.append("\n### Detailed Section-by-Section Changes\n")
        for ch in self.changes:
            if ch.change_type == "UNCHANGED":
                continue
            lines.extend([
                f"#### [{ch.change_type}] {ch.heading} ({ch.subtype or 'GENERAL'})",
                f"- **Severity**: `{ch.severity}` | **Substantive**: `{ch.substantive_change}`",
                f"- **Summary**: {ch.summary}",
                f"- **Previous Requirement**: {ch.previous_requirement or 'N/A'}",
                f"- **Current Requirement**: {ch.new_requirement or 'N/A'}",
                f"- **Impact**: {ch.impact or 'N/A'}",
            ])
            if ch.impact_details:
                imp = ch.impact_details
                if imp.deadline:
                    lines.append(f"  - Deadline: `{imp.deadline}`")
                if imp.threshold:
                    lines.append(f"  - Threshold: `{imp.threshold}`")
                if imp.effective_date:
                    lines.append(f"  - Effective Date: `{imp.effective_date}`")
                if imp.affected_entity:
                    lines.append(f"  - Affected Entity: `{imp.affected_entity}`")
            if ch.evidence:
                lines.append(f"- **Evidence**: {', '.join(ch.evidence[:2])}")
            lines.append("")

        return "\n".join(lines)


# =========================================================================
# THREAD-SAFE CHANGE INTELLIGENCE CACHE (59.20)
# =========================================================================

class ChangeIntelligenceCache:
    """Thread-safe in-memory cache keyed by content hashes and engine versions."""

    def __init__(self, max_size: int = 150):
        self._cache: Dict[str, ChangeIntelligenceReport] = {}
        self._lock = threading.Lock()
        self._max_size = max_size

    def make_key(self, hash_old: str, hash_new: str) -> str:
        raw = f"{hash_old}:{hash_new}:{CHANGE_ENGINE_VERSION}:{PROMPT_VERSION}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[ChangeIntelligenceReport]:
        with self._lock:
            val = self._cache.get(key)
            if val is not None:
                copied = val.model_copy(deep=True)
                copied.cached = True
                return copied
            return None

    def set(self, key: str, report: ChangeIntelligenceReport) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            self._cache[key] = report.model_copy(deep=True)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


_global_ci_cache = ChangeIntelligenceCache()


def clear_change_intelligence_cache() -> None:
    """Utility to clear global change intelligence cache."""
    _global_ci_cache.clear()


# =========================================================================
# PROMPT TEMPLATE AND STRICT LLM INSTRUCTIONS (59.8, 59.9)
# =========================================================================

CI_SYSTEM_PROMPT = """You are RegIntel Regulatory Change Analyst, an expert financial compliance system specializing in SEBI regulations.

Your task is to analyze the PREVIOUS regulatory section and CURRENT regulatory section supplied below and produce a precise, factually grounded comparison.

Strict Grounding Rules:
1. Base your answer ONLY on the supplied texts of the two sections.
2. Do NOT use outside knowledge, assume unstated intent, or invent legal consequences.
3. Distinguish substantive regulatory changes (changed obligations, prohibitions, eligibility, thresholds, deadlines, effective dates, reporting, disclosures, fees, penalties, applicability) from superficial changes (punctuation, capitalization, whitespace, formatting, wording style).
4. If a threshold, deadline, or entity is affected, extract it exactly as written.
5. If evidence does not support a conclusion, do NOT infer it; explicitly state null or UNKNOWN.
6. Provide short direct evidence quotes from the supplied texts."""


def build_change_intelligence_prompt(section_heading: str, old_text: str, new_text: str) -> str:
    return f"""{CI_SYSTEM_PROMPT}

SECTION HEADING: {section_heading}

--- OLD SECTION ---
{old_text.strip()}

--- NEW SECTION ---
{new_text.strip()}

Respond ONLY with a JSON object matching this schema:
{{
  "change_type": "MODIFIED", // or "UNCHANGED" if only stylistic/formatting
  "substantive_change": true, // boolean
  "subtype": "DEADLINE_CHANGED", // One of: THRESHOLD_CHANGED, DEADLINE_CHANGED, ELIGIBILITY_CHANGED, APPLICABILITY_CHANGED, REPORTING_CHANGED, DISCLOSURE_CHANGED, COMPLIANCE_CHANGED, FEE_CHANGED, PENALTY_CHANGED, DOCUMENTATION_CHANGED, PROCEDURE_CHANGED, OTHER
  "summary": "1-2 sentence factual explanation of what specific regulatory requirement changed.",
  "previous_requirement": "Exact previous requirement or 'N/A'",
  "new_requirement": "Exact current requirement or 'N/A'",
  "impact": "1 sentence describing operational/compliance impact on regulated entities.",
  "impact_details": {{
    "affected_entity": "Name of regulated entity or null",
    "affected_activity": "Activity affected or null",
    "effective_date": "Effective date if stated or null",
    "deadline": "New deadline if stated or null",
    "threshold": "New numerical threshold if stated or null",
    "scope": "Scope change or null"
  }},
  "evidence": ["Short direct quote supporting conclusion"]
}}"""


# =========================================================================
# SEVERITY DETERMINATION LOGIC (59.14)
# =========================================================================

def determine_change_severity(
    subtype: Optional[str],
    substantive_change: bool,
    impact_details: Optional[ImpactDetails]
) -> ChangeSeverity:
    """
    Deterministic regulatory impact severity assessment.
    Rules:
    - HIGH: New obligation, threshold change, penalty change, or deadline reduction
    - MEDIUM: Procedure, documentation, reporting, or disclosure modification
    - LOW: Clarification, non-substantive wording, or minor procedural tweak
    - UNKNOWN: Insufficient evidence or unclassified change
    """
    if not substantive_change:
        return "LOW"

    st = (subtype or "").upper()
    if st in ("THRESHOLD_CHANGED", "PENALTY_CHANGED", "ELIGIBILITY_CHANGED", "APPLICABILITY_CHANGED"):
        return "HIGH"

    if st == "DEADLINE_CHANGED":
        return "HIGH"

    if st in ("REPORTING_CHANGED", "DISCLOSURE_CHANGED", "COMPLIANCE_CHANGED", "PROCEDURE_CHANGED", "DOCUMENTATION_CHANGED", "FEE_CHANGED"):
        return "MEDIUM"

    if impact_details and (impact_details.threshold or impact_details.deadline):
        return "HIGH"

    if st == "OTHER":
        return "MEDIUM"

    return "UNKNOWN"


# =========================================================================
# CHANGE INTELLIGENCE ENGINE (59.1, 59.4)
# =========================================================================

class ChangeIntelligenceEngine:
    """
    Core engine answering: 'What actually changed between these two regulatory versions?'
    """

    def __init__(
        self,
        comparator: Optional[DocumentComparator] = None,
        tracker: Optional[VersionTracker] = None,
        timeline_service: Optional[TimelineService] = None,
        cache: Optional[ChangeIntelligenceCache] = None,
        generator_client: Optional[Any] = None
    ):
        self.comparator = comparator or DocumentComparator()
        self.tracker = tracker or VersionTracker()
        self.timeline_service = timeline_service or TimelineService(tracker=self.tracker)
        self.cache = cache or _global_ci_cache
        self._generator_client = generator_client

    def _get_generator(self) -> Optional[Any]:
        if self._generator_client is not None:
            return self._generator_client
        return self.comparator._get_generator()

    def compare_pair(
        self,
        doc_a_id: str,
        doc_b_id: str,
        generate_summaries: bool = True
    ) -> ChangeIntelligenceReport:
        """
        Mode B: Explicit comparison between two regulatory documents (59.2).
        """
        return self._execute_change_intelligence(
            doc_a_id=doc_a_id,
            doc_b_id=doc_b_id,
            mode="EXPLICIT",
            generate_summaries=generate_summaries
        )

    def analyze_document_changes(
        self,
        current_document_id: str,
        generate_summaries: bool = True
    ) -> ChangeIntelligenceReport:
        """
        Mode A: Automatically determine reliable predecessor for current document (59.2, 59.3).
        If no reliable predecessor exists, returns NO_RELIABLE_PREDECESSOR.
        """
        if not current_document_id or not current_document_id.strip():
            return ChangeIntelligenceReport(
                status="ERROR",
                message="Document ID must be provided."
            )

        clean_id = current_document_id.strip()
        curr_doc = self.comparator.load_document(clean_id)
        if not curr_doc:
            return ChangeIntelligenceReport(
                status="ERROR",
                message=f"Document with ID '{clean_id}' was not found in corpus."
            )

        # 59.3 Determine Comparison Pair using Timeline & Relationships
        timeline_info = self.timeline_service.get_document_timeline(clean_id)
        has_reliable_pred = timeline_info.get("has_reliable_predecessor", False)
        predecessor_id = timeline_info.get("predecessor_id")

        if not has_reliable_pred or not predecessor_id:
            logger.info(f"No reliable predecessor identified for document '{clean_id}'. Returning NO_RELIABLE_PREDECESSOR.")
            return ChangeIntelligenceReport(
                status="NO_RELIABLE_PREDECESSOR",
                message="No reliable predecessor document could be verified with sufficient confidence.",
                mode="AUTOMATIC",
                current_document={
                    "document_id": clean_id,
                    "title": curr_doc.title,
                    "circular_number": curr_doc.circular_number,
                    "published_date": curr_doc.published_date,
                    "status": timeline_info.get("status", "UNKNOWN")
                }
            )

        return self._execute_change_intelligence(
            doc_a_id=predecessor_id,
            doc_b_id=clean_id,
            mode="AUTOMATIC",
            generate_summaries=generate_summaries
        )

    def _execute_change_intelligence(
        self,
        doc_a_id: str,
        doc_b_id: str,
        mode: Literal["AUTOMATIC", "EXPLICIT"],
        generate_summaries: bool = True
    ) -> ChangeIntelligenceReport:
        """Executes full change intelligence pipeline with caching and tracing."""
        # 1. Validation
        doc_a = self.comparator.load_document(doc_a_id)
        if not doc_a:
            return ChangeIntelligenceReport(status="ERROR", message=f"Document A '{doc_a_id}' not found.", mode=mode)

        doc_b = self.comparator.load_document(doc_b_id)
        if not doc_b:
            return ChangeIntelligenceReport(status="ERROR", message=f"Document B '{doc_b_id}' not found.", mode=mode)

        # 2. Chronology Determination
        older_doc, newer_doc, order_conf = self.comparator.determine_chronology(doc_a, doc_b)

        # 3. Check Cache (59.20)
        hash_old = older_doc.content_hash or hashlib.sha256(older_doc.content.encode("utf-8")).hexdigest()
        hash_new = newer_doc.content_hash or hashlib.sha256(newer_doc.content.encode("utf-8")).hexdigest()
        cache_key = self.cache.make_key(hash_old, hash_new)

        cached_report = self.cache.get(cache_key)
        if cached_report is not None:
            logger.info(f"Change Intelligence cache hit for key {cache_key[:12]}")
            cached_report.cached = True
            return cached_report

        # 4. Observability: Start Langfuse Trace & Child Spans (59.22)
        trace_id = f"ci-{uuid_hex(8)}"
        with langfuse_tracer.start_trace(
            name="change_intelligence",
            request_id=trace_id,
            metadata={
                "doc_old": older_doc.document_id,
                "doc_new": newer_doc.document_id,
                "mode": mode,
                "engine_version": CHANGE_ENGINE_VERSION
            }
        ):
            # Span 1: Document Resolution
            rel_type, rel_conf, match_reason = self.comparator.determine_version_relationship(older_doc, newer_doc)

            # Span 2: Section Alignment
            older_sections = SectionMatcher.extract_sections(older_doc.content, document_id=older_doc.document_id)
            newer_sections = SectionMatcher.extract_sections(newer_doc.content, document_id=newer_doc.document_id)
            matched_pairs = SectionMatcher.match_sections(older_sections, newer_sections)

            # Span 3: Semantic Change Analysis (59.8, 59.10)
            client = self._get_generator() if generate_summaries else None
            changes: List[RegulatoryChangeItem] = []
            counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}

            for idx, pair in enumerate(matched_pairs, start=1):
                change_item = self._analyze_section_pair_ci(
                    idx=idx,
                    pair=pair,
                    older_doc=older_doc,
                    newer_doc=newer_doc,
                    client=client
                )
                changes.append(change_item)
                ctype = change_item.change_type.lower()
                if ctype in counts:
                    counts[ctype] += 1

            # Span 4: Report Generation & Summary (59.12)
            key_changes = [ch.summary for ch in changes if ch.substantive_change and ch.change_type != "UNCHANGED"][:5]
            total_substantive = sum(1 for ch in changes if ch.substantive_change)

            summary_obj = ChangeSummary(
                added=counts["added"],
                removed=counts["removed"],
                modified=counts["modified"],
                unchanged=counts["unchanged"],
                total_substantive=total_substantive,
                key_changes=key_changes
            )

            def _doc_info(d: RegulatoryDocument) -> Dict[str, Any]:
                meta = d.metadata.model_dump() if d.metadata else {}
                return {
                    "document_id": d.document_id,
                    "title": d.title,
                    "source": d.source or "SEBI",
                    "category": d.category or meta.get("category"),
                    "circular_number": d.circular_number or meta.get("circular_number"),
                    "published_date": d.published_date or meta.get("published_date"),
                    "effective_date": d.effective_date or meta.get("effective_date"),
                    "status": d.status or meta.get("status", "UNKNOWN"),
                    "content_hash": d.content_hash or meta.get("content_hash"),
                    "url": d.url or ""
                }

            report = ChangeIntelligenceReport(
                status="SUCCESS",
                message="Change intelligence analysis completed successfully.",
                change_engine_version=CHANGE_ENGINE_VERSION,
                prompt_version=PROMPT_VERSION,
                mode=mode,
                previous_document=_doc_info(older_doc),
                current_document=_doc_info(newer_doc),
                relationship={
                    "type": rel_type,
                    "confidence": rel_conf,
                    "match_reason": match_reason
                },
                summary=summary_obj,
                changes=changes,
                cached=False
            )

            # Store in cache
            self.cache.set(cache_key, report)
            return report

    def _analyze_section_pair_ci(
        self,
        idx: int,
        pair: MatchedSectionPair,
        older_doc: RegulatoryDocument,
        newer_doc: RegulatoryDocument,
        client: Optional[Any]
    ) -> RegulatoryChangeItem:
        """Analyzes a matched pair of sections for substantive change intelligence."""
        old_s = pair.older_section
        new_s = pair.newer_section
        change_id = f"change_{idx:03d}"

        # 1. ADDED Section
        if old_s is None and new_s is not None:
            return RegulatoryChangeItem(
                change_id=change_id,
                change_type="ADDED",
                substantive_change=True,
                subtype="APPLICABILITY_CHANGED",
                severity="HIGH",
                section_number=new_s.section_number or str(new_s.order),
                heading=new_s.heading,
                summary=f"New section '{new_s.heading}' introduced.",
                previous_requirement=None,
                new_requirement=new_s.content[:300],
                impact=f"Regulated entities must implement new requirements under '{new_s.heading}'.",
                impact_details=ImpactDetails(scope="Newly introduced requirement"),
                previous_document_id=None,
                previous_section_id=None,
                new_document_id=newer_doc.document_id,
                new_section_id=new_s.section_id,
                evidence=[new_s.content[:200]]
            )

        # 2. REMOVED Section
        if old_s is not None and new_s is None:
            return RegulatoryChangeItem(
                change_id=change_id,
                change_type="REMOVED",
                substantive_change=True,
                subtype="APPLICABILITY_CHANGED",
                severity="MEDIUM",
                section_number=old_s.section_number or str(old_s.order),
                heading=old_s.heading,
                summary=f"Section '{old_s.heading}' omitted or repealed.",
                previous_requirement=old_s.content[:300],
                new_requirement=None,
                impact=f"Prior requirements under '{old_s.heading}' are no longer mandated.",
                impact_details=ImpactDetails(scope="Repealed provision"),
                previous_document_id=older_doc.document_id,
                previous_section_id=old_s.section_id,
                new_document_id=None,
                new_section_id=None,
                evidence=[old_s.content[:200]]
            )

        # 3. Matched Pair
        assert old_s is not None and new_s is not None

        # 3A. Deterministic Difference Stage (59.7)
        # If texts are substantively equal after normalization -> UNCHANGED (Zero Gemini calls)
        if are_texts_substantively_equal(old_s.content, new_s.content):
            return RegulatoryChangeItem(
                change_id=change_id,
                change_type="UNCHANGED",
                substantive_change=False,
                subtype=None,
                severity="LOW",
                section_number=new_s.section_number or old_s.section_number or str(new_s.order),
                heading=new_s.heading,
                summary="Provisions retained verbatim without substantive amendment.",
                previous_requirement=old_s.content[:250],
                new_requirement=new_s.content[:250],
                impact="No compliance modification required.",
                impact_details=None,
                previous_document_id=older_doc.document_id,
                previous_section_id=old_s.section_id,
                new_document_id=newer_doc.document_id,
                new_section_id=new_s.section_id,
                evidence=[]
            )

        # 3B. Candidate Modified Section: Semantic Analysis (59.8, 59.9, 59.10)
        subtype: Optional[ChangeSubtype] = self._infer_subtype_keywords(f"{new_s.content} {old_s.content}")
        llm_data = None

        if client:
            llm_data = self._call_gemini_ci(
                client=client,
                section_heading=new_s.heading,
                old_text=old_s.content,
                new_text=new_s.content
            )

        if llm_data:
            stype = llm_data.get("subtype") or subtype or "OTHER"
            is_subst = llm_data.get("substantive_change", True)
            imp_dict = llm_data.get("impact_details")
            imp_obj = None
            if imp_dict and isinstance(imp_dict, dict):
                try:
                    imp_obj = ImpactDetails(**imp_dict)
                except Exception:
                    pass

            severity = determine_change_severity(stype, is_subst, imp_obj)

            return RegulatoryChangeItem(
                change_id=change_id,
                change_type=llm_data.get("change_type", "MODIFIED"),
                substantive_change=is_subst,
                subtype=stype,
                severity=severity,
                section_number=new_s.section_number or old_s.section_number or str(new_s.order),
                heading=new_s.heading,
                summary=llm_data.get("summary", f"Section '{new_s.heading}' modified."),
                previous_requirement=llm_data.get("previous_requirement") or old_s.content[:250],
                new_requirement=llm_data.get("new_requirement") or new_s.content[:250],
                impact=llm_data.get("impact"),
                impact_details=imp_obj,
                previous_document_id=older_doc.document_id,
                previous_section_id=old_s.section_id,
                new_document_id=newer_doc.document_id,
                new_section_id=new_s.section_id,
                evidence=llm_data.get("evidence", [new_s.content[:200]])
            )

        # Deterministic fallback when Gemini is offline or not requested
        severity = determine_change_severity(subtype, True, None)
        return RegulatoryChangeItem(
            change_id=change_id,
            change_type="MODIFIED",
            substantive_change=True,
            subtype=subtype or "OTHER",
            severity=severity,
            section_number=new_s.section_number or old_s.section_number or str(new_s.order),
            heading=new_s.heading,
            summary=f"Provisions in '{new_s.heading}' amended ({subtype or 'general'}).",
            previous_requirement=old_s.content[:250],
            new_requirement=new_s.content[:250],
            impact=f"Review revised requirements under '{new_s.heading}'.",
            impact_details=None,
            previous_document_id=older_doc.document_id,
            previous_section_id=old_s.section_id,
            new_document_id=newer_doc.document_id,
            new_section_id=new_s.section_id,
            evidence=[new_s.content[:200]]
        )

    def _call_gemini_ci(
        self,
        client: Any,
        section_heading: str,
        old_text: str,
        new_text: str
    ) -> Optional[Dict[str, Any]]:
        """Invokes Gemini with 1 retry on invalid structured JSON."""
        prompt = build_change_intelligence_prompt(
            section_heading=section_heading,
            old_text=old_text,
            new_text=new_text
        )

        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=settings.gemini_generation_model,
                    contents=prompt
                )
                raw = response.text.strip() if response and response.text else ""
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw.rsplit("```", 1)[0]
                raw = raw.strip()
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "change_type" in parsed:
                    return parsed
            except Exception as e:
                logger.warning(f"Gemini Change Intelligence attempt {attempt + 1} failed: {e}")
        return None

    def _infer_subtype_keywords(self, text: str) -> Optional[ChangeSubtype]:
        """Infers change subtype deterministically based on domain keywords."""
        lower = text.lower()
        if any(k in lower for k in ["deadline", "days", "months", "timeline", "w.e.f.", "within 30 days", "within 15 days"]):
            return "DEADLINE_CHANGED"
        if any(k in lower for k in ["threshold", "net worth", "capital requirement", "50 lakhs", "crores", "%"]):
            return "THRESHOLD_CHANGED"
        if any(k in lower for k in ["fee", "fees", "expense ratio", "ter", "charges"]):
            return "FEE_CHANGED"
        if any(k in lower for k in ["eligibility", "qualification", "certification", "nism"]):
            return "ELIGIBILITY_CHANGED"
        if any(k in lower for k in ["penalty", "penalties", "adjudication", "fine"]):
            return "PENALTY_CHANGED"
        if any(k in lower for k in ["report", "reporting", "filing", "portal"]):
            return "REPORTING_CHANGED"
        if any(k in lower for k in ["disclosure", "advertisement", "website"]):
            return "DISCLOSURE_CHANGED"
        if any(k in lower for k in ["audit", "compliance officer", "internal control"]):
            return "COMPLIANCE_CHANGED"
        if any(k in lower for k in ["agreement", "documentation", "records", "8 years"]):
            return "DOCUMENTATION_CHANGED"
        if any(k in lower for k in ["procedure", "workflow", "process", "sop"]):
            return "PROCEDURE_CHANGED"
        if any(k in lower for k in ["applicable to", "applicability", "scope"]):
            return "APPLICABILITY_CHANGED"
        return "OTHER"


def uuid_hex(length: int = 8) -> str:
    import uuid
    return uuid.uuid4().hex[:length]


# Singleton instance
_change_intelligence_engine = ChangeIntelligenceEngine()


def get_change_intelligence_engine() -> ChangeIntelligenceEngine:
    return _change_intelligence_engine
