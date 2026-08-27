import pytest
from app.ingestion.metadata import MetadataExtractor, parse_to_iso_date

def test_parse_to_iso_date():
    assert parse_to_iso_date("2024-05-24") == "2024-05-24"
    assert parse_to_iso_date("24-05-2024") == "2024-05-24"
    assert parse_to_iso_date("May 24, 2024") == "2024-05-24"
    assert parse_to_iso_date("24th May 2024") == "2024-05-24"
    assert parse_to_iso_date("invalid_date") is None

def test_extract_circular_number():
    text = "Circular Ref: SEBI/HO/IMD/DF2/CIR/P/2021/024 dated March 15, 2021"
    circular_no = MetadataExtractor.extract_circular_number(text)
    assert circular_no == "SEBI/HO/IMD/DF2/CIR/P/2021/024"

def test_extract_dates_published_and_effective():
    text = """
    CIRCULAR
    SEBI/HO/MIRSD/2024/10
    Dated: January 16, 2024
    
    1. All registered market intermediaries shall ensure compliance.
    2. These provisions shall come into force on April 01, 2024.
    """
    pub_date, eff_date = MetadataExtractor.extract_dates(text)
    assert pub_date == "2024-01-16"
    assert eff_date == "2024-04-01"

def test_extract_document_type():
    assert MetadataExtractor.extract_document_type("Master Circular for Mutual Funds") == "Master Circular"
    assert MetadataExtractor.extract_document_type("Consultation Paper on IA Regulations") == "Consultation Paper"
    assert MetadataExtractor.extract_document_type("Circular on T+1 Settlement") == "Circular"

def test_extract_category():
    assert MetadataExtractor.extract_category("Master Circular for Investment Advisers (IAs)") == "Investment Adviser"
    assert MetadataExtractor.extract_category("Framework for Mutual Funds overseas investment") == "Mutual Funds"
    assert MetadataExtractor.extract_category("Standard Operating Procedure for Stock Brokers") == "Market Intermediaries"
    assert MetadataExtractor.extract_category("LODR Regulations Compliance for Listed Entities") == "Securities Markets"
    assert MetadataExtractor.extract_category("General Greeting or Unrelated Notice") is None

def test_no_hallucinated_metadata():
    text = "A simple general notice without dates or numbers."
    meta = MetadataExtractor.extract(text=text, title="Notice")
    assert meta.circular_number is None
    assert meta.published_date is None
    assert meta.effective_date is None
