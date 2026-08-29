"""
Demonstration script for Direct Regulatory Document Comparison (Phases 39–41).

Executes live comparison between two SEBI circulars:
1. Displays document chronology, version relationship, and confidence ratings
2. Performs 4-tier structural alignment (Section Number > Heading > Fuzzy > Content)
3. Classifies deltas into ADDED, REMOVED, MODIFIED, and UNCHANGED
4. Displays side-by-side texts and grounded evidence references
5. Demonstrates deterministic cache hit on repeated execution
"""

import os
import sys
import json
import logging

# Ensure root directory is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.change_detection.document_comparator import DocumentComparator, ComparisonReport


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    print("\n" + "=" * 80)
    print("REGINTEL RAG — DIRECT REGULATORY DOCUMENT COMPARISON DEMONSTRATION")
    print("=" * 80)

    comparator = DocumentComparator()

    # Document pair: SEBI Investment Adviser 2020 vs Master Circular 2024
    doc_a_id = "af3f1df2c9ef7ec51afee6cbde3331b18925c8c801b1c3c6a17924d7ee5df8ab"
    doc_b_id = "69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8"

    print(f"\n[1/3] Executing Initial Direct Comparison between Document A and Document B...")
    print(f"Document A: {doc_a_id[:16]}...")
    print(f"Document B: {doc_b_id[:16]}...")

    report_1 = comparator.compare_documents(doc_a_id, doc_b_id, generate_summaries=True)

    if report_1.status == "ERROR":
        print(f"Comparison Error: {report_1.message}")
        return

    report_1.print_formatted()

    print("\n[2/3] Demonstrating Deterministic Comparison Cache...")
    print("Re-running identical comparison query...")
    report_2 = comparator.compare_documents(doc_a_id, doc_b_id, generate_summaries=True)
    print(f"Cache Status on Second Execution: {'CACHE HIT (Instant In-Memory)' if report_2.cached else 'CACHE MISS'}")
    assert report_2.cached is True, "Expected second run to be a cache hit!"

    print("\n[3/3] Sample Detailed Delta Inspection:")
    for ch in report_1.changes:
        if ch.change_type in ("MODIFIED", "ADDED", "REMOVED"):
            print(f"• Section: {ch.section} - {ch.heading} [{ch.change_type}]")
            print(f"  Summary: {ch.summary}")
            if ch.impact:
                print(f"  Impact : {ch.impact}")
            if ch.old_source:
                print(f"  Older Evidence : Doc ID {ch.old_source.document_id[:12]} | Section: {ch.old_source.heading}")
            if ch.new_source:
                print(f"  Newer Evidence : Doc ID {ch.new_source.document_id[:12]} | Section: {ch.new_source.heading}")
            print()

    print("=" * 80)
    print("DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
