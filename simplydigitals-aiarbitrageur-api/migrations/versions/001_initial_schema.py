"""Initial schema — tickers, watchlist, prices, portfolio, triggers.

Revision ID: 001_initial_schema
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tickers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("exchange", sa.String(50), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tickers_symbol", "tickers", ["symbol"])

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("ticker_id", sa.String(36), sa.ForeignKey("tickers.id"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "ticker_id"),
    )
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"])

    op.create_table(
        "closing_prices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticker_id", sa.String(36), sa.ForeignKey("tickers.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("open", sa.Float, nullable=True),
        sa.Column("high", sa.Float, nullable=True),
        sa.Column("low", sa.Float, nullable=True),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("volume", sa.Integer, nullable=True),
        sa.UniqueConstraint("ticker_id", "date"),
    )
    op.create_index("ix_closing_prices_ticker_id", "closing_prices", ["ticker_id"])

    op.create_table(
        "intraday_prices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticker_id", sa.String(36), sa.ForeignKey("tickers.id"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float, nullable=True),
        sa.Column("high", sa.Float, nullable=True),
        sa.Column("low", sa.Float, nullable=True),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("volume", sa.Integer, nullable=True),
        sa.UniqueConstraint("ticker_id", "ts"),
    )
    op.create_index("ix_intraday_prices_ticker_id", "intraday_prices", ["ticker_id"])
    op.create_index("ix_intraday_prices_ts", "intraday_prices", ["ts"])

    op.create_table(
        "portfolio_positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("avg_cost", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portfolio_positions_user_id", "portfolio_positions", ["user_id"])

    op.create_table(
        "trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("ticker_id", sa.String(36), sa.ForeignKey("tickers.id"), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trades_user_id", "trades", ["user_id"])

    op.create_table(
        "triggers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("ticker_id", sa.String(36), sa.ForeignKey("tickers.id"), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("condition_type", sa.String(20), nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("action", sa.String(10), nullable=False, server_default="alert"),
        sa.Column("qty", sa.Float, nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_triggers_user_id", "triggers", ["user_id"])


def downgrade() -> None:
    op.drop_table("triggers")
    op.drop_table("trades")
    op.drop_table("portfolio_positions")
    op.drop_table("intraday_prices")
    op.drop_table("closing_prices")
    op.drop_table("watchlist_items")
    op.drop_table("tickers")
