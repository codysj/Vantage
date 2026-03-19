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


class Market(TimestampMixin, Base):
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


class MarketSnapshot(Base):
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


class MarketOutcome(TimestampMixin, Base):
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
    __tablename__ = "trades"
    __table_args__ = (Index("ix_trades_market_executed", "market_id", "executed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    external_trade_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    side: Mapped[str | None] = mapped_column(String(32))
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    market: Mapped["Market"] = relationship(back_populates="trades")


class IngestionRun(Base):
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
