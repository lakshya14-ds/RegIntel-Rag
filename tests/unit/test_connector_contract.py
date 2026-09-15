"""
Connector Contract Verification Tests (Phases 66–69).

Verifies that all registered connectors (SEBI, RBI, IRDAI, PFRDA, IFSCA)
strictly conform to the RegulatoryConnector specification and shared behaviors.
"""

import pytest
from app.connectors import (
    RegulatoryAuthority,
    RegulatoryConnector,
    connector_registry,
    source_registry,
    list_authorities
)
from app.ingestion.models import RawDocument, RegulatoryDocument, DocumentMetadata


@pytest.mark.parametrize("authority_code", ["SEBI", "RBI", "IRDAI", "PFRDA", "IFSCA"])
def test_connector_registration(authority_code: str):
    """Verifies that all 5 authorities have a registered connector."""
    connector = connector_registry.get_connector(authority_code)
    assert connector is not None, f"Connector for {authority_code} must be registered in ConnectorRegistry"
    assert isinstance(connector, RegulatoryConnector)
    assert connector.authority.value == authority_code


@pytest.mark.parametrize("authority_code", ["SEBI", "RBI", "IRDAI", "PFRDA", "IFSCA"])
def test_connector_allowed_domains(authority_code: str):
    """Verifies that each connector enforces official domains."""
    connector = connector_registry.get_connector(authority_code)
    assert len(connector.allowed_domains) > 0, f"Connector for {authority_code} must declare allowed domains"
    
    # Valid domain should pass
    valid_url = f"https://{connector.allowed_domains[0]}/notice/123"
    assert connector.is_allowed_domain(valid_url) is True

    # External domain must be rejected
    invalid_url = "https://unauthorized-external-blog.com/leak/circular.pdf"
    assert connector.is_allowed_domain(invalid_url) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("authority_code", ["SEBI", "RBI", "IRDAI", "PFRDA", "IFSCA"])
async def test_connector_sources_discovery(authority_code: str):
    """Verifies that each connector discovers registered official sources."""
    connector = connector_registry.get_connector(authority_code)
    sources = await connector.discover_sources()
    assert isinstance(sources, list)
    assert len(sources) >= 1, f"Connector for {authority_code} should have at least 1 registered official source"
    for s in sources:
        assert s.authority.value == authority_code
        assert s.listing_url.startswith("https://")


@pytest.mark.asyncio
@pytest.mark.parametrize("authority_code", ["SEBI", "RBI", "IRDAI", "PFRDA", "IFSCA"])
async def test_connector_document_discovery(authority_code: str):
    """Verifies that each connector discovers candidate documents with required schema."""
    connector = connector_registry.get_connector(authority_code)
    candidates = await connector.discover_documents(limit=3)
    assert isinstance(candidates, list)
    assert len(candidates) >= 1, f"Connector for {authority_code} must discover candidates"
    
    for c in candidates:
        assert "url" in c
        assert "authority" in c
        assert c["authority"] == authority_code


@pytest.mark.parametrize("authority_code", ["SEBI", "RBI", "IRDAI", "PFRDA", "IFSCA"])
def test_connector_metadata_extraction_contract(authority_code: str):
    """Verifies that metadata extraction returns a valid DocumentMetadata model with authority."""
    connector = connector_registry.get_connector(authority_code)
    sample_text = f"Official regulatory announcement issued by {authority_code}. All regulated entities shall comply."
    meta = connector.extract_metadata(text=sample_text, title=f"Test {authority_code} Circular", url=f"https://{connector.allowed_domains[0]}/test")
    assert isinstance(meta, DocumentMetadata)
    assert meta.authority == authority_code


@pytest.mark.parametrize("authority_code", ["SEBI", "RBI", "IRDAI", "PFRDA", "IFSCA"])
def test_connector_normalization_contract(authority_code: str):
    """Verifies that raw document normalization produces a valid RegulatoryDocument with proper authority."""
    connector = connector_registry.get_connector(authority_code)
    raw_doc = RawDocument(
        document_id=f"test_{authority_code.lower()}_001",
        url=f"https://{connector.allowed_domains[0]}/document_001.html",
        title=f"Master Direction for {authority_code} Compliance",
        content=f"Substantive regulatory text of {authority_code}. All entities shall submit compliance certificates within 30 days.",
        source=authority_code
    )

    reg_doc = connector.normalize_document(raw_doc)
    assert isinstance(reg_doc, RegulatoryDocument)
    assert reg_doc.authority == authority_code
    assert reg_doc.source == authority_code
    assert reg_doc.document_id == raw_doc.document_id
    assert reg_doc.content_hash is not None
    assert len(reg_doc.content_hash) == 64
