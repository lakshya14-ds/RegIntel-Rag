"""
Document Comparison Service and CLI for Direct Regulatory Document Diffing.

Compares two explicitly supplied regulatory documents (Document A and Document B)
by aligning sections, classifying deltas (ADDED, REMOVED, MODIFIED, UNCHANGED),
and generating a grounded evidence-backed change report.
"""

import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from app.config import settings
from app.ingestion.models import RegulatoryDocument, from_mongo
from app.change_detection.detector import RegulatoryChangeDetector, ChangeReport, validate_change_report

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class DocumentComparator:
    """
    Service for direct, deterministic comparison between two specific regulatory documents.
    """

    def __init__(self, processed_data_dir: Optional[Path] = None, generator_client: Optional[Any] = None):
        self.processed_dir = processed_data_dir or settings.processed_data_dir
        self.detector = RegulatoryChangeDetector(processed_data_dir=self.processed_dir, generator_client=generator_client)

    def load_document(self, document_id: str) -> Optional[RegulatoryDocument]:
        """Loads a single processed regulatory document by its SHA-256 document_id."""
        if not document_id or not document_id.strip():
            return None

        clean_id = document_id.strip()
        doc_path = self.processed_dir / f"{clean_id}.json"
        if not doc_path.exists():
            # Try searching all json files in processed directory
            for f in self.processed_dir.glob("*.json"):
                if f.name.endswith("_chunks.json"):
                    continue
                try:
                    with open(f, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                    if data.get("document_id") == clean_id:
                        return from_mongo(RegulatoryDocument, data)
                except Exception:
                    continue
            return None

        try:
            with open(doc_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return from_mongo(RegulatoryDocument, data)
        except Exception as e:
            logger.error(f"Failed to load document {document_id}: {e}")
            return None

    def compare_documents(
        self,
        document_a_id: str,
        document_b_id: str
    ) -> ChangeReport:
        """
        Compares Document A (treated as previous/baseline) and Document B (treated as current/revised).
        Returns a structured ChangeReport.
        """
        if not document_a_id or not document_b_id:
            return ChangeReport(
                status="ERROR",
                message="Both document_a_id and document_b_id must be provided."
            )

        doc_a = self.load_document(document_a_id)
        if not doc_a:
            return ChangeReport(
                status="ERROR",
                message=f"Document A with ID '{document_a_id}' was not found in the corpus."
            )

        doc_b = self.load_document(document_b_id)
        if not doc_b:
            return ChangeReport(
                status="ERROR",
                message=f"Document B with ID '{document_b_id}' was not found in the corpus."
            )

        # Check content presence
        if not doc_a.content or not doc_a.content.strip():
            return ChangeReport(status="ERROR", message=f"Document A ('{doc_a.title}') has no usable content.")
        if not doc_b.content or not doc_b.content.strip():
            return ChangeReport(status="ERROR", message=f"Document B ('{doc_b.title}') has no usable content.")

        # Re-use detector: doc_b is current, doc_a is previous
        report: ChangeReport = self.detector.analyze_documents(
            current_doc=doc_b,
            previous_doc=doc_a
        )

        return report

    def compare(self, doc_a_id: str, doc_b_id: str, generate_summaries: bool = True) -> Dict[str, Any]:
        """Convenience method returning dictionary or raising error on missing docs."""
        report = self.compare_documents(doc_a_id, doc_b_id)
        if report.status == "ERROR":
            raise FileNotFoundError(report.message)
        return report.model_dump()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Direct Regulatory Document Comparison CLI.")
    parser.add_argument("--document-a", type=str, required=True, help="Baseline Document ID (Document A / Previous)")
    parser.add_argument("--document-b", type=str, required=True, help="Revised Document ID (Document B / Current)")
    args = parser.parse_args()

    comparator = DocumentComparator()
    report = comparator.compare_documents(args.document_a, args.document_b)
    report.print_formatted()


if __name__ == "__main__":
    main()
