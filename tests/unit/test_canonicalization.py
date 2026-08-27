import pytest
from app.ingestion.models import canonicalize_url

def test_canonicalize_url_basic():
    url = "HTTP://WWW.SEBI.GOV.IN/legal/circulars/index.html"
    canon = canonicalize_url(url)
    assert canon == "http://sebi.gov.in/legal/circulars/index.html"

def test_canonicalize_url_strip_tracking_params():
    url = "https://sebi.gov.in/doc.html?utm_source=twitter&utm_medium=social&category=circulars&ref=123"
    canon = canonicalize_url(url)
    assert "utm_source" not in canon
    assert "utm_medium" not in canon
    assert "ref" not in canon
    assert "category=circulars" in canon

def test_canonicalize_url_sort_query_params():
    url1 = "https://sebi.gov.in/filter?b=2&a=1"
    url2 = "https://sebi.gov.in/filter?a=1&b=2"
    assert canonicalize_url(url1) == canonicalize_url(url2)

def test_canonicalize_url_strip_fragment_and_trailing_slash():
    url = "https://sebi.gov.in/legal/circulars/#section-1"
    assert canonicalize_url(url) == "https://sebi.gov.in/legal/circulars"

def test_canonicalize_url_empty_and_invalid():
    assert canonicalize_url("") == ""
    assert canonicalize_url(None) == ""
