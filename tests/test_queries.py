from __future__ import annotations

from datetime import datetime, timezone

from src.ingest import persist_events
from src.queries import get_market_by_api_id, get_market_history, get_top_volume_markets, list_markets
from tests.test_normalize import sample_event_payload


def test_query_helpers_return_expected_shapes(session) -> None:
    payload = sample_event_payload()
    with session.begin():
        persist_events(session, [payload], observed_at=datetime(2026, 3, 18, tzinfo=timezone.utc))

    markets = list_markets(session)
    assert len(markets) == 1
    assert get_market_by_api_id(session, "market-1") is not None

    history = get_market_history(session, "market-1")
    assert len(history) == 1
    assert history[0].market.market_id == "market-1"

    top = get_top_volume_markets(session, limit=5)
    assert len(top) == 1
    assert top[0][0].market_id == "market-1"
