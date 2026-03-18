from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from src.api_client import PolymarketClient
from src.db import SessionLocal
from src.models import Event, EventTag, Market, MarketOutcome, MarketSnapshot, Tag
from src.normalize import normalize_event


logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _upsert(session: Session, model: Any, values: dict[str, Any], conflict_columns: list[str]) -> None:
    dialect_name = session.bind.dialect.name
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    elif dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:
        dialect_insert = insert

    insert_stmt = dialect_insert(model).values(**values)
    update_columns = {
        key: value for key, value in values.items() if key not in conflict_columns and key != "inserted_at"
    }
    if update_columns:
        statement = insert_stmt.on_conflict_do_update(
            index_elements=conflict_columns, set_=update_columns
        )
    else:
        statement = insert_stmt.on_conflict_do_nothing(index_elements=conflict_columns)
    session.execute(statement)


def upsert_event(session: Session, event_data: dict[str, Any]) -> Event:
    _upsert(session, Event, event_data, ["event_id"])
    return session.execute(select(Event).where(Event.event_id == event_data["event_id"])).scalar_one()


def upsert_market(session: Session, event: Event, market_data: dict[str, Any]) -> Market:
    payload = dict(market_data)
    payload["event_id"] = event.id
    payload.pop("event_api_id", None)
    _upsert(session, Market, payload, ["market_id"])
    return session.execute(select(Market).where(Market.market_id == market_data["market_id"])).scalar_one()


def upsert_market_outcomes(
    session: Session, market: Market, outcomes: Iterable[dict[str, Any]]
) -> None:
    for outcome in outcomes:
        payload = dict(outcome)
        payload["market_id"] = market.id
        _upsert(session, MarketOutcome, payload, ["market_id", "outcome_index"])


def upsert_tag(session: Session, tag_data: dict[str, Any]) -> Tag:
    _upsert(session, Tag, tag_data, ["tag_key"])
    return session.execute(select(Tag).where(Tag.tag_key == tag_data["tag_key"])).scalar_one()


def ensure_event_tags(session: Session, event: Event, tag_rows: Iterable[dict[str, Any]]) -> None:
    for tag_row in tag_rows:
        tag = upsert_tag(session, tag_row)
        join_row = {"event_id": event.id, "tag_id": tag.id}
        _upsert(session, EventTag, join_row, ["event_id", "tag_id"])


def insert_snapshot(session: Session, market: Market, snapshot_data: dict[str, Any]) -> bool:
    before_count = session.execute(
        select(MarketSnapshot).where(MarketSnapshot.snapshot_key == snapshot_data["snapshot_key"])
    ).scalar_one_or_none()
    payload = dict(snapshot_data)
    payload["market_id"] = market.id
    _upsert(session, MarketSnapshot, payload, ["snapshot_key"])
    return before_count is None


def persist_events(
    session: Session, event_payloads: Iterable[dict[str, Any]], observed_at: datetime | None = None
) -> dict[str, int]:
    observed = observed_at or datetime.now(timezone.utc)
    counts = {
        "events_processed": 0,
        "markets_processed": 0,
        "snapshots_inserted": 0,
    }

    for raw_event in event_payloads:
        normalized = normalize_event(raw_event, observed)
        event = upsert_event(session, normalized["event"])
        session.flush()
        ensure_event_tags(session, event, normalized["tags"])

        counts["events_processed"] += 1
        for market_bundle in normalized["markets"]:
            market = upsert_market(session, event, market_bundle["market"])
            session.flush()
            upsert_market_outcomes(session, market, market_bundle["outcomes"])
            if insert_snapshot(session, market, market_bundle["snapshot"]):
                counts["snapshots_inserted"] += 1
            counts["markets_processed"] += 1

    return counts


def run_ingestion(limit: int | None = None) -> dict[str, int]:
    client = PolymarketClient()
    observed_at = datetime.now(timezone.utc)
    event_payloads = client.fetch_events(limit=limit)
    with SessionLocal() as session:
        with session.begin():
            counts = persist_events(session, event_payloads, observed_at=observed_at)
    logger.info("Ingestion complete: %s", counts)
    return counts


def main() -> None:
    configure_logging()
    counts = run_ingestion()
    print(counts)


if __name__ == "__main__":
    main()
