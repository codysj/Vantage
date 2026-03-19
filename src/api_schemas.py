from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str


class ApiIndexResponse(BaseModel):
    message: str
    docs_url: str
    route_groups: list[str]


class SnapshotSummary(BaseModel):
    observed_at: datetime
    last_trade_price: float | None = None
    volume: float | None = None
    liquidity: float | None = None


class MarketSummary(BaseModel):
    market_id: str
    event_id: str
    slug: str | None = None
    question: str | None = None
    active: bool | None = None
    closed: bool | None = None
    latest_price: float | None = None
    latest_volume: float | None = None
    latest_snapshot_at: datetime | None = None


class MarketListResponse(BaseModel):
    items: list[MarketSummary]
    limit: int
    offset: int
    count: int


class MarketOutcomeResponse(BaseModel):
    outcome_index: int
    outcome_label: str | None = None
    current_price: float | None = None
    clob_token_id: str | None = None
    uma_resolution_status: str | None = None


class MarketDetailResponse(BaseModel):
    market_id: str
    event_id: str
    event_api_id: str
    slug: str | None = None
    question: str | None = None
    description: str | None = None
    resolution_source: str | None = None
    market_type: str | None = None
    active: bool | None = None
    closed: bool | None = None
    archived: bool | None = None
    restricted: bool | None = None
    latest_snapshot: SnapshotSummary | None = None
    outcomes: list[MarketOutcomeResponse]


class SnapshotHistoryRow(BaseModel):
    observed_at: datetime
    last_trade_price: float | None = None
    best_bid: float | None = None
    best_ask: float | None = None
    volume: float | None = None
    liquidity: float | None = None


class SnapshotHistoryResponse(BaseModel):
    market_id: str
    items: list[SnapshotHistoryRow]
    count: int


class SignalResponse(BaseModel):
    id: int
    market_id: str
    event_id: str
    signal_type: str
    signal_strength: float
    detected_at: datetime
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SignalListResponse(BaseModel):
    items: list[SignalResponse]
    limit: int
    count: int


class RunResponse(BaseModel):
    id: int
    status: str
    trigger_mode: str
    run_started_at: datetime
    run_finished_at: datetime | None = None
    duration_ms: int | None = None
    records_fetched: int
    events_upserted: int
    markets_upserted: int
    snapshots_inserted: int
    records_skipped: int
    integrity_errors: int
    error_message: str | None = None


class RunListResponse(BaseModel):
    items: list[RunResponse]
    limit: int
    count: int


class WhaleAlertsResponse(BaseModel):
    status: str
    message: str
    alerts: list[dict[str, Any]]
