"""Whale detection over normalized trade history.

This layer treats unusually large trades relative to a market's own recent
activity as whale candidates and persists them as first-class events.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, insert, or_, select
from sqlalchemy.orm import Session

from src.config import settings
from src.db import SessionLocal
from src.models import Market, Trade, WhaleEvent


WHALE_SIGNAL_TYPE = "whale"
WHALE_DETECTION_METHOD = "market_local_baseline"


@dataclass
class WhaleCandidate:
    market_id: int
    trade_id: int
    detected_at: Any
    trade_size: Decimal
    baseline_mean_size: Decimal | None
    baseline_median_size: Decimal | None
    baseline_std_size: Decimal | None
    median_multiple: Decimal | None
    whale_score: Decimal
    detection_method: str
    metadata_json: dict[str, Any]


@dataclass
class WhaleGenerationResult:
    generated_count: int
    skipped_count: int
    scanned_count: int
    detection_method_counts: dict[str, int]


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def _mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values) / Decimal(len(values))


def _std(values: list[Decimal], mean_value: Decimal | None) -> Decimal | None:
    if not values or mean_value is None:
        return None
    variance = sum((value - mean_value) ** 2 for value in values) / Decimal(len(values))
    return variance.sqrt() if variance >= 0 else None


def _build_summary(trade: Trade, median_multiple: Decimal | None, trade_size: Decimal) -> str:
    if median_multiple is not None:
        return f"Whale trade {median_multiple:.2f}x median notional"
    return f"Whale trade detected at notional {trade_size:.2f}"


def compute_whale_for_trade(trade: Trade, history: list[Trade]) -> WhaleCandidate | None:
    """Return a whale candidate when a trade is extreme for its own market."""
    if trade.trade_size is None or trade.trade_size < settings.whale_absolute_min_notional:
        return None

    # use a market-local baseline so large trades are judged against that
    # contract's normal activity, not against the whole platform.
    baseline_sizes = [item.trade_size for item in history if item.trade_size is not None]
    if len(baseline_sizes) < settings.whale_min_history_count:
        return None

    baseline_mean = _mean(baseline_sizes)
    baseline_median = _median(baseline_sizes)
    baseline_std = _std(baseline_sizes, baseline_mean)
    if baseline_median is None or baseline_median <= 0:
        return None

    median_multiple = trade.trade_size / baseline_median
    zscore: Decimal | None = None
    if baseline_std is not None and baseline_std > 0 and baseline_mean is not None:
        zscore = (trade.trade_size - baseline_mean) / baseline_std

    # a trade qualifies if it clears the absolute floor and is extreme by
    # either z-score or multiple-of-median, which is more stable on skewed data.
    if (
        (zscore is None or zscore < settings.whale_zscore_threshold)
        and median_multiple < settings.whale_median_multiplier_threshold
    ):
        return None

    whale_score = zscore if zscore is not None and zscore > 0 else median_multiple
    metadata_json = {
        "summary": _build_summary(trade, median_multiple, trade.trade_size),
        "side": trade.side,
        "outcome_label": trade.outcome_label,
        "outcome_index": trade.outcome_index,
        "proxy_wallet": trade.proxy_wallet,
        "transaction_hash": trade.transaction_hash,
        "trade_price": str(trade.price) if trade.price is not None else None,
        "trade_shares": str(trade.size) if trade.size is not None else None,
        "trade_size": str(trade.trade_size),
        "baseline_mean_size": str(baseline_mean) if baseline_mean is not None else None,
        "baseline_median_size": str(baseline_median) if baseline_median is not None else None,
        "baseline_std_size": str(baseline_std) if baseline_std is not None else None,
        "median_multiple": float(median_multiple),
        "whale_score": float(whale_score),
        "thresholds": {
            "absolute_min_notional": float(settings.whale_absolute_min_notional),
            "zscore_threshold": float(settings.whale_zscore_threshold),
            "median_multiplier_threshold": float(settings.whale_median_multiplier_threshold),
            "min_history_count": settings.whale_min_history_count,
            "baseline_trade_count": settings.whale_baseline_trade_count,
        },
    }
    if zscore is not None:
        metadata_json["zscore"] = float(zscore)

    return WhaleCandidate(
        market_id=trade.market_id,
        trade_id=trade.id,
        detected_at=trade.executed_at or trade.inserted_at,
        trade_size=trade.trade_size,
        baseline_mean_size=baseline_mean,
        baseline_median_size=baseline_median,
        baseline_std_size=baseline_std,
        median_multiple=median_multiple,
        whale_score=whale_score,
        detection_method=WHALE_DETECTION_METHOD,
        metadata_json=metadata_json,
    )


def _insert_whale_event(session: Session, candidate: WhaleCandidate) -> bool:
    # the same trade and detection method should only persist once, even when
    # backfills or retries replay historical trades.
    dialect_name = session.bind.dialect.name
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    else:
        from sqlalchemy.dialects.sqlite import insert as dialect_insert

    values = {
        "market_id": candidate.market_id,
        "trade_id": candidate.trade_id,
        "detected_at": candidate.detected_at,
        "trade_size": candidate.trade_size,
        "baseline_mean_size": candidate.baseline_mean_size,
        "baseline_median_size": candidate.baseline_median_size,
        "baseline_std_size": candidate.baseline_std_size,
        "median_multiple": candidate.median_multiple,
        "whale_score": candidate.whale_score,
        "detection_method": candidate.detection_method,
        "metadata": candidate.metadata_json,
    }
    statement = dialect_insert(WhaleEvent.__table__).values(**values).on_conflict_do_nothing(
        index_elements=["trade_id", "detection_method"]
    )
    result = session.execute(statement)
    return result.rowcount > 0


def generate_whales_for_trades(session: Session, trade_ids: set[int]) -> WhaleGenerationResult:
    """Detect whale events for the newly inserted trades from this run."""
    if not trade_ids:
        return WhaleGenerationResult(
            generated_count=0,
            skipped_count=0,
            scanned_count=0,
            detection_method_counts={},
        )

    detection_method_counts: Counter[str] = Counter()
    generated_count = 0
    skipped_count = 0
    scanned_count = 0

    trades = session.execute(
        select(Trade)
        .where(Trade.id.in_(trade_ids))
        .order_by(Trade.executed_at.asc().nullslast(), Trade.id.asc())
    ).scalars().all()

    for trade in trades:
        scanned_count += 1
        if trade.market_id is None:
            skipped_count += 1
            continue
        if trade.executed_at is not None:
            history_filter = or_(
                Trade.executed_at < trade.executed_at,
                and_(Trade.executed_at == trade.executed_at, Trade.id < trade.id),
            )
        else:
            history_filter = Trade.id < trade.id
        history = session.execute(
            select(Trade)
            .where(
                Trade.market_id == trade.market_id,
                Trade.trade_size.is_not(None),
                history_filter,
            )
            .order_by(Trade.executed_at.desc().nullslast(), Trade.id.desc())
            .limit(settings.whale_baseline_trade_count)
        ).scalars().all()

        candidate = compute_whale_for_trade(trade, history)
        if candidate is None:
            skipped_count += 1
            continue
        if _insert_whale_event(session, candidate):
            generated_count += 1
            detection_method_counts[candidate.detection_method] += 1

    return WhaleGenerationResult(
        generated_count=generated_count,
        skipped_count=skipped_count,
        scanned_count=scanned_count,
        detection_method_counts=dict(detection_method_counts),
    )


def backfill_whales(session: Session, market_api_id: str | None = None) -> WhaleGenerationResult:
    """Replay whale detection across already stored trades."""
    stmt = select(Trade.id)
    if market_api_id:
        stmt = stmt.join(Market).where(Market.market_id == market_api_id)
    trade_ids = set(session.execute(stmt).scalars().all())
    return generate_whales_for_trades(session, trade_ids)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Whale detection utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backfill_parser = subparsers.add_parser("backfill")
    backfill_parser.add_argument("--market-id")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    with SessionLocal() as session:
        with session.begin():
            result = backfill_whales(session, market_api_id=getattr(args, "market_id", None))
    print(
        "whale_backfill",
        f"generated={result.generated_count}",
        f"skipped={result.skipped_count}",
        f"scanned={result.scanned_count}",
    )


if __name__ == "__main__":
    main()
