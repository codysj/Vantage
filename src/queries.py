from __future__ import annotations

import argparse
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from src.db import SessionLocal
from src.models import Event, IngestionRun, Market, MarketSnapshot


def list_markets(session: Session) -> list[Market]:
    stmt = select(Market).order_by(Market.slug.is_(None), Market.slug, Market.market_id)
    return list(session.execute(stmt).scalars().all())


def get_market_by_api_id(session: Session, market_id: str) -> Market | None:
    stmt = select(Market).where(Market.market_id == market_id)
    return session.execute(stmt).scalar_one_or_none()


def get_market_by_slug(session: Session, slug: str) -> Market | None:
    stmt = select(Market).where(Market.slug == slug)
    return session.execute(stmt).scalar_one_or_none()


def get_market_history(session: Session, market_id: str) -> list[MarketSnapshot]:
    stmt = (
        select(MarketSnapshot)
        .join(Market)
        .where(Market.market_id == market_id)
        .order_by(MarketSnapshot.observed_at.asc())
    )
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


if __name__ == "__main__":
    main()
