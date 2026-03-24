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
    category: str | None = None
    has_signals: bool = False
    has_whales: bool = False
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
    available_categories: list[str] = Field(default_factory=list)


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
    market_question: str | None = None
    market_slug: str | None = None
    market_active: bool | None = None
    market_closed: bool | None = None
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


class WhaleEventResponse(BaseModel):
    id: int
    market_id: str
    event_id: str
    market_question: str | None = None
    market_slug: str | None = None
    detected_at: datetime
    trade_size: float
    whale_score: float
    median_multiple: float | None = None
    side: str | None = None
    outcome_label: str | None = None
    proxy_wallet: str | None = None
    detection_method: str
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WhaleListResponse(BaseModel):
    items: list[WhaleEventResponse]
    limit: int
    count: int


class WhaleSummaryResponse(BaseModel):
    market_id: str
    total_whale_events: int
    most_recent_whale_at: datetime | None = None
    largest_whale_trade: float | None = None
    average_whale_score: float | None = None
    whale_events_24h: int
    whale_events_7d: int
    has_recent_whale_activity: bool


class WhaleAlertsResponse(BaseModel):
    status: str
    message: str
    alerts: list[WhaleEventResponse]


class MarketSentimentSummaryResponse(BaseModel):
    market_id: str
    status: str
    message: str | None = None
    avg_sentiment: float
    doc_count: int
    pos_count: int
    neg_count: int
    neutral_count: int
    last_updated: datetime


class SentimentDocumentResponse(BaseModel):
    id: int
    source_name: str | None = None
    url: str
    title: str | None = None
    snippet: str | None = None
    published_at: datetime | None = None
    sentiment_label: str | None = None
    sentiment_confidence: float | None = None
    sentiment_value: float | None = None


class SentimentDocumentListResponse(BaseModel):
    market_id: str
    status: str
    message: str | None = None
    items: list[SentimentDocumentResponse]
    count: int
