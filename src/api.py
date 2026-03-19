from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.api_schemas import (
    ApiIndexResponse,
    HealthResponse,
    MarketDetailResponse,
    MarketListResponse,
    MarketOutcomeResponse,
    MarketSummary,
    RunListResponse,
    RunResponse,
    SignalListResponse,
    SignalResponse,
    SnapshotHistoryResponse,
    SnapshotHistoryRow,
    SnapshotSummary,
    WhaleAlertsResponse,
)
from src.config import settings
from src.db import SessionLocal
from src.models import IngestionRun, MarketSnapshot, Signal
from src.queries import (
    get_ingestion_run_by_id,
    get_market_detail_for_api,
    get_market_history,
    get_market_signals,
    get_markets_for_api,
    get_recent_ingestion_runs,
    get_recent_signals,
)


API_VERSION = "0.4.0"

app = FastAPI(
    title="Information Edge API",
    description="Read-only analytics API for markets, historical snapshots, signals, and pipeline observability.",
    version=API_VERSION,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _snapshot_summary(snapshot: MarketSnapshot | None) -> SnapshotSummary | None:
    if snapshot is None:
        return None
    return SnapshotSummary(
        observed_at=snapshot.observed_at,
        last_trade_price=_decimal_to_float(snapshot.last_trade_price),
        volume=_decimal_to_float(snapshot.volume),
        liquidity=_decimal_to_float(snapshot.liquidity),
    )


def _signal_response(signal: Signal, market) -> SignalResponse:
    return SignalResponse(
        id=signal.id,
        market_id=market.market_id,
        event_id=market.event.event_id,
        market_question=market.question,
        market_slug=market.slug,
        market_active=market.active,
        market_closed=market.closed,
        signal_type=signal.signal_type,
        signal_strength=float(signal.signal_strength),
        detected_at=signal.detected_at,
        summary=signal.metadata_json.get("summary"),
        metadata=signal.metadata_json,
    )


def _run_response(run: IngestionRun) -> RunResponse:
    return RunResponse(
        id=run.id,
        status=run.status,
        trigger_mode=run.trigger_mode,
        run_started_at=run.run_started_at,
        run_finished_at=run.run_finished_at,
        duration_ms=run.duration_ms,
        records_fetched=run.records_fetched,
        events_upserted=run.events_upserted,
        markets_upserted=run.markets_upserted,
        snapshots_inserted=run.snapshots_inserted,
        records_skipped=run.records_skipped,
        integrity_errors=run.integrity_errors,
        error_message=run.error_message,
    )


@app.get("/", response_model=ApiIndexResponse, summary="API index")
def api_index() -> ApiIndexResponse:
    return ApiIndexResponse(
        message="Information Edge API is running.",
        docs_url="/docs",
        route_groups=["/health", "/markets", "/signals", "/runs", "/whale-alerts"],
    )


@app.get("/health", response_model=HealthResponse, summary="Health check")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc),
        version=API_VERSION,
    )


@app.get("/markets", response_model=MarketListResponse, summary="List markets")
def list_markets_api(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    slug: str | None = None,
    active: bool | None = None,
    closed: bool | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
) -> MarketListResponse:
    rows = get_markets_for_api(
        db,
        limit=limit,
        offset=offset,
        slug=slug,
        active=active,
        closed=closed,
        q=q,
    )
    items = [
        MarketSummary(
            market_id=market.market_id,
            event_id=market.event.event_id,
            slug=market.slug,
            question=market.question,
            active=market.active,
            closed=market.closed,
            latest_price=_decimal_to_float(snapshot.last_trade_price) if snapshot else None,
            latest_volume=_decimal_to_float(snapshot.volume) if snapshot else None,
            latest_snapshot_at=snapshot.observed_at if snapshot else None,
        )
        for market, snapshot in rows
    ]
    return MarketListResponse(items=items, limit=limit, offset=offset, count=len(items))


@app.get("/markets/{market_id}", response_model=MarketDetailResponse, summary="Get market detail")
def get_market_api(market_id: str, db: Session = Depends(get_db)) -> MarketDetailResponse:
    detail = get_market_detail_for_api(db, market_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Market not found.")
    market, event, latest_snapshot, outcomes = detail
    return MarketDetailResponse(
        market_id=market.market_id,
        event_id=str(market.event_id),
        event_api_id=event.event_id,
        slug=market.slug,
        question=market.question,
        description=market.description,
        resolution_source=market.resolution_source,
        market_type=market.market_type,
        active=market.active,
        closed=market.closed,
        archived=market.archived,
        restricted=market.restricted,
        latest_snapshot=_snapshot_summary(latest_snapshot),
        outcomes=[
            MarketOutcomeResponse(
                outcome_index=outcome.outcome_index,
                outcome_label=outcome.outcome_label,
                current_price=_decimal_to_float(outcome.current_price),
                clob_token_id=outcome.clob_token_id,
                uma_resolution_status=outcome.uma_resolution_status,
            )
            for outcome in outcomes
        ],
    )


@app.get(
    "/markets/{market_id}/history",
    response_model=SnapshotHistoryResponse,
    summary="Get market snapshot history",
)
def get_market_history_api(
    market_id: str,
    limit: int = Query(100, ge=1, le=500),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    db: Session = Depends(get_db),
) -> SnapshotHistoryResponse:
    detail = get_market_detail_for_api(db, market_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Market not found.")
    rows = get_market_history(
        db,
        market_id,
        limit=limit,
        start_time=start_time,
        end_time=end_time,
    )
    return SnapshotHistoryResponse(
        market_id=market_id,
        items=[
            SnapshotHistoryRow(
                observed_at=row.observed_at,
                last_trade_price=_decimal_to_float(row.last_trade_price),
                best_bid=_decimal_to_float(row.best_bid),
                best_ask=_decimal_to_float(row.best_ask),
                volume=_decimal_to_float(row.volume),
                liquidity=_decimal_to_float(row.liquidity),
            )
            for row in rows
        ],
        count=len(rows),
    )


@app.get(
    "/markets/{market_id}/signals",
    response_model=SignalListResponse,
    summary="Get signals for one market",
)
def get_market_signals_api(
    market_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SignalListResponse:
    detail = get_market_detail_for_api(db, market_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Market not found.")
    rows = get_market_signals(db, market_id, limit=limit)
    items = [_signal_response(signal, market) for signal, market in rows]
    return SignalListResponse(items=items, limit=limit, count=len(items))


@app.get("/signals", response_model=SignalListResponse, summary="List recent signals")
def get_signals_api(
    limit: int = Query(20, ge=1, le=100),
    signal_type: str | None = None,
    market_id: str | None = None,
    db: Session = Depends(get_db),
) -> SignalListResponse:
    rows = get_recent_signals(db, limit=limit, signal_type=signal_type, market_id=market_id)
    items = [_signal_response(signal, market) for signal, market in rows]
    return SignalListResponse(items=items, limit=limit, count=len(items))


@app.get("/runs", response_model=RunListResponse, summary="List recent ingestion runs")
def get_runs_api(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> RunListResponse:
    runs = get_recent_ingestion_runs(db, limit=limit)
    items = [_run_response(run) for run in runs]
    return RunListResponse(items=items, limit=limit, count=len(items))


@app.get("/runs/{run_id}", response_model=RunResponse, summary="Get one ingestion run")
def get_run_api(run_id: int, db: Session = Depends(get_db)) -> RunResponse:
    run = get_ingestion_run_by_id(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _run_response(run)


@app.get("/whale-alerts", response_model=WhaleAlertsResponse, summary="Whale alerts placeholder")
def get_whale_alerts_api() -> WhaleAlertsResponse:
    return WhaleAlertsResponse(
        status="unavailable",
        message="Trade ingestion is not active yet; whale alerts are deferred.",
        alerts=[],
    )
