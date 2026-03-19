from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.ingest import execute_ingestion_cycle, persist_events
from src.models import Event, Market, MarketSnapshot, Signal
from src.queries import get_recent_signals
from src.signals import (
    LIQUIDITY_SHIFT,
    PRICE_MOVEMENT,
    VOLUME_SPIKE,
    compute_signals_for_snapshot,
    generate_signals_for_snapshots,
)
from tests.test_ingest import StubClient
from tests.test_normalize import sample_event_payload


def build_snapshot(
    snapshot_id: int,
    observed_at: datetime,
    *,
    price: str | None,
    volume: str | None,
    liquidity: str | None,
) -> MarketSnapshot:
    return MarketSnapshot(
        id=snapshot_id,
        market_id=1,
        observed_at=observed_at,
        snapshot_key=f"snapshot-{snapshot_id}",
        last_trade_price=Decimal(price) if price is not None else None,
        volume=Decimal(volume) if volume is not None else None,
        liquidity=Decimal(liquidity) if liquidity is not None else None,
    )


def build_market() -> Market:
    return Market(id=1, event_id=1, market_id="market-1", question="Test market")


def test_price_movement_signal_triggers() -> None:
    now = datetime.now(timezone.utc)
    market = build_market()
    history = [
        build_snapshot(1, now - timedelta(minutes=20), price="0.40", volume="100", liquidity="20"),
        build_snapshot(2, now, price="0.50", volume="110", liquidity="20"),
    ]

    candidates, skipped = compute_signals_for_snapshot(market, history[-1], history)

    assert skipped >= 0
    assert any(candidate.signal_type == PRICE_MOVEMENT for candidate in candidates)


def test_small_price_change_does_not_trigger() -> None:
    now = datetime.now(timezone.utc)
    market = build_market()
    history = [
        build_snapshot(1, now - timedelta(minutes=20), price="0.40", volume="100", liquidity="20"),
        build_snapshot(2, now, price="0.42", volume="110", liquidity="21"),
    ]

    candidates, _ = compute_signals_for_snapshot(market, history[-1], history)

    assert all(candidate.signal_type != PRICE_MOVEMENT for candidate in candidates)


def test_volume_spike_and_liquidity_shift_trigger() -> None:
    now = datetime.now(timezone.utc)
    market = build_market()
    history = [
        build_snapshot(1, now - timedelta(minutes=20), price="0.40", volume="100", liquidity="20"),
        build_snapshot(2, now - timedelta(minutes=10), price="0.41", volume="110", liquidity="20"),
        build_snapshot(3, now, price="0.42", volume="400", liquidity="30"),
    ]

    candidates, _ = compute_signals_for_snapshot(market, history[-1], history)
    signal_types = {candidate.signal_type for candidate in candidates}

    assert VOLUME_SPIKE in signal_types
    assert LIQUIDITY_SHIFT in signal_types


def test_no_prior_snapshots_or_missing_values_skip_cleanly() -> None:
    now = datetime.now(timezone.utc)
    market = build_market()
    history = [build_snapshot(1, now, price=None, volume="0", liquidity=None)]

    candidates, skipped = compute_signals_for_snapshot(market, history[-1], history)

    assert candidates == []
    assert skipped == 1


def test_signal_rows_insert_and_duplicates_are_prevented(session) -> None:
    event = Event(event_id="event-1", title="Event")
    market = Market(market_id="market-1", event=event, question="Question")
    session.add_all([event, market])
    session.flush()

    older = MarketSnapshot(
        market_id=market.id,
        observed_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        snapshot_key="old",
        last_trade_price=Decimal("0.40"),
        volume=Decimal("100"),
        liquidity=Decimal("20"),
    )
    latest = MarketSnapshot(
        market_id=market.id,
        observed_at=datetime.now(timezone.utc),
        snapshot_key="new",
        last_trade_price=Decimal("0.60"),
        volume=Decimal("400"),
        liquidity=Decimal("30"),
    )
    session.add_all([older, latest])
    session.commit()

    with session.begin():
        first = generate_signals_for_snapshots(session, {latest.id})
    with session.begin():
        second = generate_signals_for_snapshots(session, {latest.id})

    assert first.generated_count >= 1
    assert second.generated_count == 0
    assert session.query(Signal).count() >= 1


def test_recent_signals_query_returns_descending(session) -> None:
    event = Event(event_id="event-1", title="Event")
    market = Market(market_id="market-1", event=event, question="Question")
    session.add_all([event, market])
    session.flush()

    older = MarketSnapshot(
        market_id=market.id,
        observed_at=datetime(2026, 3, 18, 1, tzinfo=timezone.utc),
        snapshot_key="old",
    )
    latest = MarketSnapshot(
        market_id=market.id,
        observed_at=datetime(2026, 3, 18, 2, tzinfo=timezone.utc),
        snapshot_key="new",
    )
    session.add_all([older, latest])
    session.flush()
    session.add_all(
        [
            Signal(
                market_id=market.id,
                event_id=event.id,
                snapshot_id=older.id,
                signal_type=PRICE_MOVEMENT,
                signal_strength=Decimal("0.20"),
                metadata_json={"summary": "Older"},
                detected_at=older.observed_at,
            ),
            Signal(
                market_id=market.id,
                event_id=event.id,
                snapshot_id=latest.id,
                signal_type=VOLUME_SPIKE,
                signal_strength=Decimal("4.00"),
                metadata_json={"summary": "Latest"},
                detected_at=latest.observed_at,
            ),
        ]
    )
    session.commit()

    rows = get_recent_signals(session, limit=10)

    assert [row[0].signal_type for row in rows] == [VOLUME_SPIKE, PRICE_MOVEMENT]


def test_execute_ingestion_cycle_generates_signals(session_factory) -> None:
    baseline_payload = sample_event_payload()
    baseline_payload["markets"][0]["lastTradePrice"] = "0.40"
    baseline_payload["markets"][0]["volume"] = "100"
    baseline_payload["markets"][0]["liquidity"] = "20"

    changed_payload = sample_event_payload()
    changed_payload["markets"][0]["updatedAt"] = "2026-03-03T15:30:00Z"
    changed_payload["markets"][0]["lastTradePrice"] = "0.60"
    changed_payload["markets"][0]["volume"] = "400"
    changed_payload["markets"][0]["liquidity"] = "30"

    with session_factory() as session:
        with session.begin():
            persist_events(session, [baseline_payload], observed_at=datetime.now(timezone.utc))

    summary = execute_ingestion_cycle(
        client=StubClient([changed_payload]),
        session_factory=session_factory,
        trigger_mode="manual",
    )

    assert summary.status == "success"
    assert summary.signals_generated >= 1
    with session_factory() as session:
        assert session.query(Signal).count() >= 1
