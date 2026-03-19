"""add whale events and trade metadata"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260319_0004"
down_revision = "20260318_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trades", sa.Column("trade_size", sa.Numeric(20, 8), nullable=True))
    op.add_column("trades", sa.Column("proxy_wallet", sa.String(length=128), nullable=True))
    op.add_column("trades", sa.Column("outcome_label", sa.String(length=255), nullable=True))
    op.add_column("trades", sa.Column("outcome_index", sa.Integer(), nullable=True))
    op.add_column("trades", sa.Column("transaction_hash", sa.String(length=128), nullable=True))

    op.create_table(
        "whale_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("trade_id", sa.Integer(), sa.ForeignKey("trades.id"), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_size", sa.Numeric(20, 8), nullable=False),
        sa.Column("baseline_mean_size", sa.Numeric(20, 8)),
        sa.Column("baseline_median_size", sa.Numeric(20, 8)),
        sa.Column("baseline_std_size", sa.Numeric(20, 8)),
        sa.Column("median_multiple", sa.Numeric(20, 8)),
        sa.Column("whale_score", sa.Numeric(20, 8), nullable=False),
        sa.Column("detection_method", sa.String(length=64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trade_id", "detection_method", name="uq_whale_events_trade_method"),
    )
    op.create_index("ix_whale_events_market_id", "whale_events", ["market_id"])
    op.create_index("ix_whale_events_trade_id", "whale_events", ["trade_id"])
    op.create_index("ix_whale_events_detected_at", "whale_events", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_whale_events_detected_at", table_name="whale_events")
    op.drop_index("ix_whale_events_trade_id", table_name="whale_events")
    op.drop_index("ix_whale_events_market_id", table_name="whale_events")
    op.drop_table("whale_events")

    op.drop_column("trades", "transaction_hash")
    op.drop_column("trades", "outcome_index")
    op.drop_column("trades", "outcome_label")
    op.drop_column("trades", "proxy_wallet")
    op.drop_column("trades", "trade_size")
