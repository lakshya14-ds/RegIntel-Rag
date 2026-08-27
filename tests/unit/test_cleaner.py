import pytest
from app.ingestion.cleaner import clean_markdown, clean_html

def test_clean_markdown_normalizes_whitespace():
    raw = "Section 1.   All  stock brokers \t\t must comply.\n\n\n\nSection 2."
    cleaned = clean_markdown(raw)
    assert "Section 1. All stock brokers must comply." in cleaned
    assert "\n\n\n\n" not in cleaned
    assert "\n\nSection 2." in cleaned

def test_clean_markdown_preserves_regulatory_clauses_and_headings():
    raw = """
# Master Circular for Investment Advisers
## Chapter I - Registration
1. Qualifications:
   (a) Candidate must have a professional degree.
   (b) Net worth requirement of INR 50 Lakhs.
    """
    cleaned = clean_markdown(raw)
    assert "# Master Circular for Investment Advisers" in cleaned
    assert "## Chapter I - Registration" in cleaned
    assert "(a) Candidate must have a professional degree." in cleaned

def test_clean_markdown_removes_boilerplate_lines():
    raw = """
Skip to main content
# SEBI Circular
Screen Reader Access
This circular applies to all AMCs.
Print this page
Share on Twitter
    """
    cleaned = clean_markdown(raw)
    assert "Skip to main content" not in cleaned
    assert "Screen Reader Access" not in cleaned
    assert "Print this page" not in cleaned
    assert "# SEBI Circular" in cleaned
    assert "This circular applies to all AMCs." in cleaned

def test_clean_html():
    html = """
    <html>
      <head><style>.nav { color: red; }</style></head>
      <body>
        <nav><a>Home</a></nav>
        <h1>Circular on FPI</h1>
        <p>Text paragraph here.</p>
        <script>console.log("ads");</script>
      </body>
    </html>
    """
    cleaned = clean_html(html)
    assert "Circular on FPI" in cleaned
    assert "Text paragraph here." in cleaned
    assert "console.log" not in cleaned
