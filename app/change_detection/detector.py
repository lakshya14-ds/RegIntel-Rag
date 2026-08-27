"""
Regulatory Change Detection and Comparative Analysis Orchestrator.

Orchestrates automatic predecessor identification, structured section alignment,
Gemini-powered delta summarization, and change report validation.
"""

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from app.config import settings
from app.ingestion.models import RegulatoryDocument, from_mongo
from app.change_detection.document_matcher import DocumentMatcher, PredecessorMatch
from app.change_detection.section_comparer import SectionComparer, SectionChange, AlignedSectionPair
from app.change_detection.prompts import build_section_comparison_prompt

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class ChangeReport(BaseModel):
    """Normalized structured regulatory change report."""
    status: str = Field(default="SUCCESS")  # SUCCESS, NO_RELIABLE_PREDECESSOR, ERROR
    message: Optional[str] = None
    current_document: Dict[str, Any] = Field(default_factory=dict)
    previous_document: Optional[Dict[str, Any]] = None
    relationship_confidence: Optional[str] = None
    match_reason: Optional[str] = None
    executive_summary: str = Field(default="")
    changes: List[SectionChange] = Field(default_factory=list)
    total_sections_compared: int = 0
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    unchanged_count: int = 0

    def print_formatted(self):
        """Prints the change report formatted for terminal inspection."""
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"

        def _safe(t: str) -> str:
            return t.encode(encoding, errors="replace").decode(encoding)

        print("\n" + "=" * 65)
        print("REGULATORY CHANGE ANALYSIS REPORT")
        print("=" * 65)

        if self.status != "SUCCESS":
            print(f"\nStatus  : {self.status}")
            print(f"Message : {_safe(self.message or 'No details.')}\n")
            return

        curr_title = self.current_document.get("title", "Untitled Current")
        prev_title = self.previous_document.get("title", "Untitled Previous") if self.previous_document else "None"
        curr_date = self.current_document.get("published_date", "N/A")
        prev_date = self.previous_document.get("published_date", "N/A") if self.previous_document else "N/A"

        print(f"\nCurrent Document  : {_safe(curr_title)} (Date: {curr_date})")
        print(f"Previous Document : {_safe(prev_title)} (Date: {prev_date})")
        print(f"Lineage Confidence: {self.relationship_confidence.upper() if self.relationship_confidence else 'N/A'}")
        if self.match_reason:
            print(f"Match Reason      : {_safe(self.match_reason)}")

        print("\n" + "-" * 65)
        print("EXECUTIVE SUMMARY")
        print("-" * 65)
        print(_safe(self.executive_summary))

        print("\n" + "-" * 65)
        print(f"DETAILED SECTION DELTAS (Total: {self.total_sections_compared} | Added: {self.added_count} | Modified: {self.modified_count} | Removed: {self.removed_count} | Unchanged: {self.unchanged_count})")
        print("-" * 65)

        for idx, c in enumerate(self.changes, start=1):
            if c.change_type == "UNCHANGED":
                continue
            badge = f"[{c.change_type}]"
            subcat = f"({c.modification_category.upper()})" if c.modification_category else ""
            print(f"\n{idx}. {badge} {subcat} {_safe(c.title)}")
            if c.summary:
                print(f"   Summary : {_safe(c.summary)}")
            if c.impact:
                print(f"   Impact  : {_safe(c.impact)}")
            if c.evidence:
                print(f"   Evidence: {c.evidence}")

        print("\n" + "=" * 65 + "\n")


class RegulatoryChangeDetector:
    """
    Service for executing regulatory change detection across document versions.
    """

    def __init__(self, processed_data_dir: Optional[Path] = None, generator_client: Optional[Any] = None):
        self.processed_dir = processed_data_dir or settings.processed_data_dir
        self.generator_client = generator_client

    def load_all_documents(self) -> List[RegulatoryDocument]:
        """Loads all processed regulatory document JSON files from disk."""
        doc_files = list(self.processed_dir.glob("*.json"))
        docs: List[RegulatoryDocument] = []
        for df in doc_files:
            if df.name.endswith("_chunks.json"):
                continue
            try:
                with open(df, "r", encoding="utf-8") as f:
                    data = json.load(f)
                docs.append(from_mongo(RegulatoryDocument, data))
            except Exception as e:
                logger.error(f"Error loading document {df.name}: {e}")
        return docs

    def _summarize_section_diff(
        self,
        section_title: str,
        prev_text: str,
        curr_text: str,
        change_type: str,
        mod_cat: Optional[str]
    ) -> Tuple[str, str]:
        """
        Calls Gemini Flash-Lite or rule-based logic to produce concise summary and impact.
        """
        if change_type == "ADDED":
            return (
                f"New section introduced defining {mod_cat or 'operational'} guidelines.",
                "Regulated entities must establish compliance procedures for the newly introduced requirement."
            )
        elif change_type == "REMOVED":
            return (
                f"Section governing {mod_cat or 'previous requirements'} has been omitted in the current revision.",
                "Previous regulatory obligation is no longer mandated under this circular."
            )
        elif change_type == "UNCHANGED":
            return ("No substantive regulatory change.", "Existing compliance standard remains in effect.")

        # Attempt Gemini LLM comparison for MODIFIED sections if API is available
        prompt = build_section_comparison_prompt(
            section_title=section_title,
            previous_text=prev_text,
            current_text=curr_text
        )

        try:
            from app.rag.generator import GeminiGenerator
            generator = GeminiGenerator(client=self.generator_client)
            raw_res = generator._call_gemini(prompt)

            summary = ""
            impact = ""
            for line in raw_res.split("\n"):
                if line.lower().startswith("summary:"):
                    summary = line.split(":", 1)[1].strip()
                elif line.lower().startswith("impact:"):
                    impact = line.split(":", 1)[1].strip()

            if not summary:
                summary = raw_res.strip()
            if not impact:
                impact = f"Compliance workflows regarding {mod_cat or 'operational norms'} must be updated."

            return summary, impact
        except Exception as e:
            logger.info(f"Gemini LLM section comparison skipped ({e}). Using deterministic summary.")
            return (
                f"Requirement updated with specific revisions regarding {mod_cat or 'regulatory provisions'}.",
                f"Regulated entities must align internal compliance mechanisms with revised {mod_cat or 'standards'}."
            )

    def analyze_documents(
        self,
        current_doc: RegulatoryDocument,
        previous_doc: Optional[RegulatoryDocument] = None,
        candidate_docs: Optional[List[RegulatoryDocument]] = None
    ) -> ChangeReport:
        """
        Executes end-to-end change detection comparing current_doc against previous_doc or automatically matched predecessor.
        """
        if not current_doc:
            return ChangeReport(status="ERROR", message="Current document cannot be null.")

        # 1. Identify predecessor if not explicitly supplied
        match_confidence = None
        match_reason = None
        target_previous = previous_doc

        if target_previous is None:
            candidates = candidate_docs if candidate_docs is not None else self.load_all_documents()
            match_res: Optional[PredecessorMatch] = DocumentMatcher.find_predecessor(current_doc, candidates)

            if match_res is None:
                return ChangeReport(
                    status="NO_RELIABLE_PREDECESSOR",
                    message=f"No sufficiently reliable predecessor was identified for document '{current_doc.title}'.",
                    current_document=current_doc.model_dump()
                )

            target_previous = match_res.predecessor
            match_confidence = match_res.confidence
            match_reason = match_res.match_reason
        else:
            match_confidence = "high"
            match_reason = "Predecessor explicitly specified by user."

        # 2. Extract sections from both documents
        curr_sections = SectionComparer.extract_sections(current_doc.content, document_id=current_doc.document_id)
        prev_sections = SectionComparer.extract_sections(target_previous.content, document_id=target_previous.document_id)

        # 3. Align sections
        aligned_pairs = SectionComparer.align_sections(prev_sections, curr_sections)

        # 4. Classify each pair and summarize diffs
        changes: List[SectionChange] = []
        added_count = 0
        removed_count = 0
        modified_count = 0
        unchanged_count = 0

        for pair in aligned_pairs:
            change_type, mod_cat = SectionComparer.classify_change(pair)

            prev_text = pair.previous_section.content if pair.previous_section else ""
            curr_text = pair.current_section.content if pair.current_section else ""

            if change_type == "ADDED":
                added_count += 1
            elif change_type == "REMOVED":
                removed_count += 1
            elif change_type == "MODIFIED":
                modified_count += 1
            elif change_type == "UNCHANGED":
                unchanged_count += 1

            summary, impact = self._summarize_section_diff(
                section_title=pair.section_title,
                prev_text=prev_text,
                curr_text=curr_text,
                change_type=change_type,
                mod_cat=mod_cat
            )

            evidence_dict = {}
            if pair.previous_section:
                evidence_dict["previous_section_id"] = pair.previous_section.section_id
            if pair.current_section:
                evidence_dict["current_section_id"] = pair.current_section.section_id

            changes.append(SectionChange(
                section=pair.section_key,
                title=pair.section_title,
                change_type=change_type,  # type: ignore
                modification_category=mod_cat,
                previous_text=prev_text,
                current_text=curr_text,
                summary=summary,
                impact=impact,
                evidence=evidence_dict
            ))

        # 5. Construct Executive Summary
        exec_lines = [
            f"Regulatory Comparison between '{target_previous.title}' ({target_previous.published_date or 'Prior'}) "
            f"and '{current_doc.title}' ({current_doc.published_date or 'Current'}):",
            f"- Total Sections Compared: {len(aligned_pairs)}",
            f"- Modifications: {modified_count}",
            f"- Newly Added Sections: {added_count}",
            f"- Removed Sections: {removed_count}",
            f"- Unchanged Sections: {unchanged_count}"
        ]

        report = ChangeReport(
            status="SUCCESS",
            current_document={
                "document_id": current_doc.document_id,
                "title": current_doc.title,
                "category": current_doc.category,
                "published_date": current_doc.published_date,
                "effective_date": current_doc.effective_date,
                "url": current_doc.url
            },
            previous_document={
                "document_id": target_previous.document_id,
                "title": target_previous.title,
                "category": target_previous.category,
                "published_date": target_previous.published_date,
                "effective_date": target_previous.effective_date,
                "url": target_previous.url
            },
            relationship_confidence=match_confidence,
            match_reason=match_reason,
            executive_summary="\n".join(exec_lines),
            changes=changes,
            total_sections_compared=len(aligned_pairs),
            added_count=added_count,
            removed_count=removed_count,
            modified_count=modified_count,
            unchanged_count=unchanged_count
        )

        return report

    def analyze(self, current_doc_id: str, previous_doc_id: Optional[str] = None) -> ChangeReport:
        """Loads documents by ID and generates structured ChangeReport."""
        all_docs = self.load_all_documents()
        docs_by_id = {d.document_id: d for d in all_docs}

        if current_doc_id not in docs_by_id:
            return ChangeReport(status="ERROR", message=f"Current document ID '{current_doc_id}' not found.")

        curr_doc = docs_by_id[current_doc_id]
        prev_doc = docs_by_id.get(previous_doc_id) if previous_doc_id else None

        return self.analyze_documents(curr_doc, previous_doc=prev_doc, candidate_docs=all_docs)


def validate_change_report(report: ChangeReport) -> bool:
    """Validates structural integrity and citation mappings in ChangeReport."""
    if report.status != "SUCCESS":
        return True

    if not report.current_document or "document_id" not in report.current_document:
        return False
    if not report.previous_document or "document_id" not in report.previous_document:
        return False

    for c in report.changes:
        if c.change_type not in {"ADDED", "REMOVED", "MODIFIED", "UNCHANGED"}:
            return False
        if not c.title or not c.section:
            return False
        if c.change_type == "MODIFIED" and not c.summary:
            return False

    return True
