"""add sentiment cache tables

Revision ID: 20260323_0005
Revises: 20260319_0004
Create Date: 2026-03-23 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323_0005"
down_revision = "20260319_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sentiment_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_sentiment_documents_url"),
    )
    op.create_index(
        "ix_sentiment_documents_market_id",
        "sentiment_documents",
        ["market_id"],
        unique=False,
    )

    op.create_table(
        "sentiment_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("sentiment_label", sa.String(length=32), nullable=False),
        sa.Column("sentiment_confidence", sa.Numeric(20, 8), nullable=False),
        sa.Column("sentiment_value", sa.Numeric(20, 8), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["sentiment_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "model_name", name="uq_sentiment_scores_doc_model"),
    )
    op.create_index(
        "ix_sentiment_scores_document_id",
        "sentiment_scores",
        ["document_id"],
        unique=False,
    )

    op.create_table(
        "market_sentiment_summary",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("avg_sentiment", sa.Numeric(20, 8), nullable=False),
        sa.Column("doc_count", sa.Integer(), nullable=False),
        sa.Column("pos_count", sa.Integer(), nullable=False),
        sa.Column("neg_count", sa.Integer(), nullable=False),
        sa.Column("neutral_count", sa.Integer(), nullable=False),
        sa.Column("last_computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", name="uq_market_sentiment_summary_market_id"),
    )
    op.create_index(
        "ix_market_sentiment_summary_market_id",
        "market_sentiment_summary",
        ["market_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_sentiment_summary_market_id", table_name="market_sentiment_summary")
    op.drop_table("market_sentiment_summary")
    op.drop_index("ix_sentiment_scores_document_id", table_name="sentiment_scores")
    op.drop_table("sentiment_scores")
    op.drop_index("ix_sentiment_documents_market_id", table_name="sentiment_documents")
    op.drop_table("sentiment_documents")
