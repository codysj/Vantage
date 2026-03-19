from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from src.ingest import IngestionCycleSummary, execute_ingestion_cycle, persist_events, persist_trades
from src.models import Market, Trade, WhaleEvent
from src.normalize import normalize_trade
from src.queries import get_market_by_api_id
from src.whales import generate_whales_for_trades
from tests.test_normalize import sample_event_payload


def sample_trade_payload(
    *,
    condition_id: str = "cond-1",
    timestamp: int = 1_710_000_000_000,
    price: str = "0.60",
    size: str = "100",
    side: str = "BUY",
    outcome: str = "Yes",
    outcome_index: int = 0,
    wallet: str = "0xwallet",
    transaction_hash: str = "0xhash",
) -> dict:
    return {
        "conditionId": condition_id,
        "timestamp": timestamp,
        "price": price,
        "size": size,
        "side": side,
        "outcome": outcome,
        "outcomeIndex": outcome_index,
        "proxyWallet": wallet,
        "transactionHash": transaction_hash,
    }


def event_payload_with_condition() -> dict:
    payload = sample_event_payload()
    payload["markets"][0]["conditionId"] = "cond-1"
    return payload


def seed_market(session) -> Market:
    with session.begin():
        persist_events(
            session,
            [event_payload_with_condition()],
            observed_at=datetime(2026, 3, 18, tzinfo=timezone.utc),
        )
    market = get_market_by_api_id(session, "market-1")
    assert market is not None
    return market


def test_normalize_trade_builds_notional_and_metadata() -> None:
    normalized = normalize_trade(sample_trade_payload(price="0.62", size="1000"))

    assert normalized["condition_id"] == "cond-1"
    assert normalized["trade_size"] == Decimal("620.00")
    assert normalized["outcome_label"] == "Yes"
    assert normalized["proxy_wallet"] == "0xwallet"
    assert normalized["external_trade_id"].startswith("trade:")


def test_generate_whale_for_extreme_trade(session) -> None:
    market = seed_market(session)
    base_time = datetime(2026, 3, 18, 12, tzinfo=timezone.utc)
    trade_payloads = [
        sample_trade_payload(
            timestamp=int((base_time + timedelta(minutes=index)).timestamp() * 1000),
            price="0.50",
            size="200",
            transaction_hash=f"0xprior{index}",
        )
        for index in range(25)
    ]
    trade_payloads.append(
        sample_trade_payload(
            timestamp=int((base_time + timedelta(minutes=30)).timestamp() * 1000),
            price="0.60",
            size="4000",
            transaction_hash="0xwhale",
        )
    )
    summary = IngestionCycleSummary(trigger_mode="manual", run_started_at=base_time)

    persist_trades(session, [market], trade_payloads, summary=summary)
    result = generate_whales_for_trades(session, summary.touched_trade_ids)
    session.commit()

    assert result.generated_count == 1
    whale_event = session.execute(select(WhaleEvent)).scalar_one()
    assert whale_event.trade_size == Decimal("2400.00")
    assert whale_event.median_multiple is not None
    assert whale_event.median_multiple >= Decimal("5")


def test_generate_whale_skips_when_history_is_insufficient(session) -> None:
    market = seed_market(session)
    base_time = datetime(2026, 3, 18, 12, tzinfo=timezone.utc)
    trade_payloads = [
        sample_trade_payload(
            timestamp=int((base_time + timedelta(minutes=index)).timestamp() * 1000),
            price="0.50",
            size="200",
            transaction_hash=f"0xsmall{index}",
        )
        for index in range(5)
    ]
    trade_payloads.append(
        sample_trade_payload(
            timestamp=int((base_time + timedelta(minutes=10)).timestamp() * 1000),
            price="0.90",
            size="5000",
            transaction_hash="0xlate",
        )
    )
    summary = IngestionCycleSummary(trigger_mode="manual", run_started_at=base_time)

    persist_trades(session, [market], trade_payloads, summary=summary)
    result = generate_whales_for_trades(session, summary.touched_trade_ids)
    session.commit()

    assert result.generated_count == 0
    assert session.scalar(select(func.count()).select_from(WhaleEvent)) == 0


def test_generate_whale_rerun_is_idempotent(session) -> None:
    market = seed_market(session)
    base_time = datetime(2026, 3, 18, 12, tzinfo=timezone.utc)
    trade_payloads = [
        sample_trade_payload(
            timestamp=int((base_time + timedelta(minutes=index)).timestamp() * 1000),
            price="0.50",
            size="200",
            transaction_hash=f"0xstable{index}",
        )
        for index in range(25)
    ]
    trade_payloads.append(
        sample_trade_payload(
            timestamp=int((base_time + timedelta(minutes=40)).timestamp() * 1000),
            price="0.60",
            size="4000",
            transaction_hash="0xhuge",
        )
    )
    summary = IngestionCycleSummary(trigger_mode="manual", run_started_at=base_time)

    persist_trades(session, [market], trade_payloads, summary=summary)
    first_result = generate_whales_for_trades(session, summary.touched_trade_ids)
    session.commit()
    second_result = generate_whales_for_trades(session, summary.touched_trade_ids)
    session.commit()

    assert first_result.generated_count == 1
    assert second_result.generated_count == 0
    assert session.scalar(select(func.count()).select_from(WhaleEvent)) == 1


class WhaleStubClient:
    def __init__(self, event_payloads, trade_payloads):
        self.event_payloads = event_payloads
        self.trade_payloads = trade_payloads

    def fetch_events(self, limit=None):
        return self.event_payloads

    def fetch_trades(self, *, condition_ids, limit=None, offset=0):
        return [
            trade for trade in self.trade_payloads if trade["conditionId"] in set(condition_ids)
        ]


def test_execute_ingestion_cycle_ingests_trades_and_whales(session_factory) -> None:
    payload = event_payload_with_condition()
    base_time = datetime(2026, 3, 18, 12, tzinfo=timezone.utc)
    trade_payloads = [
        sample_trade_payload(
            timestamp=int((base_time + timedelta(minutes=index)).timestamp() * 1000),
            price="0.50",
            size="200",
            transaction_hash=f"0xpipe{index}",
        )
        for index in range(25)
    ]
    trade_payloads.append(
        sample_trade_payload(
            timestamp=int((base_time + timedelta(minutes=45)).timestamp() * 1000),
            price="0.60",
            size="4000",
            transaction_hash="0xpipe-whale",
        )
    )

    summary = execute_ingestion_cycle(
        client=WhaleStubClient([payload], trade_payloads),
        session_factory=session_factory,
        trigger_mode="manual",
    )

    assert summary.status == "success"
    assert summary.trades_inserted == 26
    assert summary.whales_generated == 1
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Trade)) == 26
        assert session.scalar(select(func.count()).select_from(WhaleEvent)) == 1
