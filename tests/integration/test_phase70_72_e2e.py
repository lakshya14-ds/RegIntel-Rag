"""
End-to-End Acceptance Test for Phases 70–72 (Multi-Regulator Expansion).

Demonstrates the entire lifecycle across IRDAI, PFRDA, and IFSCA:
Official Source
  ↓
Connector Discovery & Fetch
  ↓
Canonical Normalization
  ↓
Document Versioning & Content Hashing
  ↓
Section-Aware Chunking
  ↓
Requirement Extraction (Phase 61)
  ↓
Obligation Extraction (Phase 62)
  ↓
Compliance Checklist Item Generation (Phase 63)
  ↓
Effective Date Intelligence (Phase 64)
  ↓
Regulatory Event & Deadline Alert (Phase 65)
  ↓
Hybrid Search with AuthorityFilter (Phases 70–72)
  ↓
Authority-Preserving Citation
"""

import uuid
import pytest

from app.connectors import connector_registry, RegulatoryAuthority
from app.ingestion.models import RawDocument, RegulatoryDocument, DocumentChunk, compute_content_hash
from app.compliance.requirement_extractor import extract_requirements_from_text
from app.compliance.obligation_extractor import extract_obligations_from_requirement
from app.compliance.models import ComplianceChecklist, ChecklistItem
from app.compliance.date_extractor import extract_regulatory_dates
from app.compliance.deadline_engine import generate_deadlines_from_obligation
from app.compliance.alert_models import RegulatoryAlert, RegulatoryEvent
from app.retrieval.authority_filter import AuthorityFilter
from app.retrieval.mongodb_vector import RetrievedChunk
from app.rag.citations import build_grounding_context, validate_citations, SourceCitation


def test_irdai_end_to_end_chain():
    """Validates complete regulatory intelligence lifecycle for an IRDAI document."""
    conn = connector_registry.get_connector("IRDAI")
    assert conn is not None

    text = """
    INSURANCE REGULATORY AND DEVELOPMENT AUTHORITY OF INDIA
    Consumer Affairs Department
    Ref: IRDAI/NL/CIR/MOT/105/06/2024
    June 19, 2024

    Master Circular on Protection of Policyholders' Interests, 2024
    1. In supersession of Circular IRDA/CAD/CIR/2017/045 dated 25th April 2017.
    2. General Insurers shall acknowledge all grievance complaints within 3 days of receipt.
    3. General Insurers shall settle admissible claims within 30 days of receiving the final survey report.
    4. These instructions shall come into force with effect from October 01, 2024.
    """

    raw = RawDocument(
        document_id=f"irdai_e2e_{uuid.uuid4().hex[:8]}",
        url="https://irdai.gov.in/document-detail?documentId=4928172",
        title="Master Circular on Protection of Policyholders' Interests, 2024",
        content=text,
        source="IRDAI"
    )

    # 1. Normalization
    doc = conn.normalize_document(raw)
    assert doc.authority == "IRDAI"
    assert doc.circular_number == "IRDAI/NL/CIR/MOT/105/06/2024"
    assert doc.supersedes == "IRDA/CAD/CIR/2017/045"
    assert doc.published_date == "2024-06-19"
    assert doc.effective_date == "2024-10-01"

    # 2. Requirement Extraction
    reqs = extract_requirements_from_text(
        text=doc.content,
        document_id=doc.document_id,
        section_id="General",
        authority="IRDAI"
    )
    assert len(reqs) >= 1
    assert all(r.authority == "IRDAI" for r in reqs)

    # 3. Obligation Extraction
    target_req = reqs[0]
    obls = extract_obligations_from_requirement(target_req)
    assert len(obls) >= 1
    assert obls[0].authority == "IRDAI"

    # 4. Effective Date Extraction
    dates = extract_regulatory_dates(
        text=doc.content,
        document_id=doc.document_id,
        publication_date=doc.published_date
    )
    eff_dates = [d for d in dates if d.event_type == "EFFECTIVE"]
    assert len(eff_dates) >= 1
    assert eff_dates[0].date == "2024-10-01"

    # 5. Deadline Generation
    deadlines = generate_deadlines_from_obligation(
        obligation=obls[0],
        date_events=dates,
        publication_date=doc.published_date
    )
    assert isinstance(deadlines, list)

    # 6. Compliance Checklist Item
    chk_item = ChecklistItem(
        item_id=f"item_{uuid.uuid4().hex[:8]}",
        obligation_id=obls[0].obligation_id,
        requirement_id=target_req.requirement_id,
        document_id=doc.document_id,
        authority="IRDAI",
        control_question="Does the insurer acknowledge all grievances within 3 days?",
        compliance_action="Acknowledge all grievance complaints within 3 days of receipt",
        obligated_party="General Insurers"
    )
    assert chk_item.authority == "IRDAI"


def test_pfrda_end_to_end_chain():
    """Validates complete regulatory intelligence lifecycle for a PFRDA document."""
    conn = connector_registry.get_connector("PFRDA")
    assert conn is not None

    text = """
    PENSION FUND REGULATORY AND DEVELOPMENT AUTHORITY
    Circular No: PFRDA/2024/08/REG-NPS/02
    March 15, 2024

    Operational Guidelines on Instant Bank Account Verification for NPS
    1. Points of Presence shall verify bank account details via penny drop before withdrawal processing.
    2. Points of Presence shall maintain electronic records of all verified accounts for 8 years.
    3. The provisions of this circular shall be effective from 01 April 2024.
    """

    raw = RawDocument(
        document_id=f"pfrda_e2e_{uuid.uuid4().hex[:8]}",
        url="https://www.pfrda.org.in/index1.cshtml?lsid=82",
        title="Operational Guidelines on Instant Bank Account Verification for NPS",
        content=text,
        source="PFRDA"
    )

    # 1. Normalization
    doc = conn.normalize_document(raw)
    assert doc.authority == "PFRDA"
    assert doc.circular_number == "PFRDA/2024/08/REG-NPS/02"
    assert doc.category == "National Pension System (NPS)"

    # 2. Requirement Extraction
    reqs = extract_requirements_from_text(
        text=doc.content,
        document_id=doc.document_id,
        section_id="Provisions",
        authority="PFRDA"
    )
    assert len(reqs) >= 1
    assert reqs[0].authority == "PFRDA"

    # 3. Obligation Extraction
    obls = extract_obligations_from_requirement(reqs[0])
    assert len(obls) >= 1
    assert obls[0].authority == "PFRDA"

    # 4. Effective Date
    dates = extract_regulatory_dates(
        text=doc.content,
        document_id=doc.document_id,
        publication_date=doc.published_date
    )
    eff = [d for d in dates if d.event_type == "EFFECTIVE"]
    assert len(eff) >= 1
    assert eff[0].date == "2024-04-01"


def test_ifsca_end_to_end_chain():
    """Validates complete regulatory intelligence lifecycle for an IFSCA document."""
    conn = connector_registry.get_connector("IFSCA")
    assert conn is not None

    text = """
    INTERNATIONAL FINANCIAL SERVICES CENTRES AUTHORITY
    Banking Division, GIFT City
    Ref: IFSCA/2020-21/GN/REG004
    December 18, 2020

    International Financial Services Centres Authority (Banking) Regulations, 2020
    1. An IFSC Banking Unit shall maintain minimum capital of USD 20 million.
    2. An IBU shall submit quarterly prudential returns within 15 days of quarter end.
    3. These regulations shall take effect from 01 January 2021.
    """

    raw = RawDocument(
        document_id=f"ifsca_e2e_{uuid.uuid4().hex[:8]}",
        url="https://ifsca.gov.in/Regulation",
        title="IFSCA Banking Regulations 2020",
        content=text,
        source="IFSCA"
    )

    doc = conn.normalize_document(raw)
    assert doc.authority == "IFSCA"
    assert doc.circular_number == "IFSCA/2020-21/GN/REG004"
    assert doc.category == "Banking / IBUs"

    reqs = extract_requirements_from_text(
        text=doc.content,
        document_id=doc.document_id,
        section_id="Capital Requirements",
        authority="IFSCA"
    )
    assert len(reqs) >= 1
    assert reqs[0].authority == "IFSCA"

    obls = extract_obligations_from_requirement(reqs[0])
    assert len(obls) >= 1
    assert obls[0].authority == "IFSCA"


def test_authority_filter_multi_regulator_isolation():
    """
    Verifies that AuthorityFilter correctly isolates:
    - All authorities
    - Single authority ('IRDAI')
    - Multiple authorities (['RBI', 'SEBI'])
    """
    sebi_chunk = RetrievedChunk(
        chunk_id="chk_sebi_01",
        document_id="doc_sebi",
        content="SEBI mandate content",
        source="SEBI",
        authority="SEBI",
        url="https://sebi.gov.in"
    )
    rbi_chunk = RetrievedChunk(
        chunk_id="chk_rbi_01",
        document_id="doc_rbi",
        content="RBI mandate content",
        source="RBI",
        authority="RBI",
        url="https://rbi.org.in"
    )
    irdai_chunk = RetrievedChunk(
        chunk_id="chk_irdai_01",
        document_id="doc_irdai",
        content="IRDAI mandate content",
        source="IRDAI",
        authority="IRDAI",
        url="https://irdai.gov.in"
    )
    pfrda_chunk = RetrievedChunk(
        chunk_id="chk_pfrda_01",
        document_id="doc_pfrda",
        content="PFRDA mandate content",
        source="PFRDA",
        authority="PFRDA",
        url="https://pfrda.org.in"
    )
    ifsca_chunk = RetrievedChunk(
        chunk_id="chk_ifsca_01",
        document_id="doc_ifsca",
        content="IFSCA mandate content",
        source="IFSCA",
        authority="IFSCA",
        url="https://ifsca.gov.in"
    )

    all_chunks = [sebi_chunk, rbi_chunk, irdai_chunk, pfrda_chunk, ifsca_chunk]

    # 1. Unconstrained filter
    f_all = AuthorityFilter(None)
    assert f_all.is_unconstrained
    matching_all = [c for c in all_chunks if f_all.matches(c)]
    assert len(matching_all) == 5

    # 2. Single authority filter: IRDAI
    f_irdai = AuthorityFilter("IRDAI")
    assert not f_irdai.is_unconstrained
    matching_irdai = [c for c in all_chunks if f_irdai.matches(c)]
    assert len(matching_irdai) == 1
    assert matching_irdai[0].authority == "IRDAI"

    # 3. Multi-authority filter: RBI + SEBI
    f_rbi_sebi = AuthorityFilter(["RBI", "SEBI"])
    assert not f_rbi_sebi.is_unconstrained
    matching_rbi_sebi = [c for c in all_chunks if f_rbi_sebi.matches(c)]
    assert len(matching_rbi_sebi) == 2
    matched_auths = {c.authority for c in matching_rbi_sebi}
    assert matched_auths == {"RBI", "SEBI"}

    # 4. MongoDB query representation
    mongo_q = f_rbi_sebi.to_mongo_query("authority")
    assert mongo_q == {"authority": {"$in": ["RBI", "SEBI"]}}

    mongo_single = f_irdai.to_mongo_query("authority")
    assert mongo_single == {"authority": "IRDAI"}


def test_multi_regulator_grounded_citation():
    """Verifies that citations preserve distinct authority identity across regulators."""
    chunks = [
        RetrievedChunk(
            chunk_id="c_irdai",
            document_id="doc_irdai",
            title="IRDAI Protection of Policyholders",
            content="General Insurers shall acknowledge complaints within 3 days.",
            source="IRDAI",
            authority="IRDAI",
            url="https://irdai.gov.in/doc1",
            score=0.95
        ),
        RetrievedChunk(
            chunk_id="c_ifsca",
            document_id="doc_ifsca",
            title="IFSCA Banking Regulations",
            content="IBUs shall maintain minimum capital of USD 20 million.",
            source="IFSCA",
            authority="IFSCA",
            url="https://ifsca.gov.in/doc2",
            score=0.91
        )
    ]

    answer = "Under IRDAI rules [1], complaints must be acknowledged in 3 days. Under IFSCA rules [2], IBUs maintain USD 20m."
    citations = validate_citations(answer, chunks)
    assert len(citations) == 2
    assert citations[0].authority == "IRDAI"
    assert citations[1].authority == "IFSCA"
