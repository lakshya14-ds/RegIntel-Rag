"""
Unit Tests for PFRDA Connector (Phase 68).

Tests:
- PFRDA reference number patterns
- Department & category detection (NPS, APY)
- Document type classification
- Normalization into common model
- Domain validation
"""

import pytest
from app.connectors.pfrda import PFRDAConnector
from app.ingestion.models import RawDocument


@pytest.fixture
def pfrda():
    return PFRDAConnector()


def test_pfrda_ref_number_extraction(pfrda: PFRDAConnector):
    text = """
    PENSION FUND REGULATORY AND DEVELOPMENT AUTHORITY
    B-14/A, Qutab Institutional Area, New Delhi
    
    Circular No: PFRDA/2024/05/REG-CIR/02
    Date: May 10, 2024
    
    To All Points of Presence (PoPs) and Central Recordkeeping Agencies (CRAs)
    
    Master Circular on National Pension System (NPS) Intermediaries
    """
    meta = pfrda.extract_metadata(text, title="Master Circular on National Pension System Intermediaries")
    assert meta.circular_number == "PFRDA/2024/05/REG-CIR/02"
    assert meta.authority == "PFRDA"
    assert meta.document_type == "Master Circular"
    assert meta.category in ["National Pension System", "National Pension System (NPS)"]
    assert meta.published_date == "2024-05-10"


def test_pfrda_normalization(pfrda: PFRDAConnector):
    raw = RawDocument(
        document_id="pfrda_pop_guidelines_2023",
        url="https://pfrda.org.in/myauth/admin/showimg.cshtml?ID=2650",
        title="Operational Guidelines for Point of Presence under NPS",
        content="""
        PENSION FUND REGULATORY AND DEVELOPMENT AUTHORITY
        Circular No: PFRDA/CIR/2023/15
        October 12, 2023
        PoPs shall process subscriber onboarding within T+1 working days.
        """,
        source="PFRDA"
    )

    doc = pfrda.normalize_document(raw)
    assert doc.authority == "PFRDA"
    assert doc.source == "PFRDA"
    assert doc.circular_number == "PFRDA/CIR/2023/15"
    assert doc.published_date == "2023-10-12"


def test_pfrda_domain_validation(pfrda: PFRDAConnector):
    assert pfrda.is_allowed_domain("https://www.pfrda.org.in/index1.cshtml?lsid=82") is True
    assert pfrda.is_allowed_domain("https://pfrda.org.in/circulars") is True
    assert pfrda.is_allowed_domain("https://pension-advisory-india.com") is False
