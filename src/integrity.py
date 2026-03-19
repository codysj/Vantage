from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import Event, Market, MarketOutcome, MarketSnapshot


NUMERIC_SNAPSHOT_FIELDS = (
    "last_trade_price",
    "best_bid",
    "best_ask",
    "spread",
    "volume",
    "volume_24hr",
    "volume_1wk",
    "volume_1mo",
    "volume_1yr",
    "liquidity",
    "liquidity_clob",
    "volume_clob",
    "open_interest",
    "one_day_price_change",
    "one_week_price_change",
    "one_month_price_change",
    "one_year_price_change",
)
NON_NEGATIVE_FIELDS = (
    "volume",
    "volume_24hr",
    "volume_1wk",
    "volume_1mo",
    "volume_1yr",
    "liquidity",
    "liquidity_clob",
    "volume_clob",
    "open_interest",
)


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _raw_contains_invalid_numeric(raw_payload: dict[str, Any], keys: Iterable[str], normalized_value: Any) -> bool:
    for key in keys:
        if key in raw_payload and raw_payload[key] not in (None, "") and normalized_value is None:
            return True
    return False


def validate_normalized_event(normalized_event: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    event_data = normalized_event["event"]
    if _is_blank(event_data.get("event_id")):
        issues.append("Event is missing event_id.")
    return issues


def validate_market_bundle(market_bundle: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    market_data = market_bundle["market"]
    snapshot_data = market_bundle["snapshot"]
    raw_market = market_data.get("raw_json") or {}

    if _is_blank(market_data.get("market_id")):
        issues.append("Market is missing market_id.")
    if _is_blank(market_data.get("event_api_id")):
        issues.append(f"Market {market_data.get('market_id', '<unknown>')} is missing event_api_id.")

    numeric_key_map = {
        "order_min_size": ("orderMinSize",),
        "order_price_min_tick_size": ("orderPriceMinTickSize",),
        "group_item_threshold": ("groupItemThreshold",),
        "volume": ("volume",),
        "volume_24hr": ("volume24hr", "volume24Hr"),
        "volume_1wk": ("volume1wk", "volume1Wk"),
        "volume_1mo": ("volume1mo", "volume1Mo"),
        "volume_1yr": ("volume1yr", "volume1Yr"),
        "liquidity": ("liquidity",),
        "liquidity_clob": ("liquidityClob",),
        "volume_clob": ("volumeClob",),
        "open_interest": ("openInterest",),
        "last_trade_price": ("lastTradePrice", "last_trade_price"),
        "best_bid": ("bestBid", "best_bid"),
        "best_ask": ("bestAsk", "best_ask"),
        "spread": ("spread",),
        "one_day_price_change": ("oneDayPriceChange", "priceChange24hr"),
        "one_week_price_change": ("oneWeekPriceChange",),
        "one_month_price_change": ("oneMonthPriceChange",),
        "one_year_price_change": ("oneYearPriceChange",),
    }
    for field_name, raw_keys in numeric_key_map.items():
        normalized_value = market_data.get(field_name)
        if field_name in NUMERIC_SNAPSHOT_FIELDS:
            normalized_value = snapshot_data.get(field_name)
        if _raw_contains_invalid_numeric(raw_market, raw_keys, normalized_value):
            issues.append(
                f"Market {market_data.get('market_id', '<unknown>')} has invalid numeric field {field_name}."
            )

    for field_name in NON_NEGATIVE_FIELDS:
        value = snapshot_data.get(field_name)
        if isinstance(value, Decimal) and value < 0:
            issues.append(
                f"Market {market_data.get('market_id', '<unknown>')} has negative {field_name}."
            )

    for outcome in market_bundle["outcomes"]:
        price = outcome.get("current_price")
        if price is not None and (price < Decimal("0") or price > Decimal("1")):
            issues.append(
                f"Market {market_data.get('market_id', '<unknown>')} has out-of-range outcome price."
            )

    return issues


def run_post_write_checks(session: Session, records_fetched: int, events_upserted: int) -> list[str]:
    issues: list[str] = []

    duplicate_event_ids = session.execute(
        select(Event.event_id).group_by(Event.event_id).having(func.count(Event.id) > 1)
    ).scalars().all()
    if duplicate_event_ids:
        issues.append(f"Duplicate event_ids found: {duplicate_event_ids[:3]}")

    duplicate_market_ids = session.execute(
        select(Market.market_id).group_by(Market.market_id).having(func.count(Market.id) > 1)
    ).scalars().all()
    if duplicate_market_ids:
        issues.append(f"Duplicate market_ids found: {duplicate_market_ids[:3]}")

    duplicate_outcomes = session.execute(
        select(MarketOutcome.market_id, MarketOutcome.outcome_index)
        .group_by(MarketOutcome.market_id, MarketOutcome.outcome_index)
        .having(func.count(MarketOutcome.id) > 1)
    ).all()
    if duplicate_outcomes:
        issues.append("Duplicate market outcome rows found.")

    duplicate_snapshots = session.execute(
        select(MarketSnapshot.snapshot_key)
        .group_by(MarketSnapshot.snapshot_key)
        .having(func.count(MarketSnapshot.id) > 1)
    ).scalars().all()
    if duplicate_snapshots:
        issues.append("Duplicate snapshot keys found.")

    orphan_markets = session.execute(
        select(Market.id).outerjoin(Event, Market.event_id == Event.id).where(Event.id.is_(None))
    ).scalars().all()
    if orphan_markets:
        issues.append(f"Orphan markets found: {orphan_markets[:3]}")

    blank_event_ids = session.execute(
        select(func.count()).select_from(Event).where(
            (Event.event_id.is_(None)) | (Event.event_id == "")
        )
    ).scalar_one()
    if blank_event_ids:
        issues.append("Events with blank event_id found.")

    blank_market_ids = session.execute(
        select(func.count()).select_from(Market).where(
            (Market.market_id.is_(None)) | (Market.market_id == "")
        )
    ).scalar_one()
    if blank_market_ids:
        issues.append("Markets with blank market_id found.")

    session.execute(select(func.count()).select_from(MarketSnapshot)).scalar_one()

    if records_fetched > 0 and events_upserted == 0:
        issues.append("Fetched records but did not upsert any events.")

    return issues
