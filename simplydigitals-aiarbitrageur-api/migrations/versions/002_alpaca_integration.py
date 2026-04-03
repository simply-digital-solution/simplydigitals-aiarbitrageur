"""Add Alpaca integration — 1-min prices, trade tracking, limits.

Revision ID: 002_alpaca_integration
Revises: 001_initial_schema
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002_alpaca_integration"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tables and columns for Alpaca integration."""

    # 1. Create intraday_1min_prices table (1-minute bars)
    op.create_table(
        "intraday_1min_prices",
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
    op.create_index("ix_intraday_1min_prices_ticker_id", "intraday_1min_prices", ["ticker_id"])
    op.create_index("ix_intraday_1min_prices_ts", "intraday_1min_prices", ["ts"])

    # 2. Modify trades table — add order tracking and status
    op.add_column("trades", sa.Column("order_id", sa.String(100), nullable=True))
    op.add_column("trades", sa.Column("limit_price", sa.Float, nullable=True))
    op.add_column("trades", sa.Column("execution_price", sa.Float, nullable=True))
    op.add_column("trades", sa.Column("status", sa.String(20), nullable=False, server_default="pending"))
    op.add_column("trades", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trades", sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True))

    # Create index on order_id for fast lookups
    op.create_index("ix_trades_order_id", "trades", ["order_id"], unique=True)
    op.create_index("ix_trades_status", "trades", ["status"])
    op.create_index("ix_trades_created_at", "trades", ["created_at"])

    # 3. Create trade_limits table
    op.create_table(
        "trade_limits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, unique=True),
        sa.Column("max_position_exposure_pct", sa.Float, nullable=False, server_default="10.0"),
        sa.Column("max_daily_loss_pct", sa.Float, nullable=False, server_default="5.0"),
        sa.Column("max_order_size_pct", sa.Float, nullable=False, server_default="2.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trade_limits_user_id", "trade_limits", ["user_id"])


def downgrade() -> None:
    """Revert Alpaca integration changes."""
    op.drop_table("trade_limits")
    op.drop_index("ix_trades_created_at")
    op.drop_index("ix_trades_status")
    op.drop_index("ix_trades_order_id")
    op.drop_column("trades", "executed_at")
    op.drop_column("trades", "created_at")
    op.drop_column("trades", "status")
    op.drop_column("trades", "execution_price")
    op.drop_column("trades", "limit_price")
    op.drop_column("trades", "order_id")
    op.drop_index("ix_intraday_1min_prices_ts")
    op.drop_index("ix_intraday_1min_prices_ticker_id")
    op.drop_table("intraday_1min_prices")
