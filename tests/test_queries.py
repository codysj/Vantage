from __future__ import annotations

from datetime import datetime, timezone

from decimal import Decimal

from src.models import IngestionRun, Signal
from src.ingest import persist_events
from src.queries import (
    get_market_by_api_id,
    get_market_history,
    get_recent_ingestion_runs,
    get_recent_signals,
    get_top_volume_markets,
    list_markets,
)
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


def test_recent_ingestion_runs_are_returned_descending(session) -> None:
    session.add_all(
        [
            IngestionRun(
                run_started_at=datetime(2026, 3, 18, 1, tzinfo=timezone.utc),
                status="success",
                trigger_mode="manual",
                api_source="gamma_events",
            ),
            IngestionRun(
                run_started_at=datetime(2026, 3, 18, 2, tzinfo=timezone.utc),
                status="failed",
                trigger_mode="scheduled",
                api_source="gamma_events",
            ),
        ]
    )
    session.commit()

    runs = get_recent_ingestion_runs(session, limit=2)

    assert [run.status for run in runs] == ["failed", "success"]


def test_recent_signals_filtering(session) -> None:
    payload = sample_event_payload()
    with session.begin():
        persist_events(session, [payload], observed_at=datetime(2026, 3, 18, tzinfo=timezone.utc))

    market = get_market_by_api_id(session, "market-1")
    snapshot = get_market_history(session, "market-1")[0]
    session.add(
        Signal(
            market_id=market.id,
            event_id=market.event_id,
            snapshot_id=snapshot.id,
            signal_type="price_movement",
            signal_strength=Decimal("0.20"),
            metadata_json={"summary": "Price moved"},
            detected_at=snapshot.observed_at,
        )
    )
    session.commit()

    rows = get_recent_signals(session, limit=10, signal_type="price_movement", market_id="market-1")

    assert len(rows) == 1
    assert rows[0][0].signal_type == "price_movement"
