"""
Integration tests for Document Comparison and Version Lineage FastAPI Endpoints.
"""

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ingestion.models import RegulatoryDocument, DocumentMetadata
from app.config import settings

client = TestClient(app)


@pytest.fixture
def setup_api_docs(tmp_path, monkeypatch):
    doc_1 = RegulatoryDocument(
        document_id="api_comp_doc_1",
        url="https://sebi.gov.in/api_comp_doc_1.html",
        title="SEBI Investment Adviser Guidelines 2020",
        source="SEBI",
        document_type="Circular",
        category="Investment Adviser",
        circular_number="SEBI/HO/2020/01",
        published_date="2020-05-10",
        content="""# 1. Capital Requirement
Net worth must be INR 25 Lakhs.

# 2. Grievance Redressal
Resolve grievances within 30 days.
""",
        metadata=DocumentMetadata(category="Investment Adviser", circular_number="SEBI/HO/2020/01", published_date="2020-05-10")
    )

    doc_2 = RegulatoryDocument(
        document_id="api_comp_doc_2",
        url="https://sebi.gov.in/api_comp_doc_2.html",
        title="SEBI Investment Adviser Master Circular 2024",
        source="SEBI",
        document_type="Master Circular",
        category="Investment Adviser",
        circular_number="SEBI/HO/2024/05",
        published_date="2024-05-24",
        content="""# 1. Capital Requirement
Net worth must be INR 50 Lakhs.

# 2. Grievance Redressal
Resolve grievances within 21 days via SCORES portal.
""",
        metadata=DocumentMetadata(category="Investment Adviser", circular_number="SEBI/HO/2024/05", published_date="2024-05-24")
    )

    with open(tmp_path / "api_comp_doc_1.json", "w", encoding="utf-8") as f:
        json.dump(doc_1.model_dump(), f)
    with open(tmp_path / "api_comp_doc_2.json", "w", encoding="utf-8") as f:
        json.dump(doc_2.model_dump(), f)

    monkeypatch.setattr(settings, "processed_data_dir", tmp_path)
    import app.api.routes_rag as routes_rag
    monkeypatch.setattr(routes_rag, "_document_comparator", None)
    return tmp_path


def test_api_compare_documents(setup_api_docs):
    payload = {
        "document_a_id": "api_comp_doc_1",
        "document_b_id": "api_comp_doc_2"
    }

    response = client.post("/compare", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["total_changes"] == 2
    assert data["modified_count"] == 2
    assert data["older_document"]["document_id"] == "api_comp_doc_1"
    assert data["newer_document"]["document_id"] == "api_comp_doc_2"
    assert data["document_order_confidence"] == "high"
    assert len(data["changes"]) == 2

    # Check evidence source structure
    ch1 = data["changes"][0]
    assert ch1["old_source"] is not None
    assert ch1["new_source"] is not None
    assert ch1["old_source"]["document_id"] == "api_comp_doc_1"
    assert ch1["new_source"]["document_id"] == "api_comp_doc_2"


def test_api_compare_missing_document(setup_api_docs):
    payload = {
        "document_a_id": "missing_doc_123",
        "document_b_id": "api_comp_doc_2"
    }

    response = client.post("/compare", json=payload)
    assert response.status_code == 404


def test_api_get_document_versions(setup_api_docs):
    response = client.get("/document/api_comp_doc_2/versions")
    assert response.status_code == 200

    data = response.json()
    assert data["document_id"] == "api_comp_doc_2"
    assert "timeline" in data
