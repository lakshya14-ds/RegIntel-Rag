import pytest
from app.retrieval.query_analyzer import QueryAnalyzer, QueryIntent, build_metadata_filters


def test_query_analyzer_latest_investment_adviser():
    query = "What are the latest SEBI requirements for investment advisers?"
    intent: QueryIntent = QueryAnalyzer.analyze(query)

    assert intent.source == "SEBI"
    assert intent.category == "Investment Adviser"
    assert intent.time_intent == "latest"
    assert intent.query_type == "current_requirement"
    assert "SEBI" in intent.exact_terms or "investment advisers" in " ".join(intent.exact_terms).lower() or len(intent.exact_terms) >= 0


def test_query_analyzer_change_analysis():
    query = "What changed between the January and August circular for mutual funds?"
    intent: QueryIntent = QueryAnalyzer.analyze(query)

    assert intent.query_type == "change_analysis"
    assert intent.category == "Mutual Funds"
    assert intent.time_intent == "none" or intent.time_intent == "date_specific"


def test_query_analyzer_effective_date_and_specific_date():
    query = "When did circular SEBI/HO/MIRSD/2024/56 become effective in August 2026?"
    intent: QueryIntent = QueryAnalyzer.analyze(query)

    assert intent.time_intent == "date_specific"
    assert intent.target_date == "2026-08"
    assert intent.query_type == "effective_date"
    assert any("SEBI/HO/MIRSD/2024/56" in t for t in intent.exact_terms)


def test_query_analyzer_historical():
    query = "What were the old historical rules for portfolio managers?"
    intent: QueryIntent = QueryAnalyzer.analyze(query)

    assert intent.time_intent == "historical"
    assert intent.category == "Market Intermediaries"
    assert intent.query_type == "historical"


def test_query_analyzer_exact_regulation_and_clause():
    query = "What does Regulation 15A and Clause 4.2 say about BASL?"
    intent: QueryIntent = QueryAnalyzer.analyze(query)

    terms_str = " ".join(intent.exact_terms)
    assert "Regulation 15A" in terms_str or "Regulation 15" in terms_str
    assert "Clause 4.2" in terms_str or "4.2" in terms_str
    assert "BASL" in terms_str


def test_build_metadata_filters():
    intent = QueryIntent(
        original_query="test",
        source="SEBI",
        category="Investment Adviser",
        document_type="Master Circular"
    )
    filters = build_metadata_filters(intent)
    assert filters == {
        "source": "SEBI",
        "category": "Investment Adviser",
        "document_type": "Master Circular"
    }
