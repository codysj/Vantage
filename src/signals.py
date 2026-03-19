from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from src.config import settings
from src.models import Market, MarketSnapshot, Signal


PRICE_MOVEMENT = "price_movement"
VOLUME_SPIKE = "volume_spike"
LIQUIDITY_SHIFT = "liquidity_shift"


@dataclass
class SignalCandidate:
    market_id: int
    event_id: int
    snapshot_id: int
    signal_type: str
    signal_strength: Decimal
    detected_at: Any
    metadata_json: dict[str, Any]


@dataclass
class SignalGenerationResult:
    generated_count: int
    skipped_count: int
    signal_type_counts: dict[str, int]


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _extract_price(snapshot: MarketSnapshot) -> Decimal | None:
    if snapshot.last_trade_price is not None:
        return _as_decimal(snapshot.last_trade_price)
    outcome_prices = snapshot.outcome_prices or []
    if not outcome_prices:
        return None
    return _as_decimal(outcome_prices[0])


def _relative_change(new_value: Decimal, old_value: Decimal) -> Decimal | None:
    if old_value == 0:
        return None
    return abs((new_value - old_value) / old_value)


def _build_summary(signal_type: str, details: dict[str, Any]) -> str:
    if signal_type == PRICE_MOVEMENT:
        return f"Price moved {details['change_pct']:.2%} in {details['window_minutes']} minutes"
    if signal_type == VOLUME_SPIKE:
        return f"Volume increased {details['multiplier']:.2f}x versus recent baseline"
    return f"Liquidity changed {details['change_pct']:.2%} in {details['window_minutes']} minutes"


def compute_signals_for_snapshot(
    market: Market,
    latest_snapshot: MarketSnapshot,
    history: list[MarketSnapshot],
) -> tuple[list[SignalCandidate], int]:
    if len(history) < 2:
        return [], 1

    candidates: list[SignalCandidate] = []
    skipped_rules = 0
    earlier_snapshots = history[:-1]
    earliest_snapshot = history[0]

    latest_price = _extract_price(latest_snapshot)
    earliest_price = _extract_price(earliest_snapshot)
    if latest_price is not None and earliest_price is not None:
        price_change = _relative_change(latest_price, earliest_price)
        if price_change is not None and price_change >= settings.signal_price_threshold:
            metadata = {
                "summary": "",
                "window_minutes": settings.signal_lookback_window_minutes,
                "latest_price": str(latest_price),
                "baseline_price": str(earliest_price),
                "change_pct": float(price_change),
            }
            metadata["summary"] = _build_summary(PRICE_MOVEMENT, metadata)
            candidates.append(
                SignalCandidate(
                    market_id=market.id,
                    event_id=market.event_id,
                    snapshot_id=latest_snapshot.id,
                    signal_type=PRICE_MOVEMENT,
                    signal_strength=price_change,
                    detected_at=latest_snapshot.observed_at,
                    metadata_json=metadata,
                )
            )
    else:
        skipped_rules += 1

    prior_volumes = [_as_decimal(snapshot.volume) for snapshot in earlier_snapshots if snapshot.volume is not None]
    latest_volume = _as_decimal(latest_snapshot.volume)
    if latest_volume is not None and prior_volumes:
        baseline_volume = sum(prior_volumes) / Decimal(len(prior_volumes))
        if baseline_volume > 0:
            multiplier = latest_volume / baseline_volume
            if multiplier >= settings.signal_volume_multiplier:
                metadata = {
                    "summary": "",
                    "window_minutes": settings.signal_lookback_window_minutes,
                    "latest_volume": str(latest_volume),
                    "baseline_volume": str(baseline_volume),
                    "multiplier": float(multiplier),
                }
                metadata["summary"] = _build_summary(VOLUME_SPIKE, metadata)
                candidates.append(
                    SignalCandidate(
                        market_id=market.id,
                        event_id=market.event_id,
                        snapshot_id=latest_snapshot.id,
                        signal_type=VOLUME_SPIKE,
                        signal_strength=multiplier,
                        detected_at=latest_snapshot.observed_at,
                        metadata_json=metadata,
                    )
                )
        else:
            skipped_rules += 1
    else:
        skipped_rules += 1

    latest_liquidity = _as_decimal(latest_snapshot.liquidity)
    earliest_liquidity = _as_decimal(earliest_snapshot.liquidity)
    if latest_liquidity is not None and earliest_liquidity is not None:
        liquidity_change = _relative_change(latest_liquidity, earliest_liquidity)
        if liquidity_change is not None and liquidity_change >= settings.signal_liquidity_threshold:
            metadata = {
                "summary": "",
                "window_minutes": settings.signal_lookback_window_minutes,
                "latest_liquidity": str(latest_liquidity),
                "baseline_liquidity": str(earliest_liquidity),
                "change_pct": float(liquidity_change),
            }
            metadata["summary"] = _build_summary(LIQUIDITY_SHIFT, metadata)
            candidates.append(
                SignalCandidate(
                    market_id=market.id,
                    event_id=market.event_id,
                    snapshot_id=latest_snapshot.id,
                    signal_type=LIQUIDITY_SHIFT,
                    signal_strength=liquidity_change,
                    detected_at=latest_snapshot.observed_at,
                    metadata_json=metadata,
                )
            )
    else:
        skipped_rules += 1

    return candidates, skipped_rules


def _insert_signal(session: Session, candidate: SignalCandidate) -> bool:
    dialect_name = session.bind.dialect.name
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    else:
        from sqlalchemy.dialects.sqlite import insert as dialect_insert

    values = {
        "market_id": candidate.market_id,
        "event_id": candidate.event_id,
        "snapshot_id": candidate.snapshot_id,
        "signal_type": candidate.signal_type,
        "signal_strength": candidate.signal_strength,
        "metadata": candidate.metadata_json,
        "detected_at": candidate.detected_at,
    }
    statement = dialect_insert(Signal.__table__).values(**values).on_conflict_do_nothing(
        index_elements=["market_id", "signal_type", "snapshot_id"]
    )
    result = session.execute(statement)
    return result.rowcount > 0


def generate_signals_for_snapshots(
    session: Session,
    snapshot_ids: set[int],
) -> SignalGenerationResult:
    if not snapshot_ids:
        return SignalGenerationResult(generated_count=0, skipped_count=0, signal_type_counts={})

    signal_type_counts: Counter[str] = Counter()
    generated_count = 0
    skipped_count = 0

    latest_snapshots = session.execute(
        select(MarketSnapshot)
        .where(MarketSnapshot.id.in_(snapshot_ids))
        .order_by(MarketSnapshot.observed_at.asc())
    ).scalars().all()

    for latest_snapshot in latest_snapshots:
        market = session.get(Market, latest_snapshot.market_id)
        if market is None:
            skipped_count += 1
            continue

        window_start = latest_snapshot.observed_at - timedelta(
            minutes=settings.signal_lookback_window_minutes
        )
        history = session.execute(
            select(MarketSnapshot)
            .where(
                MarketSnapshot.market_id == market.id,
                MarketSnapshot.observed_at >= window_start,
                MarketSnapshot.observed_at <= latest_snapshot.observed_at,
            )
            .order_by(MarketSnapshot.observed_at.asc())
        ).scalars().all()

        candidates, skipped_rules = compute_signals_for_snapshot(market, latest_snapshot, history)
        skipped_count += skipped_rules
        for candidate in candidates:
            if _insert_signal(session, candidate):
                generated_count += 1
                signal_type_counts[candidate.signal_type] += 1

    return SignalGenerationResult(
        generated_count=generated_count,
        skipped_count=skipped_count,
        signal_type_counts=dict(signal_type_counts),
    )
