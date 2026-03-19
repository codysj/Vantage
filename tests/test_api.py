from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api import app, get_db
from src.models import Base
from src.models import IngestionRun, Signal
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
    payload["markets"][0]["lastTradePrice"] = "0.43"
    payload["markets"][0]["volume"] = "150"
    payload["markets"][0]["liquidity"] = "20"
    with session_factory() as session:
        with session.begin():
            persist_events(session, [payload], observed_at=datetime(2026, 3, 18, tzinfo=timezone.utc))
        market = get_market_by_api_id(session, "market-1")
        snapshot = get_market_history(session, "market-1")[0]
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
    assert list_response.json()["count"] == 1
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
    missing = client.get("/markets/does-not-exist")

    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1
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
    assert market_signals.status_code == 200
    assert market_signals.json()["count"] == 1
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
    client = create_test_client(create_api_session_factory())

    response = client.get("/whale-alerts")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["alerts"] == []
    app.dependency_overrides.clear()
