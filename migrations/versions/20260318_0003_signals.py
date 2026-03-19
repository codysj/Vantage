"""add signals table"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260318_0003"
down_revision = "20260318_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("market_snapshots.id"), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("signal_strength", sa.Numeric(20, 8), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "market_id",
            "signal_type",
            "snapshot_id",
            name="uq_signals_market_type_snapshot",
        ),
    )
    op.create_index("ix_signals_market_id", "signals", ["market_id"])
    op.create_index("ix_signals_event_id", "signals", ["event_id"])
    op.create_index("ix_signals_snapshot_id", "signals", ["snapshot_id"])
    op.create_index("ix_signals_signal_type", "signals", ["signal_type"])
    op.create_index("ix_signals_detected_at", "signals", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_signals_detected_at", table_name="signals")
    op.drop_index("ix_signals_signal_type", table_name="signals")
    op.drop_index("ix_signals_snapshot_id", table_name="signals")
    op.drop_index("ix_signals_event_id", table_name="signals")
    op.drop_index("ix_signals_market_id", table_name="signals")
    op.drop_table("signals")
