"""
Unit tests for Deterministic Comparison Cache.
"""

import json
import pytest
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.change_detection.document_comparator import DocumentComparator, ComparisonCache


def test_comparison_cache_hit_and_invalidation(tmp_path):
    doc_a = RegulatoryDocument(
        document_id="cache_doc_a",
        url="https://sebi.gov.in/doc_a.html",
        title="Circular A",
        source="SEBI",
        content="""# 1. Eligibility
Requirements are strict.
""",
        published_date="2021-01-01",
        metadata=DocumentMetadata(category="Investment Adviser", published_date="2021-01-01")
    )

    doc_b = RegulatoryDocument(
        document_id="cache_doc_b",
        url="https://sebi.gov.in/doc_b.html",
        title="Circular B",
        source="SEBI",
        content="""# 1. Eligibility
Requirements are revised.
""",
        published_date="2022-01-01",
        metadata=DocumentMetadata(category="Investment Adviser", published_date="2022-01-01")
    )

    # Save to disk
    with open(tmp_path / "cache_doc_a.json", "w", encoding="utf-8") as f:
        json.dump(doc_a.model_dump(), f)
    with open(tmp_path / "cache_doc_b.json", "w", encoding="utf-8") as f:
        json.dump(doc_b.model_dump(), f)

    cache = ComparisonCache()
    comparator = DocumentComparator(processed_data_dir=tmp_path, cache=cache)

    # 1. First execution -> Cache Miss
    report_1 = comparator.compare_documents("cache_doc_a", "cache_doc_b", generate_summaries=False)
    assert report_1.status == "SUCCESS"
    assert report_1.cached is False

    # 2. Second execution with identical documents -> Cache Hit
    report_2 = comparator.compare_documents("cache_doc_a", "cache_doc_b", generate_summaries=False)
    assert report_2.status == "SUCCESS"
    assert report_2.cached is True

    # 3. Modify content of Doc B -> Content Hash Changes -> Cache Miss
    doc_b.content = """# 1. Eligibility
Requirements are updated once again with new thresholds.
"""
    with open(tmp_path / "cache_doc_b.json", "w", encoding="utf-8") as f:
        json.dump(doc_b.model_dump(), f)

    report_3 = comparator.compare_documents("cache_doc_a", "cache_doc_b", generate_summaries=False)
    assert report_3.status == "SUCCESS"
    assert report_3.cached is False
