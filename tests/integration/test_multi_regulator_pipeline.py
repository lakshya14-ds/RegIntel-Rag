"""
Integration Test for Multi-Regulator Intelligence Pipeline (Phases 66–69).

Validates end-to-end processing across SEBI and RBI documents:
1. Document normalization preserves authority context
2. Requirement extraction assigns authority correctly
3. Obligation extraction retains authority & deontic classification
4. Effective date & deadline calculation flow
5. Retrieval preserves distinct authority metadata for citations
"""

import uuid
import pytest
from app.connectors import connector_registry, RegulatoryAuthority
from app.ingestion.models import RawDocument, RegulatoryDocument, DocumentChunk
from app.compliance.requirement_extractor import extract_requirements_from_text
from app.compliance.obligation_extractor import extract_obligations_from_requirement
from app.compliance.date_extractor import extract_regulatory_dates
from app.compliance.deadline_engine import generate_deadlines_from_obligation
from app.retrieval.mongodb_vector import RetrievedChunk
from app.rag.citations import build_grounding_context


def test_rbi_end_to_end_compliance_flow():
    """Verifies that an RBI document flows cleanly through requirements, obligations, and deadlines."""
    rbi_conn = connector_registry.get_connector("RBI")
    assert rbi_conn is not None

    rbi_text = """
    RESERVE BANK OF INDIA
    Department of Regulation
    RBI/2023-24/105
    August 18, 2023

    Fair Lending Practice - Penal Charges in Loan Accounts
    1. Regulated Entities (REs) shall not introduce any additional component to the rate of interest.
    2. Penal charges, if levied, shall be clearly disclosed to the borrower in the loan agreement.
    3. The instructions shall come into force with effect from January 1, 2024.
    4. REs shall submit a board-approved policy on penal charges within 90 days.
    """

    raw_doc = RawDocument(
        document_id=f"rbi_test_{uuid.uuid4().hex[:8]}",
        url="https://rbi.org.in/Scripts/NotificationUser.aspx?Id=99999",
        title="Fair Lending Practice - Penal Charges",
        content=rbi_text,
        source="RBI"
    )

    # 1. Normalization
    reg_doc = rbi_conn.normalize_document(raw_doc)
    assert reg_doc.authority == "RBI"
    assert reg_doc.circular_number == "RBI/2023-24/105"
    assert reg_doc.published_date == "2023-08-18"

    # 2. Requirement Extraction
    reqs = extract_requirements_from_text(
        text=reg_doc.content,
        document_id=reg_doc.document_id,
        section_id="General",
        authority="RBI"
    )
    assert len(reqs) >= 1
    for r in reqs:
        assert r.authority == "RBI"
        assert r.document_id == reg_doc.document_id

    # 3. Obligation Extraction
    target_req = reqs[0]
    obls = extract_obligations_from_requirement(target_req)
    assert len(obls) >= 1
    for obl in obls:
        assert obl.authority == "RBI"
        assert obl.requirement_id == target_req.requirement_id

    # 4. Effective Date Extraction
    date_events = extract_regulatory_dates(
        text=reg_doc.content,
        document_id=reg_doc.document_id,
        publication_date=reg_doc.published_date
    )
    assert len(date_events) >= 1
    effective_events = [e for e in date_events if e.event_type == "EFFECTIVE"]
    assert len(effective_events) >= 1
    assert effective_events[0].date == "2024-01-01"

    # 5. Deadline Generation
    deadlines = generate_deadlines_from_obligation(
        obligation=obls[0],
        date_events=date_events,
        publication_date=reg_doc.published_date
    )
    assert isinstance(deadlines, list)


def test_cross_regulator_citation_isolation():
    """Verifies that retrieval results from SEBI and RBI maintain authority isolation."""
    sebi_chunk = RetrievedChunk(
        chunk_id="sebi_chunk_01",
        document_id="sebi_ia_circ_2024",
        title="SEBI Master Circular for Investment Advisers",
        content="Investment Advisers shall maintain client agreements for 8 years.",
        score=0.92,
        source="SEBI",
        published_date="2024-05-24",
        url="https://sebi.gov.in/circ/ia2024.html"
    )

    rbi_chunk = RetrievedChunk(
        chunk_id="rbi_chunk_01",
        document_id="rbi_kyc_2023",
        title="RBI Master Direction - Know Your Customer",
        content="Regulated entities shall preserve KYC records for at least 5 years after the business relationship ends.",
        score=0.88,
        source="RBI",
        published_date="2023-04-01",
        url="https://rbi.org.in/md/kyc2023.html"
    )

    # Build grounding context
    evidence_text, valid_indices = build_grounding_context([sebi_chunk, rbi_chunk])
    assert "[1]" in evidence_text
    assert "[2]" in evidence_text
    assert "SEBI" in evidence_text
    assert "RBI" in evidence_text
    assert valid_indices == [1, 2]
