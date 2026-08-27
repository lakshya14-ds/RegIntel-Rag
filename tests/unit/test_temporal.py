import pytest
from app.retrieval.mongodb_vector import RetrievedChunk
from app.retrieval.query_analyzer import QueryIntent
from app.retrieval.temporal import TemporalRanker, parse_date_safe, apply_temporal_ranking


@pytest.fixture
def mock_temporal_chunks():
    return [
        RetrievedChunk(
            chunk_id="chk_old",
            document_id="doc_2021",
            title="SEBI Circular 2021",
            content="Old regulation content.",
            source="SEBI",
            published_date="2021-06-28",
            url="https://sebi.gov.in/2021.html",
            score=0.85
        ),
        RetrievedChunk(
            chunk_id="chk_new",
            document_id="doc_2024",
            title="SEBI Master Circular 2024",
            content="New regulation content.",
            source="SEBI",
            published_date="2024-05-24",
            url="https://sebi.gov.in/2024.html",
            score=0.82
        )
    ]


def test_parse_date_safe():
    assert str(parse_date_safe("2024-05-24")) == "2024-05-24"
    assert str(parse_date_safe("2026-08")) == "2026-08-01"
    assert parse_date_safe("invalid-date") is None
    assert parse_date_safe(None) is None


def test_temporal_ranker_latest_boosts_recent_document(mock_temporal_chunks):
    ranker = TemporalRanker(boost_weight=0.10)
    intent = QueryIntent(original_query="latest circular", time_intent="latest")

    ranked = ranker.apply_temporal_ranking(intent, mock_temporal_chunks)

    # Newer 2024 document should receive higher boost and outrank older 2021 document
    assert ranked[0].chunk_id == "chk_new"
    assert ranked[0].score > mock_temporal_chunks[1].score


def test_temporal_ranker_irrelevant_recent_does_not_overwhelm_highly_relevant_old():
    # If old chunk has very high relevance (0.95) and new chunk has low relevance (0.40)
    old_relevant = RetrievedChunk(
        chunk_id="chk_old_rel",
        document_id="doc_old",
        title="Old Highly Relevant Document",
        content="Exact answer to user question.",
        source="SEBI",
        published_date="2021-01-01",
        url="https://sebi.gov.in/old.html",
        score=0.95
    )
    new_irrelevant = RetrievedChunk(
        chunk_id="chk_new_irrel",
        document_id="doc_new",
        title="New Irrelevant Document",
        content="Unrelated news.",
        source="SEBI",
        published_date="2026-08-26",
        url="https://sebi.gov.in/new.html",
        score=0.40
    )

    ranker = TemporalRanker(boost_weight=0.10)
    intent = QueryIntent(original_query="latest rules", time_intent="latest")

    ranked = ranker.apply_temporal_ranking(intent, [old_relevant, new_irrelevant])
    # The 0.95 relevant document remains on top (0.95 vs 0.40 + 0.10 = 0.50)
    assert ranked[0].chunk_id == "chk_old_rel"


def test_temporal_ranker_date_specific(mock_temporal_chunks):
    ranker = TemporalRanker(boost_weight=0.10)
    intent = QueryIntent(original_query="circular in 2021", time_intent="date_specific", target_date="2021")

    ranked = ranker.apply_temporal_ranking(intent, mock_temporal_chunks)
    assert ranked[0].chunk_id == "chk_old"
    assert ranked[0].score == 0.95
