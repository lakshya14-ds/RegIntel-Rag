"""
Unit tests for Regulatory Watchlists (Phase 65.9).
"""

import pytest
from app.compliance.alert_models import Watchlist, RegulatoryDeadline
from app.compliance.temporal_models import RegulatoryDateEvent
from app.compliance.alert_engine import get_alert_engine
from app.compliance.repository import get_compliance_repository

repo = get_compliance_repository()
engine = get_alert_engine()


def test_watchlist_filtering():
    # User only watches doc_watched
    watchlist = Watchlist(
        watchlist_id="wtch_test_01",
        name="IA Watchlist",
        document_ids=["doc_watched"],
        is_active=True
    )
    repo.save_watchlist(watchlist)

    retrieved = repo.get_watchlist_by_id("wtch_test_01")
    assert retrieved is not None
    assert retrieved.name == "IA Watchlist"

    # Evaluate events: one matches, one does not
    ev_watched = RegulatoryDateEvent(
        event_id="rde_w1",
        document_id="doc_watched",
        event_type="EFFECTIVE",
        date="2026-09-20",
        source_text="effective 20 September 2026"
    )
    ev_unwatched = RegulatoryDateEvent(
        event_id="rde_w2",
        document_id="doc_unwatched",
        event_type="EFFECTIVE",
        date="2026-09-20",
        source_text="effective 20 September 2026"
    )

    alerts = engine.evaluate_upcoming_effective_dates(
        date_events=[ev_watched, ev_unwatched],
        as_of_date="2026-09-15",
        watchlist=watchlist
    )

    # Only doc_watched should generate an alert!
    assert len(alerts) == 1
    assert alerts[0].document_id == "doc_watched"
