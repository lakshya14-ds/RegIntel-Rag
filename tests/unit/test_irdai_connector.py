"""
Unit Tests for IRDAI Connector (Phase 67).

Tests:
- IRDAI reference number patterns
- Department detection (Health, Life, Non-Life)
- Document type classification (Master Circular, Regulation, Circular)
- Normalization into common model
- Domain and content quality validation
"""

import pytest
from app.connectors.irdai import IRDAIConnector
from app.ingestion.models import RawDocument


@pytest.fixture
def irdai():
    return IRDAIConnector()


def test_irdai_ref_number_extraction(irdai: IRDAIConnector):
    text = """
    INSURANCE REGULATORY AND DEVELOPMENT AUTHORITY OF INDIA
    Consumer Affairs Department, Hyderabad
    
    Ref: IRDAI/NL/CIR/MOT/105/06/2024
    Dated: June 19, 2024
    
    Master Circular on Protection of Policyholders' Interests
    All General Insurers and Standalone Health Insurers
    """
    meta = irdai.extract_metadata(text, title="Master Circular on Protection of Policyholders' Interests")
    assert meta.circular_number == "IRDAI/NL/CIR/MOT/105/06/2024"
    assert meta.authority == "IRDAI"
    assert meta.section == "Consumer Affairs Department"
    assert meta.published_date == "2024-06-19"
    assert meta.document_type == "Master Circular"


def test_irdai_health_insurance_extraction(irdai: IRDAIConnector):
    text = """
    INSURANCE REGULATORY AND DEVELOPMENT AUTHORITY OF INDIA
    Health Department
    
    Ref No: IRDAI/HLT/CIR/PRO/095/05/2024
    May 29, 2024
    
    Guidelines on Cashless Everywhere in Health Insurance
    In supersession of circular IRDAI/HLT/CIR/PRO/012/01/2021.
    """
    meta = irdai.extract_metadata(text, title="Guidelines on Cashless Everywhere in Health Insurance")
    assert meta.circular_number == "IRDAI/HLT/CIR/PRO/095/05/2024"
    assert meta.category == "Health Insurance"
    assert meta.supersedes == "IRDAI/HLT/CIR/PRO/012/01/2021"


def test_irdai_normalization(irdai: IRDAIConnector):
    raw = RawDocument(
        document_id="irdai_policyholder_2024",
        url="https://irdai.gov.in/document-detail?documentId=4928172",
        title="Master Circular on Protection of Policyholders Interests",
        content="""
        INSURANCE REGULATORY AND DEVELOPMENT AUTHORITY OF INDIA
        Ref: IRDAI/ACTL/CIR/PRO/080/04/2024
        April 15, 2024
        Insurers shall ensure settlement of death claims within 15 days of receiving all documents.
        """,
        source="IRDAI"
    )

    doc = irdai.normalize_document(raw)
    assert doc.authority == "IRDAI"
    assert doc.source == "IRDAI"
    assert doc.circular_number == "IRDAI/ACTL/CIR/PRO/080/04/2024"
    assert doc.published_date == "2024-04-15"


def test_irdai_domain_validation(irdai: IRDAIConnector):
    assert irdai.is_allowed_domain("https://irdai.gov.in/circulars") is True
    assert irdai.is_allowed_domain("https://www.irdai.gov.in/regulations") is True
    assert irdai.is_allowed_domain("https://insurance-news-daily.com/irdai") is False
