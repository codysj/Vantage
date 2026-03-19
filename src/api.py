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
    WhaleEventResponse,
    WhaleAlertsResponse,
    WhaleListResponse,
    WhaleSummaryResponse,
)
from src.config import settings
from src.db import SessionLocal
from src.models import IngestionRun, MarketSnapshot, Signal, Trade, WhaleEvent
from src.queries import (
    get_available_market_categories,
    get_ingestion_run_by_id,
    get_market_detail_for_api,
    get_market_history,
    get_market_signals,
    get_markets_for_api,
    get_market_whale_summary,
    get_market_whales,
    get_recent_ingestion_runs,
    get_recent_signals,
    get_recent_whale_events,
    get_signal_feed,
)


API_VERSION = "0.5.0"

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


def _whale_response(whale_event: WhaleEvent, market, trade: Trade | None = None) -> WhaleEventResponse:
    trade_record = trade or whale_event.trade
    return WhaleEventResponse(
        id=whale_event.id,
        market_id=market.market_id,
        event_id=market.event.event_id,
        market_question=market.question,
        market_slug=market.slug,
        detected_at=whale_event.detected_at,
        trade_size=float(whale_event.trade_size),
        whale_score=float(whale_event.whale_score),
        median_multiple=(
            float(whale_event.median_multiple) if whale_event.median_multiple is not None else None
        ),
        side=trade_record.side if trade_record else None,
        outcome_label=trade_record.outcome_label if trade_record else None,
        proxy_wallet=trade_record.proxy_wallet if trade_record else None,
        detection_method=whale_event.detection_method,
        summary=whale_event.metadata_json.get("summary"),
        metadata=whale_event.metadata_json,
    )


def _feed_signal_response(item) -> SignalResponse:
    if item.source == "whale":
        whale_event = item.record
        market = item.market
        trade = whale_event.trade
        metadata = dict(whale_event.metadata_json)
        return SignalResponse(
            id=whale_event.id,
            market_id=market.market_id,
            event_id=market.event.event_id,
            market_question=market.question,
            market_slug=market.slug,
            market_active=market.active,
            market_closed=market.closed,
            signal_type="whale",
            signal_strength=float(whale_event.whale_score),
            detected_at=whale_event.detected_at,
            summary=metadata.get("summary"),
            metadata={
                **metadata,
                "side": trade.side if trade else metadata.get("side"),
                "outcome_label": trade.outcome_label if trade else metadata.get("outcome_label"),
                "proxy_wallet": trade.proxy_wallet if trade else metadata.get("proxy_wallet"),
            },
        )
    return _signal_response(item.record, item.market)


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
        route_groups=["/health", "/markets", "/signals", "/runs", "/whales", "/whale-alerts"],
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
    category: str | None = None,
    has_signals: bool | None = None,
    signal_type: str | None = None,
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
        category=category,
        has_signals=has_signals,
        signal_type=signal_type,
    )
    items = [
        MarketSummary(
            market_id=market.market_id,
            event_id=market.event.event_id,
            slug=market.slug,
            question=market.question,
            category=market_category,
            has_signals=has_signals_value,
            has_whales=has_whales_value,
            active=market.active,
            closed=market.closed,
            latest_price=_decimal_to_float(snapshot.last_trade_price) if snapshot else None,
            latest_volume=_decimal_to_float(snapshot.volume) if snapshot else None,
            latest_snapshot_at=snapshot.observed_at if snapshot else None,
        )
        for market, snapshot, market_category, has_signals_value, has_whales_value in rows
    ]
    return MarketListResponse(
        items=items,
        limit=limit,
        offset=offset,
        count=len(items),
        available_categories=get_available_market_categories(db),
    )


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
    items = [_feed_signal_response(item) for item in rows]
    return SignalListResponse(items=items, limit=limit, count=len(items))


@app.get("/signals", response_model=SignalListResponse, summary="List recent signals")
def get_signals_api(
    limit: int = Query(20, ge=1, le=100),
    signal_type: str | None = None,
    market_id: str | None = None,
    db: Session = Depends(get_db),
) -> SignalListResponse:
    rows = get_signal_feed(db, limit=limit, signal_type=signal_type, market_id=market_id)
    items = [_feed_signal_response(item) for item in rows]
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


@app.get("/whales/recent", response_model=WhaleListResponse, summary="List recent whale events")
def get_whales_api(
    limit: int = Query(20, ge=1, le=100),
    category: str | None = None,
    min_score: float | None = Query(None, ge=0),
    market_id: str | None = None,
    db: Session = Depends(get_db),
) -> WhaleListResponse:
    rows = get_recent_whale_events(
        db,
        limit=limit,
        category=category,
        min_score=Decimal(str(min_score)) if min_score is not None else None,
        market_id=market_id,
    )
    items = [_whale_response(whale_event, market, trade) for whale_event, market, trade in rows]
    return WhaleListResponse(items=items, limit=limit, count=len(items))


@app.get(
    "/markets/{market_id}/whales",
    response_model=WhaleListResponse,
    summary="Get whale events for one market",
)
def get_market_whales_api(
    market_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> WhaleListResponse:
    detail = get_market_detail_for_api(db, market_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Market not found.")
    rows = get_market_whales(db, market_id, limit=limit)
    items = [_whale_response(whale_event, market, trade) for whale_event, market, trade in rows]
    return WhaleListResponse(items=items, limit=limit, count=len(items))


@app.get(
    "/markets/{market_id}/whale-summary",
    response_model=WhaleSummaryResponse,
    summary="Get whale summary for one market",
)
def get_market_whale_summary_api(
    market_id: str,
    db: Session = Depends(get_db),
) -> WhaleSummaryResponse:
    summary = get_market_whale_summary(db, market_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Market not found.")
    return WhaleSummaryResponse(
        market_id=summary["market_id"],
        total_whale_events=summary["total_whale_events"],
        most_recent_whale_at=summary["most_recent_whale_at"],
        largest_whale_trade=_decimal_to_float(summary["largest_whale_trade"]),
        average_whale_score=_decimal_to_float(summary["average_whale_score"]),
        whale_events_24h=summary["whale_events_24h"],
        whale_events_7d=summary["whale_events_7d"],
        has_recent_whale_activity=summary["has_recent_whale_activity"],
    )


@app.get("/whale-alerts", response_model=WhaleAlertsResponse, summary="List recent whale alerts")
def get_whale_alerts_api(db: Session = Depends(get_db)) -> WhaleAlertsResponse:
    rows = get_recent_whale_events(db, limit=10)
    alerts = [_whale_response(whale_event, market, trade) for whale_event, market, trade in rows]
    return WhaleAlertsResponse(
        status="ok",
        message=(
            "Recent whale alerts across tracked markets."
            if alerts
            else "No whale alerts detected yet."
        ),
        alerts=alerts,
    )
