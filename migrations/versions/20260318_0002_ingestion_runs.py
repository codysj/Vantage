"""add ingestion runs table"""

from alembic import op
import sqlalchemy as sa


revision = "20260318_0002"
down_revision = "20260318_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger_mode", sa.String(length=32), nullable=False),
        sa.Column("scheduler_job_id", sa.String(length=128)),
        sa.Column("api_source", sa.String(length=64), nullable=False),
        sa.Column("records_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("events_upserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("markets_upserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshots_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("integrity_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_index(
        "ix_ingestion_runs_started_status",
        "ingestion_runs",
        ["run_started_at", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_started_status", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_status", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
