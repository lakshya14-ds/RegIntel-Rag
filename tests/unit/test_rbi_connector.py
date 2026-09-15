"""
Unit Tests for RBI Connector (Phase 66).

Tests:
- RBI reference number extraction patterns
- Department detection (Department of Regulation, DPSS, FMRD)
- Document type classification (Master Direction, Master Circular, Notification, Circular)
- Publication date parsing
- Relationship detection (supersedes, amends, references)
- Document normalization
- Reject invalid domains & bad content
"""

import pytest
from app.connectors.rbi import RBIConnector
from app.connectors.authority import RegulatoryAuthority
from app.ingestion.models import RawDocument


@pytest.fixture
def rbi():
    return RBIConnector()


def test_rbi_ref_number_extraction(rbi: RBIConnector):
    text = """
    RESERVE BANK OF INDIA
    Department of Regulation, Central Office, Mumbai
    
    RBI/2023-24/105
    DOR.STR.REC.45/21.04.048/2023-24
    
    August 18, 2023
    
    To All Commercial Banks (including Small Finance Banks, Local Area Banks and Regional Rural Banks)
    
    Fair Lending Practice - Penal Charges in Loan Accounts
    """
    meta = rbi.extract_metadata(text, title="Fair Lending Practice", url="https://rbi.org.in/notice/123")
    assert meta.circular_number == "RBI/2023-24/105"
    assert meta.authority == "RBI"
    assert meta.section == "Department of Regulation"
    assert meta.published_date == "2023-08-18"
    assert meta.category == "Banking Regulation"


def test_rbi_dpss_digital_payment_extraction(rbi: RBIConnector):
    text = """
    RESERVE BANK OF INDIA
    Department of Payment and Settlement Systems
    
    RBI/2020-21/74
    DPSS.CO.OD.No.1934/06.08.005/2019-20
    
    February 18, 2021
    
    Master Direction on Digital Payment Security Controls
    """
    meta = rbi.extract_metadata(text, title="Master Direction on Digital Payment Security Controls")
    assert meta.document_type == "Master Direction"
    assert meta.circular_number == "RBI/2020-21/74"
    assert meta.section == "Department of Payment and Settlement Systems"
    assert meta.published_date == "2021-02-18"
    assert meta.category == "Payment & Settlement Systems"


def test_rbi_relationship_extraction(rbi: RBIConnector):
    text = """
    RESERVE BANK OF INDIA
    Department of Regulation
    
    RBI/2023-24/80
    September 15, 2023
    
    These instructions are issued in supersession of circular RBI/2020-21/45 dated July 1, 2020.
    Further, this circular amends DOR.No.BP.BC.23/21.04.018/2021-22.
    Please refer to circular RBI/2018-19/12 on prudential norms.
    """
    meta = rbi.extract_metadata(text)
    assert meta.supersedes == "RBI/2020-21/45"
    assert meta.amends == "DOR.No.BP.BC.23/21.04.018/2021-22"
    assert "RBI/2018-19/12" in meta.references


def test_rbi_normalization(rbi: RBIConnector):
    raw = RawDocument(
        document_id="rbi_fair_lending_2023",
        url="https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12530",
        title="Fair Lending Practice - Penal Charges in Loan Accounts",
        content="""
        RESERVE BANK OF INDIA
        Department of Regulation
        RBI/2023-24/53
        August 18, 2023
        
        Banks shall ensure that penal charges are not treated as penal interest.
        All regulated entities shall formulate board-approved policies within 90 days.
        """,
        source="RBI"
    )

    doc = rbi.normalize_document(raw)
    assert doc.authority == "RBI"
    assert doc.source == "RBI"
    assert doc.circular_number == "RBI/2023-24/53"
    assert doc.published_date == "2023-08-18"
    assert doc.document_type in ["Circular", "Notification"]


def test_rbi_reject_unauthorized_domain(rbi: RBIConnector):
    assert rbi.is_allowed_domain("https://www.rbi.org.in/Scripts/NotificationUser.aspx") is True
    assert rbi.is_allowed_domain("https://rbi.org.in/notifications") is True
    assert rbi.is_allowed_domain("https://financial-blog.com/rbi-update.html") is False
    assert rbi.is_allowed_domain("https://phishing-rbi.org/notice") is False


def test_rbi_content_validation(rbi: RBIConnector):
    valid, _ = rbi.validate_content("Short")
    assert valid is False

    valid, err = rbi.validate_content("<html><body>403 Forbidden Access Denied to resource</body></html>" + " " * 50)
    assert valid is False
    assert "Access Denied" in err

    valid, err = rbi.validate_content("This is a valid official circular text from the Reserve Bank of India with sufficient length and compliance instructions.")
    assert valid is True
    assert err is None
