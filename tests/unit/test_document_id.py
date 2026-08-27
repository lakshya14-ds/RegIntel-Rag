import pytest
from app.ingestion.models import generate_document_id

def test_deterministic_document_id():
    url1 = "https://www.sebi.gov.in/legal/circulars/doc1.html?utm_source=news"
    url2 = "https://sebi.gov.in/legal/circulars/doc1.html"
    
    id1 = generate_document_id(source="SEBI", url=url1)
    id2 = generate_document_id(source="SEBI", url=url2)
    
    assert id1 == id2
    assert len(id1) == 64  # SHA-256 length

def test_document_id_different_sources():
    url = "https://sebi.gov.in/legal/circulars/doc1.html"
    id_sebi = generate_document_id(source="SEBI", url=url)
    id_mc = generate_document_id(source="Moneycontrol", url=url)
    
    assert id_sebi != id_mc
