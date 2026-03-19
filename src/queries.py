from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from src.db import SessionLocal
from src.models import Event, IngestionRun, Market, MarketOutcome, MarketSnapshot, Signal


def list_markets(session: Session) -> list[Market]:
    stmt = select(Market).order_by(Market.slug.is_(None), Market.slug, Market.market_id)
    return list(session.execute(stmt).scalars().all())


def get_markets_for_api(
    session: Session,
    *,
    limit: int = 20,
    offset: int = 0,
    slug: str | None = None,
    active: bool | None = None,
    closed: bool | None = None,
    q: str | None = None,
) -> list[tuple[Market, MarketSnapshot | None]]:
    latest_snapshot_subquery = (
        select(
            MarketSnapshot.market_id.label("market_id"),
            func.max(MarketSnapshot.observed_at).label("max_observed_at"),
        )
        .group_by(MarketSnapshot.market_id)
        .subquery()
    )
    stmt = (
        select(Market, MarketSnapshot)
        .outerjoin(latest_snapshot_subquery, latest_snapshot_subquery.c.market_id == Market.id)
        .outerjoin(
            MarketSnapshot,
            (MarketSnapshot.market_id == latest_snapshot_subquery.c.market_id)
            & (MarketSnapshot.observed_at == latest_snapshot_subquery.c.max_observed_at),
        )
        .join(Event, Market.event_id == Event.id)
    )
    if slug:
        stmt = stmt.where(Market.slug == slug)
    if active is not None:
        stmt = stmt.where(Market.active == active)
    if closed is not None:
        stmt = stmt.where(Market.closed == closed)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Market.slug.ilike(pattern),
                Market.question.ilike(pattern),
                Event.title.ilike(pattern),
                Event.question.ilike(pattern),
            )
        )
    stmt = stmt.order_by(Market.slug.is_(None), Market.slug, Market.market_id).limit(limit).offset(offset)
    return list(session.execute(stmt).all())


def get_market_by_api_id(session: Session, market_id: str) -> Market | None:
    stmt = select(Market).where(Market.market_id == market_id)
    return session.execute(stmt).scalar_one_or_none()


def get_market_detail_for_api(
    session: Session, market_id: str
) -> tuple[Market, Event, MarketSnapshot | None, list[MarketOutcome]] | None:
    market = session.execute(
        select(Market)
        .options(joinedload(Market.event), joinedload(Market.outcomes))
        .where(Market.market_id == market_id)
    ).unique().scalar_one_or_none()
    if market is None:
        return None
    latest_snapshot = session.execute(
        select(MarketSnapshot)
        .where(MarketSnapshot.market_id == market.id)
        .order_by(MarketSnapshot.observed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return market, market.event, latest_snapshot, list(market.outcomes)


def get_market_by_slug(session: Session, slug: str) -> Market | None:
    stmt = select(Market).where(Market.slug == slug)
    return session.execute(stmt).scalar_one_or_none()


def get_market_history(
    session: Session,
    market_id: str,
    *,
    limit: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[MarketSnapshot]:
    stmt = select(MarketSnapshot).join(Market).where(Market.market_id == market_id)
    if start_time is not None:
        stmt = stmt.where(MarketSnapshot.observed_at >= start_time)
    if end_time is not None:
        stmt = stmt.where(MarketSnapshot.observed_at <= end_time)
    stmt = stmt.order_by(MarketSnapshot.observed_at.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars().all())


def get_top_volume_markets(session: Session, limit: int = 10) -> list[tuple[Market, Decimal | None]]:
    latest_snapshot_subquery = (
        select(
            MarketSnapshot.market_id,
            func.max(MarketSnapshot.observed_at).label("max_observed_at"),
        )
        .group_by(MarketSnapshot.market_id)
        .subquery()
    )
    stmt = (
        select(Market, MarketSnapshot.volume)
        .join(latest_snapshot_subquery, latest_snapshot_subquery.c.market_id == Market.id)
        .join(
            MarketSnapshot,
            (MarketSnapshot.market_id == latest_snapshot_subquery.c.market_id)
            & (MarketSnapshot.observed_at == latest_snapshot_subquery.c.max_observed_at),
        )
        .order_by(desc(MarketSnapshot.volume))
        .limit(limit)
    )
    return list(session.execute(stmt).all())


def get_events_with_markets(session: Session) -> list[Event]:
    stmt = select(Event).options(joinedload(Event.markets)).order_by(
        Event.start_date.is_(None), Event.start_date.desc()
    )
    return list(session.execute(stmt).scalars().unique().all())


def get_recent_ingestion_runs(session: Session, limit: int = 10) -> list[IngestionRun]:
    stmt = select(IngestionRun).order_by(IngestionRun.run_started_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def get_ingestion_run_by_id(session: Session, run_id: int) -> IngestionRun | None:
    return session.get(IngestionRun, run_id)


def get_recent_signals(
    session: Session,
    limit: int = 10,
    signal_type: str | None = None,
    market_id: str | None = None,
) -> list[tuple[Signal, Market]]:
    stmt = select(Signal, Market).join(Market, Signal.market_id == Market.id)
    if signal_type:
        stmt = stmt.where(Signal.signal_type == signal_type)
    if market_id:
        stmt = stmt.where(Market.market_id == market_id)
    stmt = stmt.order_by(Signal.detected_at.desc()).limit(limit)
    return list(session.execute(stmt).all())


def get_market_signals(
    session: Session,
    market_id: str,
    *,
    limit: int = 10,
) -> list[tuple[Signal, Market]]:
    return get_recent_signals(session, limit=limit, market_id=market_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query stored Information Edge market data.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-markets")

    market_parser = subparsers.add_parser("market")
    market_parser.add_argument("--market-id")
    market_parser.add_argument("--slug")

    history_parser = subparsers.add_parser("history")
    history_parser.add_argument("--market-id", required=True)

    top_parser = subparsers.add_parser("top-volume")
    top_parser.add_argument("--limit", type=int, default=10)

    subparsers.add_parser("events")
    runs_parser = subparsers.add_parser("runs")
    runs_parser.add_argument("--limit", type=int, default=10)
    signals_parser = subparsers.add_parser("signals")
    signals_parser.add_argument("--limit", type=int, default=10)
    signals_parser.add_argument("--signal-type")
    signals_parser.add_argument("--market-id")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    with SessionLocal() as session:
        if args.command == "list-markets":
            for market in list_markets(session):
                print(f"{market.market_id}\t{market.slug}\t{market.question}")
        elif args.command == "market":
            market = None
            if args.market_id:
                market = get_market_by_api_id(session, args.market_id)
            elif args.slug:
                market = get_market_by_slug(session, args.slug)
            print(market)
        elif args.command == "history":
            for snapshot in get_market_history(session, args.market_id):
                print(
                    snapshot.observed_at.isoformat(),
                    snapshot.last_trade_price,
                    snapshot.volume,
                    snapshot.liquidity,
                )
        elif args.command == "top-volume":
            for market, volume in get_top_volume_markets(session, limit=args.limit):
                print(f"{market.market_id}\t{market.slug}\t{volume}")
        elif args.command == "events":
            for event in get_events_with_markets(session):
                print(f"{event.event_id}\t{event.title}\tmarkets={len(event.markets)}")
        elif args.command == "runs":
            for run in get_recent_ingestion_runs(session, limit=args.limit):
                print(
                    f"{run.id}\t{run.status}\t{run.trigger_mode}\t"
                    f"{run.run_started_at.isoformat()}\t{run.records_fetched}\t"
                    f"{run.snapshots_inserted}"
                )
        elif args.command == "signals":
            for signal, market in get_recent_signals(
                session,
                limit=args.limit,
                signal_type=args.signal_type,
                market_id=args.market_id,
            ):
                summary = signal.metadata_json.get("summary", "")
                print(
                    f"{signal.detected_at.isoformat()}\t{market.market_id}\t"
                    f"{signal.signal_type}\t{signal.signal_strength}\t{summary}"
                )


if __name__ == "__main__":
    main()
