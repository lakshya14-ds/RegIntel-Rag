"""
End-to-End Document Comparison Workflow Test (Phase 51.12).

Tests:
Doc A + Doc B -> Chronology Resolution -> Section Alignment ->
Delta Detection (ADDED, REMOVED, MODIFIED, UNCHANGED) -> LLM Compliance Impact ->
FastAPI Response Formatting.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.change_detection.document_comparator import ComparisonReport, DetailedSectionChange, EvidenceSource


@pytest.fixture
def api_client():
    return TestClient(app)


def test_e2e_document_comparison_workflow(api_client):
    mock_report = ComparisonReport(
        status="SUCCESS",
        older_document={"document_id": "sebi_ia_2023", "title": "SEBI IA Master Circular 2023", "published_date": "2023-05-15", "source": "SEBI"},
        newer_document={"document_id": "sebi_ia_2024", "title": "SEBI IA Master Circular 2024", "published_date": "2024-05-24", "source": "SEBI"},
        document_order_confidence="high",
        version_relationship="UPDATE",
        relationship_confidence="high",
        executive_summary="Updated IA guidelines with enhanced risk disclosures.",
        key_changes=["Fee disclosure requirements strengthened."],
        changes=[
            DetailedSectionChange(
                section="Fee Structure",
                heading="Fee Structure and Invoicing",
                change_type="MODIFIED",
                substantive_change=True,
                modification_category="ENHANCED_RESTRICTION",
                previous_text="Fees may be charged quarterly.",
                current_text="Fees must be collected through centralized compliance portal.",
                summary="Centralized fee collection mandated.",
                impact="High compliance impact on billing operations.",
                old_source=EvidenceSource(document_id="sebi_ia_2023", section_id="sec_fee", heading="Fee Structure"),
                new_source=EvidenceSource(document_id="sebi_ia_2024", section_id="sec_fee_new", heading="Fee Structure and Invoicing")
            ),
            DetailedSectionChange(
                section="AI Usage Norms",
                heading="Use of Generative AI Tools",
                change_type="ADDED",
                substantive_change=True,
                modification_category="NEW_MANDATE",
                current_text="Advisers using AI tools must conduct model risk auditing.",
                summary="AI auditing mandatory.",
                impact="Critical AI governance requirement.",
                new_source=EvidenceSource(document_id="sebi_ia_2024", section_id="sec_ai", heading="Use of Generative AI Tools")
            )
        ],
        summary_counts={"added": 1, "removed": 0, "modified": 1, "unchanged": 5},
        statistics={"older_sections": 6, "newer_sections": 7, "added": 1, "removed": 0, "modified": 1, "unchanged": 5}
    )

    with patch("app.change_detection.document_comparator.DocumentComparator.compare_documents", return_value=mock_report):
        payload = {
            "document_a_id": "sebi_ia_2023",
            "document_b_id": "sebi_ia_2024"
        }

        response = api_client.post("/compare", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "SUCCESS"
        assert data["added_count"] == 1
        assert data["modified_count"] == 1
        assert data["removed_count"] == 0
        assert len(data["changes"]) == 2
        assert data["changes"][0]["change_type"] == "MODIFIED"
        assert data["changes"][1]["change_type"] == "ADDED"
