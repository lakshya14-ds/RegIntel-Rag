"""
Unit Tests for IFSCA Connector (Phase 69).

Tests:
- IFSCA reference number standards
- Division classification (Banking, FinTech, Fund Management)
- Document type classification (Regulation, Framework, Circular)
- Normalization into common model
- Domain validation
"""

import pytest
from app.connectors.ifsca import IFSCAConnector
from app.ingestion.models import RawDocument


@pytest.fixture
def ifsca():
    return IFSCAConnector()


def test_ifsca_ref_number_extraction(ifsca: IFSCAConnector):
    text = """
    INTERNATIONAL FINANCIAL SERVICES CENTRES AUTHORITY
    GIFT City, Gandhinagar, Gujarat
    
    Notification No. IFSCA/2020-21/GN/REG004
    November 20, 2020
    
    International Financial Services Centres Authority (Banking) Regulations, 2020
    In exercise of the powers conferred by the IFSCA Act, 2019.
    """
    meta = ifsca.extract_metadata(text, title="International Financial Services Centres Authority (Banking) Regulations, 2020")
    assert meta.circular_number == "IFSCA/2020-21/GN/REG004"
    assert meta.authority == "IFSCA"
    assert meta.document_type == "Regulation"
    assert meta.published_date == "2020-11-20"
    assert meta.category in ["Banking in IFSC", "Banking / IBUs"]


def test_ifsca_fintech_framework_extraction(ifsca: IFSCAConnector):
    text = """
    INTERNATIONAL FINANCIAL SERVICES CENTRES AUTHORITY
    Fintech Division
    
    Ref: IFSCA/2022-23/GN/GL001
    April 27, 2022
    
    Framework for FinTech Entity in the International Financial Services Centres (IFSCs)
    """
    meta = ifsca.extract_metadata(text, title="Framework for FinTech Entity in the IFSCs")
    assert meta.circular_number == "IFSCA/2022-23/GN/GL001"
    assert meta.authority == "IFSCA"
    assert meta.document_type == "Framework"
    assert meta.section == "Fintech Division"
    assert meta.category in ["FinTech", "FinTech / Regulatory Sandbox"]


def test_ifsca_normalization(ifsca: IFSCAConnector):
    raw = RawDocument(
        document_id="ifsca_fund_mgmt_2022",
        url="https://ifsca.gov.in/Document/Legal/fund-management-regulations-2022.pdf",
        title="IFSCA (Fund Management) Regulations, 2022",
        content="""
        INTERNATIONAL FINANCIAL SERVICES CENTRES AUTHORITY
        Notification No. IFSCA/2022-23/GN/REG024
        April 19, 2022
        A Fund Management Entity shall register with the Authority before commencing operations.
        """,
        source="IFSCA"
    )

    doc = ifsca.normalize_document(raw)
    assert doc.authority == "IFSCA"
    assert doc.source == "IFSCA"
    assert doc.circular_number == "IFSCA/2022-23/GN/REG024"
    assert doc.published_date == "2022-04-19"


def test_ifsca_domain_validation(ifsca: IFSCAConnector):
    assert ifsca.is_allowed_domain("https://ifsca.gov.in/Circular") is True
    assert ifsca.is_allowed_domain("https://www.ifsca.gov.in/Regulation") is True
    assert ifsca.is_allowed_domain("https://gift-city-times.com/ifsca") is False
