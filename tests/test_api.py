from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api import app, get_db
from src.config import settings
from src.models import Base
from src.models import (
    IngestionRun,
    MarketSentimentSummary,
    SentimentDocument,
    SentimentScore,
    Signal,
    Trade,
    WhaleEvent,
)
from src.queries import get_market_by_api_id, get_market_history
from tests.test_normalize import sample_event_payload
from src.ingest import persist_events


def create_api_session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def create_test_client(session_factory):
    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def seed_market_data(session_factory) -> None:
    payload = sample_event_payload()
    payload["category"] = "Economy"
    payload["markets"][0]["lastTradePrice"] = "0.43"
    payload["markets"][0]["volume"] = "150"
    payload["markets"][0]["liquidity"] = "20"
    payload["markets"][0]["active"] = True
    payload["markets"][0]["closed"] = False
    payload["markets"][0]["conditionId"] = "cond-1"
    second_payload = {
        "id": "event-2",
        "slug": "btc-market",
        "title": "BTC Market",
        "question": "Will BTC rally this week?",
        "category": "Crypto",
        "active": True,
        "closed": False,
        "markets": [
            {
                "id": "market-2",
                "slug": "will-btc-rally-this-week",
                "question": "Will BTC rally this week?",
                "conditionId": "cond-2",
                "outcomes": "[\"Yes\", \"No\"]",
                "outcomePrices": "[\"0.51\", \"0.49\"]",
                "clobTokenIds": "[\"btc-yes\", \"btc-no\"]",
                "umaResolutionStatuses": "[\"pending\", \"pending\"]",
                "volume": "80",
                "liquidity": "30",
                "active": True,
                "closed": False,
                "updatedAt": "2026-03-04T15:30:00Z",
            }
        ],
    }
    with session_factory() as session:
        with session.begin():
            persist_events(
                session,
                [payload, second_payload],
                observed_at=datetime(2026, 3, 18, tzinfo=timezone.utc),
            )
        market = get_market_by_api_id(session, "market-1")
        snapshot = get_market_history(session, "market-1")[0]
        trade = Trade(
            market_id=market.id,
            external_trade_id="trade-1",
            side="BUY",
            price=Decimal("0.62"),
            size=Decimal("1000"),
            trade_size=Decimal("620"),
            proxy_wallet="0xabc",
            outcome_label="Yes",
            outcome_index=0,
            transaction_hash="0xhash",
            executed_at=snapshot.observed_at,
            raw_json={"conditionId": "cond-1"},
        )
        session.add(trade)
        session.flush()
        session.add(
            Signal(
                market_id=market.id,
                event_id=market.event_id,
                snapshot_id=snapshot.id,
                signal_type="price_movement",
                signal_strength=Decimal("0.20"),
                metadata_json={"summary": "Price moved 20%"},
                detected_at=snapshot.observed_at,
            )
        )
        session.add(
            WhaleEvent(
                market_id=market.id,
                trade_id=trade.id,
                detected_at=snapshot.observed_at,
                trade_size=Decimal("620"),
                baseline_mean_size=Decimal("120"),
                baseline_median_size=Decimal("75"),
                baseline_std_size=Decimal("50"),
                median_multiple=Decimal("8.26666667"),
                whale_score=Decimal("10"),
                detection_method="market_local_baseline",
                metadata_json={
                    "summary": "Whale trade 8.27x median notional",
                    "median_multiple": 8.27,
                    "side": "BUY",
                    "outcome_label": "Yes",
                    "proxy_wallet": "0xabc",
                },
            )
        )
        session.add(
            IngestionRun(
                run_started_at=datetime(2026, 3, 18, 1, tzinfo=timezone.utc),
                run_finished_at=datetime(2026, 3, 18, 1, 5, tzinfo=timezone.utc),
                status="success",
                trigger_mode="manual",
                api_source="gamma_events",
                records_fetched=1,
                events_upserted=1,
                markets_upserted=1,
                snapshots_inserted=1,
                records_skipped=0,
                integrity_errors=0,
                duration_ms=5000,
            )
        )
        sentiment_document = SentimentDocument(
            market_id=market.id,
            source_name="Reuters",
            url="https://example.com/fed-rates",
            title="Fed outlook remains in focus",
            snippet="Markets continue to watch the Fed closely.",
            raw_text="Fed outlook remains in focus Markets continue to watch the Fed closely.",
            published_at=snapshot.observed_at,
        )
        session.add(sentiment_document)
        session.flush()
        session.add(
            SentimentScore(
                document_id=sentiment_document.id,
                model_name=settings.sentiment_model_name,
                sentiment_label="positive",
                sentiment_confidence=Decimal("0.88"),
                sentiment_value=Decimal("0.88"),
                scored_at=snapshot.observed_at,
            )
        )
        session.add(
            MarketSentimentSummary(
                market_id=market.id,
                avg_sentiment=Decimal("0.88"),
                doc_count=1,
                pos_count=1,
                neg_count=0,
                neutral_count=0,
                last_computed_at=snapshot.observed_at,
            )
        )
        session.commit()


def test_health_endpoint() -> None:
    client = create_test_client(create_api_session_factory())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body
    app.dependency_overrides.clear()


def test_markets_endpoints() -> None:
    session_factory = create_api_session_factory()
    seed_market_data(session_factory)
    client = create_test_client(session_factory)

    list_response = client.get("/markets")
    detail_response = client.get("/markets/market-1")
    history_response = client.get("/markets/market-1/history")

    assert list_response.status_code == 200
    assert list_response.json()["count"] == 2
    assert list_response.json()["available_categories"] == ["Crypto", "Economy"]
    signal_flags = {item["market_id"]: item["has_signals"] for item in list_response.json()["items"]}
    whale_flags = {item["market_id"]: item["has_whales"] for item in list_response.json()["items"]}
    assert signal_flags["market-1"] is True
    assert signal_flags["market-2"] is False
    assert whale_flags["market-1"] is True
    assert whale_flags["market-2"] is False
    assert detail_response.status_code == 200
    assert detail_response.json()["market_id"] == "market-1"
    assert history_response.status_code == 200
    assert history_response.json()["count"] == 1
    app.dependency_overrides.clear()


def test_markets_filter_and_404() -> None:
    session_factory = create_api_session_factory()
    seed_market_data(session_factory)
    client = create_test_client(session_factory)

    filtered = client.get("/markets", params={"slug": "will-fed-cut-rates-june"})
    category_filtered = client.get("/markets", params={"category": "Economy"})
    has_signals_filtered = client.get("/markets", params={"has_signals": "true"})
    signal_type_filtered = client.get("/markets", params={"signal_type": "price_movement"})
    whale_type_filtered = client.get("/markets", params={"signal_type": "whale"})
    missing = client.get("/markets/does-not-exist")

    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1
    assert category_filtered.status_code == 200
    assert category_filtered.json()["count"] == 1
    assert has_signals_filtered.status_code == 200
    assert has_signals_filtered.json()["count"] == 1
    assert has_signals_filtered.json()["items"][0]["market_id"] == "market-1"
    assert signal_type_filtered.status_code == 200
    assert signal_type_filtered.json()["count"] == 1
    assert signal_type_filtered.json()["items"][0]["market_id"] == "market-1"
    assert whale_type_filtered.status_code == 200
    assert whale_type_filtered.json()["count"] == 1
    assert whale_type_filtered.json()["items"][0]["market_id"] == "market-1"
    assert missing.status_code == 404
    app.dependency_overrides.clear()


def test_signals_endpoints() -> None:
    session_factory = create_api_session_factory()
    seed_market_data(session_factory)
    client = create_test_client(session_factory)

    signals = client.get("/signals", params={"signal_type": "price_movement"})
    market_signals = client.get("/markets/market-1/signals")

    assert signals.status_code == 200
    assert signals.json()["count"] == 1
    assert signals.json()["items"][0]["signal_type"] == "price_movement"
    assert signals.json()["items"][0]["market_question"] == "Will the Fed cut rates in June?"
    assert signals.json()["items"][0]["market_slug"] == "will-fed-cut-rates-june"
    assert signals.json()["items"][0]["market_active"] is True
    assert signals.json()["items"][0]["market_closed"] is False
    assert market_signals.status_code == 200
    assert market_signals.json()["count"] == 2
    whale_feed = client.get("/signals", params={"signal_type": "whale"})
    assert whale_feed.status_code == 200
    assert whale_feed.json()["count"] == 1
    assert whale_feed.json()["items"][0]["signal_type"] == "whale"
    app.dependency_overrides.clear()


def test_runs_endpoints() -> None:
    session_factory = create_api_session_factory()
    seed_market_data(session_factory)
    client = create_test_client(session_factory)

    runs = client.get("/runs")
    run_detail = client.get("/runs/1")
    missing = client.get("/runs/999")

    assert runs.status_code == 200
    assert runs.json()["count"] == 1
    assert run_detail.status_code == 200
    assert run_detail.json()["id"] == 1
    assert missing.status_code == 404
    app.dependency_overrides.clear()


def test_whale_alerts_endpoint() -> None:
    session_factory = create_api_session_factory()
    seed_market_data(session_factory)
    client = create_test_client(session_factory)

    response = client.get("/whale-alerts")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["alerts"][0]["market_id"] == "market-1"
    assert "Whale trade" in body["alerts"][0]["summary"]
    app.dependency_overrides.clear()


def test_whale_endpoints() -> None:
    session_factory = create_api_session_factory()
    seed_market_data(session_factory)
    client = create_test_client(session_factory)

    recent = client.get("/whales/recent")
    market_whales = client.get("/markets/market-1/whales")
    summary = client.get("/markets/market-1/whale-summary")
    missing = client.get("/markets/does-not-exist/whale-summary")

    assert recent.status_code == 200
    assert recent.json()["count"] == 1
    assert recent.json()["items"][0]["trade_size"] == 620.0
    assert market_whales.status_code == 200
    assert market_whales.json()["count"] == 1
    assert summary.status_code == 200
    assert summary.json()["total_whale_events"] == 1
    assert summary.json()["has_recent_whale_activity"] is True
    assert missing.status_code == 404
    app.dependency_overrides.clear()


def test_sentiment_endpoints(monkeypatch) -> None:
    session_factory = create_api_session_factory()
    seed_market_data(session_factory)

    def stub_sentiment(session, market_id):
        market = get_market_by_api_id(session, market_id)
        if market is None:
            return None
        summary = market.sentiment_summary
        return SimpleNamespace(market=market, summary=summary, from_cache=True)

    monkeypatch.setattr("src.api.get_or_compute_market_sentiment", stub_sentiment)
    client = create_test_client(session_factory)

    summary = client.get("/markets/market-1/sentiment")
    documents = client.get("/markets/market-1/sentiment/documents")
    missing = client.get("/markets/does-not-exist/sentiment")

    assert summary.status_code == 200
    assert summary.json()["market_id"] == "market-1"
    assert summary.json()["status"] == "ok"
    assert summary.json()["avg_sentiment"] == 0.88
    assert summary.json()["doc_count"] == 1
    assert documents.status_code == 200
    assert documents.json()["status"] == "ok"
    assert documents.json()["count"] == 1
    assert documents.json()["items"][0]["sentiment_label"] == "positive"
    assert missing.status_code == 404
    app.dependency_overrides.clear()


def test_sentiment_empty_state_endpoint(monkeypatch) -> None:
    session_factory = create_api_session_factory()
    seed_market_data(session_factory)

    def stub_empty_sentiment(session, market_id):
        market = get_market_by_api_id(session, market_id)
        if market is None:
            return None
        summary = market.sentiment_summary
        summary.avg_sentiment = Decimal("0")
        summary.doc_count = 0
        summary.pos_count = 0
        summary.neg_count = 0
        summary.neutral_count = 0
        return SimpleNamespace(market=market, summary=summary, from_cache=False)

    monkeypatch.setattr("src.api.get_or_compute_market_sentiment", stub_empty_sentiment)
    monkeypatch.setattr("src.api.get_market_sentiment_documents", lambda db, market_id, model_name: [])
    client = create_test_client(session_factory)

    summary = client.get("/markets/market-1/sentiment")
    documents = client.get("/markets/market-1/sentiment/documents")

    assert summary.status_code == 200
    assert summary.json()["status"] == "empty"
    assert summary.json()["message"] == "No recent headlines found for this market."
    assert documents.status_code == 200
    assert documents.json()["status"] == "empty"
    assert documents.json()["count"] == 0
    app.dependency_overrides.clear()


def test_sentiment_upstream_failure_returns_structured_503(monkeypatch) -> None:
    from src.sentiment import SentimentUpstreamError

    session_factory = create_api_session_factory()
    seed_market_data(session_factory)
    client = create_test_client(session_factory)

    monkeypatch.setattr(
        "src.api.get_or_compute_market_sentiment",
        lambda db, market_id: (_ for _ in ()).throw(
            SentimentUpstreamError("Headline source is temporarily unavailable.")
        ),
    )

    response = client.get("/markets/market-1/sentiment")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "sentiment_upstream_unavailable"
    assert response.json()["detail"]["message"] == "Headline source is temporarily unavailable."
    app.dependency_overrides.clear()


def test_sentiment_model_failure_returns_structured_503(monkeypatch) -> None:
    from src.sentiment import SentimentModelError

    session_factory = create_api_session_factory()
    seed_market_data(session_factory)
    client = create_test_client(session_factory)

    monkeypatch.setattr(
        "src.api.get_or_compute_market_sentiment",
        lambda db, market_id: (_ for _ in ()).throw(
            SentimentModelError("Sentiment model is temporarily unavailable.")
        ),
    )

    response = client.get("/markets/market-1/sentiment/documents")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "sentiment_model_unavailable"
    assert response.json()["detail"]["message"] == "Sentiment model is temporarily unavailable."
    app.dependency_overrides.clear()
