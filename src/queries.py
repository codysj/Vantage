from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, desc, func, literal, or_, select
from sqlalchemy.orm import Session, joinedload

from src.db import SessionLocal
from src.models import (
    Event,
    EventTag,
    IngestionRun,
    Market,
    MarketOutcome,
    MarketSnapshot,
    Signal,
    Tag,
    Trade,
    WhaleEvent,
)


@dataclass
class SignalFeedItem:
    source: str
    record: Any
    market: Market


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
    category: str | None = None,
    has_signals: bool | None = None,
    signal_type: str | None = None,
) -> list[tuple[Market, MarketSnapshot | None, str | None, bool, bool]]:
    latest_snapshot_subquery = (
        select(
            MarketSnapshot.market_id.label("market_id"),
            func.max(MarketSnapshot.observed_at).label("max_observed_at"),
        )
        .group_by(MarketSnapshot.market_id)
        .subquery()
    )

    primary_tag_subquery = (
        select(
            EventTag.event_id.label("event_id"),
            func.min(Tag.label).label("primary_tag_label"),
        )
        .join(Tag, EventTag.tag_id == Tag.id)
        .group_by(EventTag.event_id)
        .subquery()
    )

    category_expr = func.coalesce(Event.category, primary_tag_subquery.c.primary_tag_label)
    snapshot_signal_presence_subquery = (
        select(Signal.market_id.label("market_id"))
        .distinct()
        .subquery()
    )
    whale_presence_subquery = (
        select(WhaleEvent.market_id.label("market_id"))
        .distinct()
        .subquery()
    )
    signal_type_subquery = None
    if signal_type:
        if signal_type == "whale":
            signal_type_subquery = (
                select(
                    WhaleEvent.market_id.label("market_id"),
                    literal("whale").label("signal_type"),
                )
                .distinct()
                .subquery()
            )
        else:
            signal_type_subquery = (
                select(
                    Signal.market_id.label("market_id"),
                    Signal.signal_type.label("signal_type"),
                )
                .distinct()
                .where(Signal.signal_type == signal_type)
                .subquery()
            )
    has_snapshot_signals_expr = snapshot_signal_presence_subquery.c.market_id.is_not(None)
    has_whales_expr = whale_presence_subquery.c.market_id.is_not(None)
    has_signals_expr = or_(has_snapshot_signals_expr, has_whales_expr)

    stmt = (
        select(
            Market,
            MarketSnapshot,
            category_expr.label("category"),
            has_signals_expr.label("has_signals"),
            has_whales_expr.label("has_whales"),
        )
        .outerjoin(latest_snapshot_subquery, latest_snapshot_subquery.c.market_id == Market.id)
        .outerjoin(
            MarketSnapshot,
            (MarketSnapshot.market_id == latest_snapshot_subquery.c.market_id)
            & (MarketSnapshot.observed_at == latest_snapshot_subquery.c.max_observed_at),
        )
        .join(Event, Market.event_id == Event.id)
        .outerjoin(primary_tag_subquery, primary_tag_subquery.c.event_id == Event.id)
        .outerjoin(
            snapshot_signal_presence_subquery,
            snapshot_signal_presence_subquery.c.market_id == Market.id,
        )
        .outerjoin(whale_presence_subquery, whale_presence_subquery.c.market_id == Market.id)
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
    if category:
        normalized_category = category.strip().lower()
        stmt = stmt.where(func.lower(category_expr) == normalized_category)
    if has_signals is True:
        stmt = stmt.where(has_signals_expr)
    if signal_type:
        stmt = stmt.outerjoin(
            signal_type_subquery,
            and_(
                signal_type_subquery.c.market_id == Market.id,
                signal_type_subquery.c.signal_type == signal_type,
            ),
        ).where(signal_type_subquery.c.market_id.is_not(None))

    stmt = stmt.order_by(
        desc(has_signals_expr),
        Market.slug.is_(None),
        Market.slug,
        Market.market_id,
    ).limit(limit).offset(offset)
    return list(session.execute(stmt).all())


def get_available_market_categories(session: Session) -> list[str]:
    primary_tag_subquery = (
        select(
            EventTag.event_id.label("event_id"),
            func.min(Tag.label).label("primary_tag_label"),
        )
        .join(Tag, EventTag.tag_id == Tag.id)
        .group_by(EventTag.event_id)
        .subquery()
    )
    category_expr = func.coalesce(Event.category, primary_tag_subquery.c.primary_tag_label)
    stmt = (
        select(func.distinct(category_expr))
        .select_from(Event)
        .outerjoin(primary_tag_subquery, primary_tag_subquery.c.event_id == Event.id)
        .where(category_expr.is_not(None))
        .order_by(category_expr.asc())
    )
    return [value for value in session.execute(stmt).scalars().all() if value]


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


def get_recent_whale_events(
    session: Session,
    *,
    limit: int = 10,
    market_id: str | None = None,
    category: str | None = None,
    min_score: Decimal | None = None,
) -> list[tuple[WhaleEvent, Market, Trade]]:
    stmt = (
        select(WhaleEvent, Market, Trade)
        .join(Market, WhaleEvent.market_id == Market.id)
        .join(Trade, WhaleEvent.trade_id == Trade.id)
        .join(Event, Market.event_id == Event.id)
    )
    if market_id:
        stmt = stmt.where(Market.market_id == market_id)
    if category:
        stmt = stmt.where(func.lower(Event.category) == category.strip().lower())
    if min_score is not None:
        stmt = stmt.where(WhaleEvent.whale_score >= min_score)
    stmt = stmt.order_by(WhaleEvent.detected_at.desc()).limit(limit)
    return list(session.execute(stmt).all())


def get_market_whales(
    session: Session,
    market_id: str,
    *,
    limit: int = 20,
) -> list[tuple[WhaleEvent, Market, Trade]]:
    return get_recent_whale_events(session, limit=limit, market_id=market_id)


def get_market_whale_summary(session: Session, market_id: str) -> dict[str, Any] | None:
    market = get_market_by_api_id(session, market_id)
    if market is None:
        return None

    whale_rows = session.execute(
        select(WhaleEvent, Trade)
        .join(Trade, WhaleEvent.trade_id == Trade.id)
        .where(WhaleEvent.market_id == market.id)
        .order_by(WhaleEvent.detected_at.desc())
    ).all()
    if not whale_rows:
        return {
            "market_id": market.market_id,
            "total_whale_events": 0,
            "most_recent_whale_at": None,
            "largest_whale_trade": None,
            "average_whale_score": None,
            "whale_events_24h": 0,
            "whale_events_7d": 0,
            "has_recent_whale_activity": False,
        }

    now_anchor = datetime.now(timezone.utc)
    past_24h = 0
    past_7d = 0
    total_score = Decimal("0")
    largest_trade = Decimal("0")
    for whale_event, _trade in whale_rows:
        total_score += whale_event.whale_score
        largest_trade = max(largest_trade, whale_event.trade_size)
        detected_at = whale_event.detected_at
        if detected_at.tzinfo is None:
            detected_at = detected_at.replace(tzinfo=timezone.utc)
        age_seconds = (now_anchor - detected_at).total_seconds()
        if age_seconds <= 86400:
            past_24h += 1
        if age_seconds <= 604800:
            past_7d += 1

    return {
        "market_id": market.market_id,
        "total_whale_events": len(whale_rows),
        "most_recent_whale_at": whale_rows[0][0].detected_at,
        "largest_whale_trade": largest_trade,
        "average_whale_score": total_score / Decimal(len(whale_rows)),
        "whale_events_24h": past_24h,
        "whale_events_7d": past_7d,
        "has_recent_whale_activity": past_24h > 0 or past_7d > 0,
    }


def get_signal_feed(
    session: Session,
    *,
    limit: int = 10,
    signal_type: str | None = None,
    market_id: str | None = None,
) -> list[SignalFeedItem]:
    if signal_type == "whale":
        return [
            SignalFeedItem(source="whale", record=whale_event, market=market)
            for whale_event, market, _trade in get_recent_whale_events(
                session,
                limit=limit,
                market_id=market_id,
            )
        ]

    signal_items = [
        SignalFeedItem(source="signal", record=signal, market=market)
        for signal, market in get_recent_signals(
            session,
            limit=limit,
            signal_type=signal_type,
            market_id=market_id,
        )
    ]

    if signal_type is None:
        whale_items = [
            SignalFeedItem(source="whale", record=whale_event, market=market)
            for whale_event, market, _trade in get_recent_whale_events(
                session,
                limit=limit,
                market_id=market_id,
            )
        ]
        combined = signal_items + whale_items
        combined.sort(key=lambda item: item.record.detected_at, reverse=True)
        return combined[:limit]

    return signal_items


def get_market_signals(
    session: Session,
    market_id: str,
    *,
    limit: int = 10,
) -> list[SignalFeedItem]:
    return get_signal_feed(session, limit=limit, market_id=market_id)


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
    whales_parser = subparsers.add_parser("whales")
    whales_parser.add_argument("--limit", type=int, default=10)
    whales_parser.add_argument("--market-id")
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
            for item in get_signal_feed(
                session,
                limit=args.limit,
                signal_type=args.signal_type,
                market_id=args.market_id,
            ):
                if item.source == "whale":
                    whale_event = item.record
                    summary = whale_event.metadata_json.get("summary", "")
                    print(
                        f"{whale_event.detected_at.isoformat()}\t{item.market.market_id}\t"
                        f"whale\t{whale_event.whale_score}\t{summary}"
                    )
                else:
                    signal = item.record
                    summary = signal.metadata_json.get("summary", "")
                    print(
                        f"{signal.detected_at.isoformat()}\t{item.market.market_id}\t"
                        f"{signal.signal_type}\t{signal.signal_strength}\t{summary}"
                    )
        elif args.command == "whales":
            for whale_event, market, _trade in get_recent_whale_events(
                session,
                limit=args.limit,
                market_id=args.market_id,
            ):
                summary = whale_event.metadata_json.get("summary", "")
                print(
                    f"{whale_event.detected_at.isoformat()}\t{market.market_id}\t"
                    f"{whale_event.trade_size}\t{whale_event.whale_score}\t{summary}"
                )


if __name__ == "__main__":
    main()
