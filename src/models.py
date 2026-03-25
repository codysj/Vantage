"""SQLAlchemy models for the full market-intelligence system.

The tables mirror the product architecture: raw market data and historical
snapshots, derived analytics such as signals and whale events, and the lazy
sentiment cache used by the dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


JSONType = JSON().with_variant(JSONB, "postgresql")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Event(TimestampMixin, Base):
    """A Polymarket event and its slow-changing metadata."""
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255))
    ticker: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool | None] = mapped_column(Boolean)
    closed: Mapped[bool | None] = mapped_column(Boolean)
    archived: Mapped[bool | None] = mapped_column(Boolean)
    featured: Mapped[bool | None] = mapped_column(Boolean)
    restricted: Mapped[bool | None] = mapped_column(Boolean)
    created_at_api: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at_api: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    markets: Mapped[list["Market"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    event_tags: Mapped[list["EventTag"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(back_populates="event")


class Market(TimestampMixin, Base):
    """One tradeable contract under an event."""
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    condition_id: Mapped[str | None] = mapped_column(String(255))
    question_id: Mapped[str | None] = mapped_column(String(255))
    slug: Mapped[str | None] = mapped_column(String(255), index=True)
    question: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    resolution_source: Mapped[str | None] = mapped_column(Text)
    market_type: Mapped[str | None] = mapped_column(String(128))
    active: Mapped[bool | None] = mapped_column(Boolean)
    closed: Mapped[bool | None] = mapped_column(Boolean)
    archived: Mapped[bool | None] = mapped_column(Boolean)
    restricted: Mapped[bool | None] = mapped_column(Boolean)
    accepting_orders: Mapped[bool | None] = mapped_column(Boolean)
    enable_order_book: Mapped[bool | None] = mapped_column(Boolean)
    order_min_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    order_price_min_tick_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    group_item_title: Mapped[str | None] = mapped_column(String(255))
    group_item_threshold: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    created_at_api: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at_api: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_date_iso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date_iso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    event: Mapped["Event"] = relationship(back_populates="markets")
    outcomes: Mapped[list["MarketOutcome"]] = relationship(
        back_populates="market", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["MarketSnapshot"]] = relationship(
        back_populates="market", cascade="all, delete-orphan"
    )
    trades: Mapped[list["Trade"]] = relationship(back_populates="market")
    signals: Mapped[list["Signal"]] = relationship(back_populates="market")
    whale_events: Mapped[list["WhaleEvent"]] = relationship(back_populates="market")
    sentiment_documents: Mapped[list["SentimentDocument"]] = relationship(
        back_populates="market"
    )
    sentiment_summary: Mapped["MarketSentimentSummary | None"] = relationship(
        back_populates="market",
        uselist=False,
    )


class MarketSnapshot(Base):
    """A point-in-time observation used for price history and anomaly rules."""
    __tablename__ = "market_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_key", name="uq_market_snapshots_snapshot_key"),
        Index("ix_market_snapshots_market_observed", "market_id", "observed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_key: Mapped[str] = mapped_column(String(128), nullable=False)
    last_trade_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    best_bid: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    best_ask: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    spread: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume_24hr: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume_1wk: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume_1mo: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume_1yr: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    liquidity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    liquidity_clob: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume_clob: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    open_interest: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    one_day_price_change: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    one_week_price_change: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    one_month_price_change: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    one_year_price_change: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    outcome_prices: Mapped[list[Any] | None] = mapped_column(JSONType)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    market: Mapped["Market"] = relationship(back_populates="snapshots")
    signals: Mapped[list["Signal"]] = relationship(back_populates="snapshot")


class MarketOutcome(TimestampMixin, Base):
    """Normalized per-outcome data so binary and multi-outcome markets share one shape."""
    __tablename__ = "market_outcomes"
    __table_args__ = (
        UniqueConstraint("market_id", "outcome_index", name="uq_market_outcomes_market_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    outcome_index: Mapped[int] = mapped_column(nullable=False)
    outcome_label: Mapped[str | None] = mapped_column(String(255))
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    clob_token_id: Mapped[str | None] = mapped_column(String(255))
    uma_resolution_status: Mapped[str | None] = mapped_column(String(255))

    market: Mapped["Market"] = relationship(back_populates="outcomes")


class Tag(TimestampMixin, Base):
    """Event-level category/tag metadata from the source payload."""
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    tag_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    external_tag_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255))
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    event_tags: Mapped[list["EventTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class EventTag(Base):
    """Join table linking stored events to normalized tags."""
    __tablename__ = "event_tags"
    __table_args__ = (UniqueConstraint("event_id", "tag_id", name="uq_event_tags_event_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), nullable=False, index=True)
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    event: Mapped["Event"] = relationship(back_populates="event_tags")
    tag: Mapped["Tag"] = relationship(back_populates="event_tags")


class Trade(Base):
    """Normalized trade history used for whale detection and market drill-downs."""
    __tablename__ = "trades"
    __table_args__ = (Index("ix_trades_market_executed", "market_id", "executed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    external_trade_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    side: Mapped[str | None] = mapped_column(String(32))
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    trade_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    proxy_wallet: Mapped[str | None] = mapped_column(String(128))
    outcome_label: Mapped[str | None] = mapped_column(String(255))
    outcome_index: Mapped[int | None] = mapped_column()
    transaction_hash: Mapped[str | None] = mapped_column(String(128))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    market: Mapped["Market"] = relationship(back_populates="trades")
    whale_events: Mapped[list["WhaleEvent"]] = relationship(back_populates="trade")


class IngestionRun(Base):
    """Operational record for one ingestion cycle."""
    __tablename__ = "ingestion_runs"
    __table_args__ = (Index("ix_ingestion_runs_started_status", "run_started_at", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    run_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trigger_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduler_job_id: Mapped[str | None] = mapped_column(String(128))
    api_source: Mapped[str] = mapped_column(String(64), nullable=False, default="gamma_events")
    records_fetched: Mapped[int] = mapped_column(nullable=False, default=0)
    events_upserted: Mapped[int] = mapped_column(nullable=False, default=0)
    markets_upserted: Mapped[int] = mapped_column(nullable=False, default=0)
    snapshots_inserted: Mapped[int] = mapped_column(nullable=False, default=0)
    records_skipped: Mapped[int] = mapped_column(nullable=False, default=0)
    integrity_errors: Mapped[int] = mapped_column(nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column()
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("market_id", "signal_type", "snapshot_id", name="uq_signals_market_type_snapshot"),
        Index("ix_signals_detected_at", "detected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("market_snapshots.id"), nullable=False, index=True
    )
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signal_strength: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    market: Mapped["Market"] = relationship(back_populates="signals")
    event: Mapped["Event"] = relationship(back_populates="signals")
    snapshot: Mapped["MarketSnapshot"] = relationship(back_populates="signals")


class WhaleEvent(Base):
    __tablename__ = "whale_events"
    __table_args__ = (
        UniqueConstraint("trade_id", "detection_method", name="uq_whale_events_trade_method"),
        Index("ix_whale_events_detected_at", "detected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), nullable=False, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_size: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    baseline_mean_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    baseline_median_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    baseline_std_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    median_multiple: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    whale_score: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    market: Mapped["Market"] = relationship(back_populates="whale_events")
    trade: Mapped["Trade"] = relationship(back_populates="whale_events")


class SentimentDocument(Base):
    __tablename__ = "sentiment_documents"
    __table_args__ = (
        UniqueConstraint("url", name="uq_sentiment_documents_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    source_name: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    market: Mapped["Market"] = relationship(back_populates="sentiment_documents")
    scores: Mapped[list["SentimentScore"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class SentimentScore(Base):
    __tablename__ = "sentiment_scores"
    __table_args__ = (
        UniqueConstraint("document_id", "model_name", name="uq_sentiment_scores_doc_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("sentiment_documents.id"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sentiment_label: Mapped[str] = mapped_column(String(32), nullable=False)
    sentiment_confidence: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    sentiment_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    document: Mapped["SentimentDocument"] = relationship(back_populates="scores")


class MarketSentimentSummary(Base):
    __tablename__ = "market_sentiment_summary"
    __table_args__ = (
        UniqueConstraint("market_id", name="uq_market_sentiment_summary_market_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    avg_sentiment: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=Decimal("0")
    )
    doc_count: Mapped[int] = mapped_column(nullable=False, default=0)
    pos_count: Mapped[int] = mapped_column(nullable=False, default=0)
    neg_count: Mapped[int] = mapped_column(nullable=False, default=0)
    neutral_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    market: Mapped["Market"] = relationship(back_populates="sentiment_summary")
