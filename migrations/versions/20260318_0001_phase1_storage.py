"""phase 1 storage schema"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260318_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=255)),
        sa.Column("ticker", sa.String(length=128)),
        sa.Column("title", sa.String(length=512)),
        sa.Column("description", sa.Text()),
        sa.Column("question", sa.Text()),
        sa.Column("category", sa.String(length=255)),
        sa.Column("active", sa.Boolean()),
        sa.Column("closed", sa.Boolean()),
        sa.Column("archived", sa.Boolean()),
        sa.Column("featured", sa.Boolean()),
        sa.Column("restricted", sa.Boolean()),
        sa.Column("created_at_api", sa.DateTime(timezone=True)),
        sa.Column("updated_at_api", sa.DateTime(timezone=True)),
        sa.Column("start_date", sa.DateTime(timezone=True)),
        sa.Column("end_date", sa.DateTime(timezone=True)),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_events_event_id", "events", ["event_id"])

    op.create_table(
        "markets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("condition_id", sa.String(length=255)),
        sa.Column("question_id", sa.String(length=255)),
        sa.Column("slug", sa.String(length=255)),
        sa.Column("question", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("resolution_source", sa.Text()),
        sa.Column("market_type", sa.String(length=128)),
        sa.Column("active", sa.Boolean()),
        sa.Column("closed", sa.Boolean()),
        sa.Column("archived", sa.Boolean()),
        sa.Column("restricted", sa.Boolean()),
        sa.Column("accepting_orders", sa.Boolean()),
        sa.Column("enable_order_book", sa.Boolean()),
        sa.Column("order_min_size", sa.Numeric(20, 8)),
        sa.Column("order_price_min_tick_size", sa.Numeric(20, 8)),
        sa.Column("group_item_title", sa.String(length=255)),
        sa.Column("group_item_threshold", sa.Numeric(20, 8)),
        sa.Column("created_at_api", sa.DateTime(timezone=True)),
        sa.Column("updated_at_api", sa.DateTime(timezone=True)),
        sa.Column("start_date", sa.DateTime(timezone=True)),
        sa.Column("end_date", sa.DateTime(timezone=True)),
        sa.Column("start_date_iso", sa.DateTime(timezone=True)),
        sa.Column("end_date_iso", sa.DateTime(timezone=True)),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("market_id"),
    )
    op.create_index("ix_markets_market_id", "markets", ["market_id"])
    op.create_index("ix_markets_event_id", "markets", ["event_id"])
    op.create_index("ix_markets_slug", "markets", ["slug"])

    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("snapshot_key", sa.String(length=128), nullable=False),
        sa.Column("last_trade_price", sa.Numeric(20, 8)),
        sa.Column("best_bid", sa.Numeric(20, 8)),
        sa.Column("best_ask", sa.Numeric(20, 8)),
        sa.Column("spread", sa.Numeric(20, 8)),
        sa.Column("volume", sa.Numeric(20, 8)),
        sa.Column("volume_24hr", sa.Numeric(20, 8)),
        sa.Column("volume_1wk", sa.Numeric(20, 8)),
        sa.Column("volume_1mo", sa.Numeric(20, 8)),
        sa.Column("volume_1yr", sa.Numeric(20, 8)),
        sa.Column("liquidity", sa.Numeric(20, 8)),
        sa.Column("liquidity_clob", sa.Numeric(20, 8)),
        sa.Column("volume_clob", sa.Numeric(20, 8)),
        sa.Column("open_interest", sa.Numeric(20, 8)),
        sa.Column("one_day_price_change", sa.Numeric(20, 8)),
        sa.Column("one_week_price_change", sa.Numeric(20, 8)),
        sa.Column("one_month_price_change", sa.Numeric(20, 8)),
        sa.Column("one_year_price_change", sa.Numeric(20, 8)),
        sa.Column("outcome_prices", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("snapshot_key", name="uq_market_snapshots_snapshot_key"),
    )
    op.create_index(
        "ix_market_snapshots_market_observed",
        "market_snapshots",
        ["market_id", "observed_at"],
    )
    op.create_index("ix_market_snapshots_market_id", "market_snapshots", ["market_id"])

    op.create_table(
        "market_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("outcome_index", sa.Integer(), nullable=False),
        sa.Column("outcome_label", sa.String(length=255)),
        sa.Column("current_price", sa.Numeric(20, 8)),
        sa.Column("clob_token_id", sa.String(length=255)),
        sa.Column("uma_resolution_status", sa.String(length=255)),
        sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("market_id", "outcome_index", name="uq_market_outcomes_market_index"),
    )
    op.create_index("ix_market_outcomes_market_id", "market_outcomes", ["market_id"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tag_key", sa.String(length=255), nullable=False),
        sa.Column("external_tag_id", sa.String(length=64)),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255)),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tag_key"),
        sa.UniqueConstraint("external_tag_id"),
    )
    op.create_index("ix_tags_tag_key", "tags", ["tag_key"])

    op.create_table(
        "event_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "tag_id", name="uq_event_tags_event_tag"),
    )
    op.create_index("ix_event_tags_event_id", "event_tags", ["event_id"])
    op.create_index("ix_event_tags_tag_id", "event_tags", ["tag_id"])

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("external_trade_id", sa.String(length=128)),
        sa.Column("side", sa.String(length=32)),
        sa.Column("price", sa.Numeric(20, 8)),
        sa.Column("size", sa.Numeric(20, 8)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("external_trade_id"),
    )
    op.create_index("ix_trades_market_id", "trades", ["market_id"])
    op.create_index("ix_trades_market_executed", "trades", ["market_id", "executed_at"])


def downgrade() -> None:
    op.drop_index("ix_trades_market_executed", table_name="trades")
    op.drop_index("ix_trades_market_id", table_name="trades")
    op.drop_table("trades")

    op.drop_index("ix_event_tags_tag_id", table_name="event_tags")
    op.drop_index("ix_event_tags_event_id", table_name="event_tags")
    op.drop_table("event_tags")

    op.drop_index("ix_tags_tag_key", table_name="tags")
    op.drop_table("tags")

    op.drop_index("ix_market_outcomes_market_id", table_name="market_outcomes")
    op.drop_table("market_outcomes")

    op.drop_index("ix_market_snapshots_market_id", table_name="market_snapshots")
    op.drop_index("ix_market_snapshots_market_observed", table_name="market_snapshots")
    op.drop_table("market_snapshots")

    op.drop_index("ix_markets_slug", table_name="markets")
    op.drop_index("ix_markets_event_id", table_name="markets")
    op.drop_index("ix_markets_market_id", table_name="markets")
    op.drop_table("markets")

    op.drop_index("ix_events_event_id", table_name="events")
    op.drop_table("events")
