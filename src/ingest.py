from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session, sessionmaker

from src.api_client import PolymarketClient
from src.db import SessionLocal
from src.integrity import (
    run_post_write_checks,
    validate_market_bundle,
    validate_normalized_event,
)
from src.logging_config import configure_logging
from src.models import Event, EventTag, Market, MarketOutcome, MarketSnapshot, Tag
from src.normalize import normalize_event
from src.run_tracking import create_run, update_run
from src.signals import generate_signals_for_snapshots


logger = logging.getLogger(__name__)


@dataclass
class IngestionCycleSummary:
    trigger_mode: str
    run_started_at: datetime
    run_finished_at: datetime | None = None
    run_id: int | None = None
    status: str = "running"
    records_fetched: int = 0
    events_upserted: int = 0
    markets_upserted: int = 0
    snapshots_inserted: int = 0
    records_skipped: int = 0
    integrity_errors: int = 0
    duration_ms: int | None = None
    error_message: str | None = None
    signals_generated: int = 0
    signals_skipped: int = 0
    record_errors: list[str] = field(default_factory=list)
    integrity_messages: list[str] = field(default_factory=list)
    signal_messages: list[str] = field(default_factory=list)
    signal_type_counts: dict[str, int] = field(default_factory=dict)
    touched_snapshot_ids: set[int] = field(default_factory=set, repr=False)

    def finish(self, *, status: str, error_message: str | None = None) -> None:
        self.status = status
        self.error_message = error_message
        self.run_finished_at = datetime.now(timezone.utc)
        self.duration_ms = int(
            (self.run_finished_at - self.run_started_at).total_seconds() * 1000
        )
        self.integrity_errors = len(self.integrity_messages)

    def to_cli_summary(self) -> str:
        return (
            f"run_id={self.run_id} status={self.status} fetched={self.records_fetched} "
            f"events_upserted={self.events_upserted} markets_upserted={self.markets_upserted} "
            f"snapshots_inserted={self.snapshots_inserted} records_skipped={self.records_skipped} "
            f"integrity_errors={self.integrity_errors} signals_generated={self.signals_generated} "
            f"signals_skipped={self.signals_skipped} duration_ms={self.duration_ms}"
        )


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
        key: value
        for key, value in values.items()
        if key not in conflict_columns and key != "inserted_at"
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


def insert_snapshot(session: Session, market: Market, snapshot_data: dict[str, Any]) -> tuple[MarketSnapshot, bool]:
    before_snapshot = session.execute(
        select(MarketSnapshot).where(MarketSnapshot.snapshot_key == snapshot_data["snapshot_key"])
    ).scalar_one_or_none()
    payload = dict(snapshot_data)
    payload["market_id"] = market.id
    _upsert(session, MarketSnapshot, payload, ["snapshot_key"])
    snapshot = session.execute(
        select(MarketSnapshot).where(MarketSnapshot.snapshot_key == snapshot_data["snapshot_key"])
    ).scalar_one()
    return snapshot, before_snapshot is None


def _log_record_issue(summary: IngestionCycleSummary, message: str) -> None:
    summary.record_errors.append(message)
    logger.warning(message)


def _skip_record(summary: IngestionCycleSummary, messages: Iterable[str]) -> None:
    summary.records_skipped += 1
    for message in messages:
        _log_record_issue(summary, message)


def persist_events(
    session: Session,
    event_payloads: Iterable[dict[str, Any]],
    *,
    summary: IngestionCycleSummary | None = None,
    observed_at: datetime | None = None,
) -> None:
    observed = observed_at or datetime.now(timezone.utc)
    active_summary = summary or IngestionCycleSummary(
        trigger_mode="manual",
        run_started_at=observed,
    )

    for raw_event in event_payloads:
        try:
            normalized = normalize_event(raw_event, observed)
        except ValueError as exc:
            _skip_record(active_summary, [str(exc)])
            continue

        for market_error in normalized.get("market_errors", []):
            _skip_record(active_summary, [market_error])

        event_issues = validate_normalized_event(normalized)
        if event_issues:
            _skip_record(active_summary, event_issues)
            continue

        event = upsert_event(session, normalized["event"])
        session.flush()
        ensure_event_tags(session, event, normalized["tags"])
        active_summary.events_upserted += 1

        for market_bundle in normalized["markets"]:
            market_issues = validate_market_bundle(market_bundle)
            if market_issues:
                _skip_record(active_summary, market_issues)
                continue

            market = upsert_market(session, event, market_bundle["market"])
            session.flush()
            upsert_market_outcomes(session, market, market_bundle["outcomes"])
            snapshot, inserted = insert_snapshot(session, market, market_bundle["snapshot"])
            active_summary.touched_snapshot_ids.add(snapshot.id)
            if inserted:
                active_summary.snapshots_inserted += 1
            active_summary.markets_upserted += 1


def execute_ingestion_cycle(
    *,
    trigger_mode: str = "manual",
    scheduler_job_id: str | None = None,
    limit: int | None = None,
    client: PolymarketClient | None = None,
    session_factory: sessionmaker = SessionLocal,
    raise_on_failure: bool = False,
) -> IngestionCycleSummary:
    started_at = datetime.now(timezone.utc)
    summary = IngestionCycleSummary(trigger_mode=trigger_mode, run_started_at=started_at)
    run = create_run(
        session_factory,
        trigger_mode=trigger_mode,
        run_started_at=started_at,
        scheduler_job_id=scheduler_job_id,
    )
    summary.run_id = run.id
    api_client = client or PolymarketClient()

    logger.info(
        "Ingestion run started.",
        extra={"context": {"run_id": summary.run_id, "trigger_mode": trigger_mode}},
    )

    try:
        event_payloads = api_client.fetch_events(limit=limit)
        summary.records_fetched = len(event_payloads)
        logger.info(
            "Fetched event payloads.",
            extra={"context": {"run_id": summary.run_id, "records_fetched": summary.records_fetched}},
        )

        with session_factory() as session:
            with session.begin():
                persist_events(
                    session,
                    event_payloads,
                    summary=summary,
                    observed_at=started_at,
                )

        with session_factory() as session:
            summary.integrity_messages = run_post_write_checks(
                session,
                records_fetched=summary.records_fetched,
                events_upserted=summary.events_upserted,
            )
        logger.info(
            "Integrity checks completed.",
            extra={
                "context": {
                    "run_id": summary.run_id,
                    "integrity_errors": len(summary.integrity_messages),
                }
            },
        )

        if summary.integrity_messages:
            raise RuntimeError("; ".join(summary.integrity_messages))

        with session_factory() as session:
            with session.begin():
                signal_result = generate_signals_for_snapshots(session, summary.touched_snapshot_ids)
        summary.signals_generated = signal_result.generated_count
        summary.signals_skipped = signal_result.skipped_count
        summary.signal_type_counts = signal_result.signal_type_counts
        logger.info(
            "Signal generation completed.",
            extra={
                "context": {
                    "run_id": summary.run_id,
                    "signals_generated": summary.signals_generated,
                    "signals_skipped": summary.signals_skipped,
                    "signal_types": summary.signal_type_counts,
                }
            },
        )

        summary.finish(status="success")
        update_run(
            session_factory,
            summary.run_id,
            run_finished_at=summary.run_finished_at,
            status=summary.status,
            records_fetched=summary.records_fetched,
            events_upserted=summary.events_upserted,
            markets_upserted=summary.markets_upserted,
            snapshots_inserted=summary.snapshots_inserted,
            records_skipped=summary.records_skipped,
            integrity_errors=summary.integrity_errors,
            duration_ms=summary.duration_ms,
            error_message=None,
        )
        logger.info(
            "Ingestion run succeeded.",
            extra={
                "context": {
                    "run_id": summary.run_id,
                    "duration_ms": summary.duration_ms,
                    "events_upserted": summary.events_upserted,
                    "markets_upserted": summary.markets_upserted,
                    "snapshots_inserted": summary.snapshots_inserted,
                    "records_skipped": summary.records_skipped,
                    "signals_generated": summary.signals_generated,
                }
            },
        )
        return summary
    except Exception as exc:
        summary.finish(status="failed", error_message=str(exc))
        update_run(
            session_factory,
            summary.run_id,
            run_finished_at=summary.run_finished_at,
            status=summary.status,
            records_fetched=summary.records_fetched,
            events_upserted=summary.events_upserted,
            markets_upserted=summary.markets_upserted,
            snapshots_inserted=summary.snapshots_inserted,
            records_skipped=summary.records_skipped,
            integrity_errors=summary.integrity_errors,
            duration_ms=summary.duration_ms,
            error_message=summary.error_message,
        )
        logger.exception(
            "Ingestion run failed.",
            extra={"context": {"run_id": summary.run_id, "trigger_mode": trigger_mode}},
        )
        if raise_on_failure:
            raise
        return summary


def run_ingestion(limit: int | None = None) -> dict[str, int | str | None]:
    summary = execute_ingestion_cycle(trigger_mode="manual", limit=limit)
    return {
        "status": summary.status,
        "records_fetched": summary.records_fetched,
        "events_upserted": summary.events_upserted,
        "markets_upserted": summary.markets_upserted,
        "snapshots_inserted": summary.snapshots_inserted,
        "records_skipped": summary.records_skipped,
        "integrity_errors": summary.integrity_errors,
        "signals_generated": summary.signals_generated,
        "run_id": summary.run_id,
    }


def main() -> None:
    configure_logging()
    summary = execute_ingestion_cycle(trigger_mode="manual", raise_on_failure=False)
    print(summary.to_cli_summary())
    if summary.status != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
