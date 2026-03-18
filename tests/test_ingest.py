from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from src.ingest import persist_events
from src.models import Event, Market, MarketOutcome, MarketSnapshot
from tests.test_normalize import sample_event_payload


def test_event_market_and_snapshot_deduplicate(session) -> None:
    payload = sample_event_payload()
    observed_at = datetime(2026, 3, 18, tzinfo=timezone.utc)

    with session.begin():
        persist_events(session, [payload], observed_at=observed_at)
    with session.begin():
        persist_events(session, [payload], observed_at=observed_at)

    assert session.scalar(select(func.count()).select_from(Event)) == 1
    assert session.scalar(select(func.count()).select_from(Market)) == 1
    assert session.scalar(select(func.count()).select_from(MarketOutcome)) == 2
    assert session.scalar(select(func.count()).select_from(MarketSnapshot)) == 1


def test_new_dynamic_state_creates_new_snapshot(session) -> None:
    payload = sample_event_payload()
    changed_payload = sample_event_payload()
    changed_payload["markets"][0]["updatedAt"] = "2026-03-03T15:30:00Z"
    changed_payload["markets"][0]["volume"] = "120.5"

    with session.begin():
        persist_events(session, [payload], observed_at=datetime(2026, 3, 18, tzinfo=timezone.utc))
    with session.begin():
        persist_events(session, [changed_payload], observed_at=datetime(2026, 3, 19, tzinfo=timezone.utc))

    assert session.scalar(select(func.count()).select_from(MarketSnapshot)) == 2
